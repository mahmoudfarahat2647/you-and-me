import { useState, useEffect, useCallback, useRef } from 'react';
import { Sidebar } from './components/Sidebar';
import { WorkflowCanvas, type WorkspaceTab } from './components/WorkflowCanvas';
import { Inspector } from './components/Inspector';
import { ProjectListModal } from './components/ProjectListModal';
import { CreateProjectDialog } from './components/CreateProjectDialog';
import { ActionableError } from './components/ActionableError';
import {
  checkBackendHealth,
  listProjects,
  getTauriBackendStatus,
  restartTauriBackend,
} from './api/client';
import { useProjectMedia } from './hooks/useProjectMedia';
import { isStageId } from './lib/workflow/stages';
import type { Project, StageExecutionMode, StageId } from './types';
import { Loader2, Plus, Sparkles } from 'lucide-react';
import { Button } from './components/ui/button';

export function App() {
  const [backendStatus, setBackendStatus] = useState<'checking' | 'healthy' | 'error'>('checking');
  const [backendError, setBackendError] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const initializing = useRef(false);

  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [currentView, setCurrentView] = useState('workflow');

  const [isProjectsModalOpen, setIsProjectsModalOpen] = useState(false);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isInspectorOpen, setIsInspectorOpen] = useState(true);
  const [selectedStage, setSelectedStage] = useState('script');
  const [activeCanvasTab, setActiveCanvasTab] = useState<WorkspaceTab>('workflow');
  const [stageModes, setStageModes] = useState<Partial<Record<StageId, StageExecutionMode>>>({});
  const media = useProjectMedia(activeProject?.id);

  const handleStageModeChange = useCallback((stage: StageId, mode: StageExecutionMode) => {
    setStageModes((prev) => ({ ...prev, [stage]: mode }));
  }, []);

  const handleRunStage = useCallback(
    (stage: StageId) => {
      setSelectedStage(stage);
      if (stage === 'voice' || stage === 'scenes') {
        setActiveCanvasTab('assets');
        return;
      }
      if (stage === 'edit' || stage === 'export') {
        void media.triggerExport();
      }
    },
    [media]
  );

  const handleRunWorkflow = useCallback(() => {
    void media.triggerExport();
  }, [media]);

  const initBackendAndProjects = useCallback(async (isRetry = false) => {
    if (initializing.current) return;
    initializing.current = true;
    if (isRetry) {
      setIsRetrying(true);
      try {
        await restartTauriBackend();
      } catch {
        // ignore if not running in Tauri
      }
    } else {
      setBackendStatus('checking');
    }

    try {
      // 1. Check health
      await checkBackendHealth();
      // 2. Fetch projects from SQLite
      const loadedProjects = await listProjects();
      setProjects(loadedProjects);

      if (loadedProjects.length > 0) {
        // Keep active project if it still exists, else pick most recent
        setActiveProject((prev) => {
          if (prev && loadedProjects.some((p) => p.id === prev.id)) {
            return loadedProjects.find((p) => p.id === prev.id) || loadedProjects[0];
          }
          return loadedProjects[0];
        });
      } else {
        setActiveProject(null);
      }
      setBackendStatus('healthy');
      setBackendError(null);
    } catch (err: unknown) {
      // Check if Tauri process has more detail
      const tauriStatus = await getTauriBackendStatus();
      const detailedError =
        tauriStatus?.error ||
        (err instanceof Error && err.message) ||
        'Failed to connect to local backend service or load projects.';

      setBackendStatus('error');
      setBackendError(detailedError);
    } finally {
      initializing.current = false;
      setIsRetrying(false);
    }
  }, []);

  useEffect(() => {
    initBackendAndProjects();
  }, [initBackendAndProjects]);

  const handleProjectCreated = (newProject: Project) => {
    setProjects((prev) => [newProject, ...prev.filter((p) => p.id !== newProject.id)]);
    setActiveProject(newProject);
    setCurrentView('workflow');
    setActiveCanvasTab('workflow');
  };

  const handleSelectProject = (project: Project) => {
    setActiveProject(project);
    setCurrentView('workflow');
    setActiveCanvasTab('workflow');
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#191919] text-neutral-100 antialiased font-sans">
      {/* Backend Actionable Error Banner / Overlay */}
      {backendStatus === 'error' && backendError && (
        <ActionableError
          error={backendError}
          onRetry={() => initBackendAndProjects(true)}
          isRetrying={isRetrying}
        />
      )}

      {/* Main Layout */}
      {backendStatus === 'checking' && projects.length === 0 ? (
        <div className="flex flex-1 items-center justify-center bg-[#191919]">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-6 w-6 animate-spin text-emerald-500" />
            <span className="text-xs text-neutral-400 font-medium">Connecting to local backend...</span>
          </div>
        </div>
      ) : (
        <>
          {/* Left Sidebar */}
          <Sidebar
            currentView={currentView}
            onSelectView={setCurrentView}
            projects={projects}
            activeProject={activeProject}
            onSelectProject={handleSelectProject}
            onOpenProjectsModal={() => setIsProjectsModalOpen(true)}
            onOpenCreateDialog={() => setIsCreateDialogOpen(true)}
          />

          {/* Center Main View */}
          <main className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
            {activeProject ? (
              <WorkflowCanvas
                project={activeProject}
                onOpenProjectsModal={() => setIsProjectsModalOpen(true)}
                selectedStage={selectedStage}
                onSelectStage={setSelectedStage}
                stageStates={media.stageStates}
                stageModes={stageModes}
                onStageModeChange={handleStageModeChange}
                onRunStage={handleRunStage}
                onRunWorkflow={handleRunWorkflow}
                isInspectorOpen={isInspectorOpen}
                activeTab={activeCanvasTab}
                onTabChange={setActiveCanvasTab}
                mediaController={media}
              />
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center canvas-dots">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#202020] border border-[#2e2e2e] text-emerald-400 mb-4 shadow-lg">
                  <Sparkles className="h-6 w-6" />
                </div>
                <h2 className="text-sm font-semibold text-neutral-100">No Project Open</h2>
                <p className="mt-1 text-xs text-neutral-400 max-w-sm">
                  Create a new project to start building your video workflow, or open an existing project from SQLite.
                </p>
                <div className="mt-5 flex items-center gap-3">
                  <Button
                    onClick={() => setIsCreateDialogOpen(true)}
                    className="gap-1.5"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Create Named Project
                  </Button>
                  {projects.length > 0 && (
                    <Button
                      variant="secondary"
                      onClick={() => setIsProjectsModalOpen(true)}
                    >
                      Open Existing ({projects.length})
                    </Button>
                  )}
                </div>
              </div>
            )}
          </main>

          {/* Right Inspector */}
          {activeProject && (
            <Inspector
              isCollapsed={!isInspectorOpen}
              onToggleCollapse={() => setIsInspectorOpen((open) => !open)}
              selectedStage={selectedStage}
              stageMode={isStageId(selectedStage) ? (stageModes[selectedStage] ?? 'auto') : 'auto'}
              onStageModeChange={(mode) => {
                if (isStageId(selectedStage)) {
                  handleStageModeChange(selectedStage, mode);
                }
              }}
              mediaController={media}
              onOpenMediaTab={(tab) => setActiveCanvasTab(tab)}
            />
          )}
        </>
      )}

      {/* Projects List Modal */}
      <ProjectListModal
        isOpen={isProjectsModalOpen}
        onClose={() => setIsProjectsModalOpen(false)}
        projects={projects}
        activeProjectId={activeProject?.id}
        onSelectProject={handleSelectProject}
        onOpenCreateDialog={() => setIsCreateDialogOpen(true)}
      />

      {/* Create Project Dialog */}
      <CreateProjectDialog
        isOpen={isCreateDialogOpen}
        onClose={() => setIsCreateDialogOpen(false)}
        onProjectCreated={handleProjectCreated}
      />
    </div>
  );
}

export default App;
