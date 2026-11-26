import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Sidebar } from './components/Sidebar';
import { WorkflowCanvas, type WorkspaceTab } from './components/WorkflowCanvas';
import { Inspector } from './components/Inspector';
import { ProjectListModal } from './components/ProjectListModal';
import { CreateProjectDialog } from './components/CreateProjectDialog';
import { ChannelsView } from './components/ChannelsView';
import { ProvidersView } from './components/ProvidersView';
import { BudgetPreflightBanner } from './components/BudgetPreflightBanner';
import { ActionableError } from './components/ActionableError';
import {
  checkBackendHealth,
  createChannel,
  createProjectAsset,
  deleteProjectAsset,
  getProjectSettings,
  getTauriBackendStatus,
  listChannels,
  listPresets,
  listProjectAssets,
  listProjects,
  restartTauriBackend,
  updateChannel,
  updateProjectSettings,
} from './api/client';
import { useProjectMedia } from './hooks/useProjectMedia';
import { useProjectWorkflow } from './hooks/useProjectWorkflow';
import { useProjectProviders } from './hooks/useProjectProviders';
import { isStageId } from './lib/workflow/stages';
import type {
  ChannelProfile,
  CreateChannelPayload,
  CreateProjectAssetPayload,
  Project,
  ProjectAsset,
  ProjectSettings,
  StageExecutionMode,
  StageId,
  UpdateChannelPayload,
  UpdateProjectSettingsPayload,
  WorkflowPreset,
} from './types';
import { Loader2, Plus, Sparkles } from 'lucide-react';
import { Button } from './components/ui/button';

export function App() {
  const [backendStatus, setBackendStatus] = useState<'checking' | 'healthy' | 'error'>('checking');
  const [backendError, setBackendError] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const initializing = useRef(false);

  const [projects, setProjects] = useState<Project[]>([]);
  const [channels, setChannels] = useState<ChannelProfile[]>([]);
  const [presets, setPresets] = useState<WorkflowPreset[]>([]);
  const [activeChannelId, setActiveChannelId] = useState<string | null>(null);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [activeProjectSettings, setActiveProjectSettings] = useState<ProjectSettings | null>(null);
  const [activeProjectAssets, setActiveProjectAssets] = useState<ProjectAsset[]>([]);
  const [currentView, setCurrentView] = useState('workflow');

  const [isProjectsModalOpen, setIsProjectsModalOpen] = useState(false);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [createDialogChannelId, setCreateDialogChannelId] = useState<string | null>(null);
  const [isInspectorOpen, setIsInspectorOpen] = useState(true);
  const [selectedStage, setSelectedStage] = useState('script');
  const [activeCanvasTab, setActiveCanvasTab] = useState<WorkspaceTab>('workflow');
  const media = useProjectMedia(activeProject?.id);
  const workflow = useProjectWorkflow(activeProject?.id, { onExportMayHaveChanged: media.refresh });
  const { setStageMode } = workflow;
  const providerSettings = useProjectProviders(
    backendStatus === 'healthy', currentView === 'providers' ? activeProject?.id : undefined
  );
  const budgetBlock = workflow.job?.budget_block;
  const actionStage = workflow.job?.stages.find((stage) =>
    stage.status === 'waiting_manual' || stage.status === 'awaiting_approval'
  )?.stage_id;

  useEffect(() => {
    if (actionStage) {
      setSelectedStage(actionStage);
      setIsInspectorOpen(true);
    }
  }, [workflow.job?.id, actionStage]);

  const activeProjectIdRef = useRef<string | null>(null);

  const visibleProjects = useMemo(() => {
    if (!activeChannelId) return projects;
    return projects.filter((p) => p.channel_profile_id === activeChannelId);
  }, [projects, activeChannelId]);

  const activeChannel = useMemo(
    () => channels.find((c) => c.id === (activeProject?.channel_profile_id ?? activeChannelId)) ?? null,
    [channels, activeProject, activeChannelId]
  );

  const loadProjectContext = useCallback(async (projectId: string | null) => {
    activeProjectIdRef.current = projectId;
    setActiveProjectSettings(null);
    setActiveProjectAssets([]);
    if (!projectId) return;

    try {
      const [settings, assets] = await Promise.all([
        getProjectSettings(projectId),
        listProjectAssets(projectId),
      ]);
      if (activeProjectIdRef.current !== projectId) return;
      setActiveProjectSettings(settings ?? null);
      setActiveProjectAssets(Array.isArray(assets) ? assets : []);
    } catch (err) {
      console.warn('Could not load project settings/assets:', err);
    }
  }, []);

  useEffect(() => {
    void loadProjectContext(activeProject?.id ?? null);
  }, [activeProject?.id, loadProjectContext]);

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
      await checkBackendHealth();
      const loadedProjects = await listProjects();
      const [loadedChannels, loadedPresets] = await Promise.all([
        listChannels(),
        listPresets(),
      ]);

      setProjects(loadedProjects);
      setChannels(loadedChannels);
      setPresets(loadedPresets);

      if (loadedProjects.length > 0) {
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

  const handleSelectActiveChannel = useCallback(
    (channelId: string | null) => {
      setActiveChannelId(channelId);
      const matching = channelId
        ? projects.filter((p) => p.channel_profile_id === channelId)
        : projects;
      setActiveProject((prev) => {
        if (prev && matching.some((p) => p.id === prev.id)) {
          return prev;
        }
        return matching[0] ?? null;
      });
    },
    [projects]
  );

  const handleCreateChannel = useCallback(async (payload: CreateChannelPayload) => {
    const created = await createChannel(payload);
    setChannels((prev) => [created, ...prev]);
    return created;
  }, []);

  const handleUpdateChannel = useCallback(
    async (channelId: string, payload: UpdateChannelPayload) => {
      const updated = await updateChannel(channelId, payload);
      setChannels((prev) => prev.map((c) => (c.id === channelId ? updated : c)));
      return updated;
    },
    []
  );

  const handleProjectCreated = (newProject: Project) => {
    setProjects((prev) => [newProject, ...prev.filter((p) => p.id !== newProject.id)]);
    if (activeChannelId && newProject.channel_profile_id !== activeChannelId) {
      setActiveChannelId(newProject.channel_profile_id ?? null);
    }
    setActiveProject(newProject);
    setCurrentView('workflow');
    setActiveCanvasTab('workflow');
  };

  const handleSelectProject = (project: Project) => {
    setActiveProject(project);
    setCurrentView('workflow');
    setActiveCanvasTab('workflow');
  };

  const handleUpdateProjectSettings = useCallback(
    async (patch: UpdateProjectSettingsPayload) => {
      if (!activeProject) return;
      const targetProjectId = activeProject.id;
      const updated = await updateProjectSettings(targetProjectId, patch);
      if (activeProjectIdRef.current === targetProjectId) {
        setActiveProjectSettings(updated);
      }
    },
    [activeProject]
  );

  const handleStageModeChange = useCallback(
    async (stage: StageId, mode: StageExecutionMode) => {
      if (!activeProject) return;
      const targetProjectId = activeProject.id;
      const result = await setStageMode(stage, mode);
      if (result && activeProjectIdRef.current === targetProjectId) {
        setActiveProjectSettings((prev) =>
          prev && prev.project_id === targetProjectId
            ? {
                ...prev,
                stage_modes: { ...prev.stage_modes, [stage]: mode },
              }
            : prev
        );
      }
      return result;
    },
    [activeProject, setStageMode]
  );

  const handleCreateAsset = useCallback(
    async (payload: CreateProjectAssetPayload) => {
      if (!activeProject) return;
      const targetProjectId = activeProject.id;
      const created = await createProjectAsset(targetProjectId, payload);
      if (activeProjectIdRef.current === targetProjectId) {
        setActiveProjectAssets((prev) => [...prev, created]);
      }
    },
    [activeProject]
  );

  const handleDeleteAsset = useCallback(
    async (assetId: string) => {
      if (!activeProject) return;
      const targetProjectId = activeProject.id;
      await deleteProjectAsset(targetProjectId, assetId);
      if (activeProjectIdRef.current === targetProjectId) {
        setActiveProjectAssets((prev) => prev.filter((a) => a.id !== assetId));
      }
    },
    [activeProject]
  );

  const openCreateDialog = (channelIdOverride?: string | null) => {
    setCreateDialogChannelId(
      channelIdOverride !== undefined ? channelIdOverride : activeChannelId
    );
    setIsCreateDialogOpen(true);
  };

  const stageModes = activeProjectSettings?.stage_modes;

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
            projects={visibleProjects}
            activeProject={activeProject}
            onSelectProject={handleSelectProject}
            onOpenProjectsModal={() => setIsProjectsModalOpen(true)}
            onOpenCreateDialog={() => openCreateDialog()}
            channels={channels}
            activeChannelId={activeChannelId}
            onSelectActiveChannel={handleSelectActiveChannel}
          />

          {/* Center Main View */}
          <main className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
            {currentView === 'channels' ? (
              <ChannelsView
                channels={channels}
                projects={projects}
                activeChannelId={activeChannelId}
                onSelectActiveChannel={handleSelectActiveChannel}
                onCreateChannel={handleCreateChannel}
                onUpdateChannel={handleUpdateChannel}
                onSelectProject={handleSelectProject}
                onOpenCreateProjectForChannel={(channelId) => openCreateDialog(channelId)}
              />
            ) : currentView === 'providers' ? (
              <ProvidersView
                key={activeProject?.id ?? 'providers'}
                providers={providerSettings.providers}
                activeProjectId={activeProject?.id}
                projectBudget={providerSettings.ledger?.budget}
                spendLedger={providerSettings.ledger}
                loadError={providerSettings.error}
                onConfigureProvider={providerSettings.configure}
                onTestProvider={providerSettings.test}
                onSelectModel={providerSettings.selectModel}
                onDeleteProvider={providerSettings.remove}
                onUpdateProjectBudget={providerSettings.updateBudget}
                onReconcileRequest={providerSettings.reconcile}
              />
            ) : activeProject ? (
              <>
                {budgetBlock && (
                  <div className="px-6 pt-3">
                    <BudgetPreflightBanner
                      budget={null}
                      preflight={budgetBlock.preflight}
                      isBusy={workflow.isSubmitting || workflow.isStopping}
                      onApproveOverrun={(preflight) => void workflow.resume(preflight.request_key)}
                      onSwitchToManual={async () => {
                        if (!(await handleStageModeChange(budgetBlock.stage_id, 'manual'))) return;
                        setSelectedStage(budgetBlock.stage_id);
                        setIsInspectorOpen(true);
                      }}
                    />
                  </div>
                )}
                <WorkflowCanvas
                  key={activeProject.id}
                  project={activeProject}
                  onOpenProjectsModal={() => setIsProjectsModalOpen(true)}
                  selectedStage={selectedStage}
                  onSelectStage={setSelectedStage}
                  stageStates={media.stageStates}
                  stageModes={stageModes}
                  onStageModeChange={handleStageModeChange}
                  isInspectorOpen={isInspectorOpen}
                  projectSettings={activeProjectSettings}
                  projectAssets={activeProjectAssets}
                  onCreateAsset={handleCreateAsset}
                  onDeleteAsset={handleDeleteAsset}
                  activeChannel={activeChannel}
                  activeTab={activeCanvasTab}
                  onTabChange={setActiveCanvasTab}
                  mediaController={media}
                  workflowController={workflow}
                  providers={providerSettings.providers}
                />
              </>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center canvas-dots">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#202020] border border-[#2e2e2e] text-emerald-400 mb-4 shadow-lg">
                  <Sparkles className="h-6 w-6" />
                </div>
                <h2 className="text-sm font-semibold text-neutral-100">No Project Open</h2>
                <p className="mt-1 text-xs text-neutral-400 max-w-sm">
                  {activeChannelId
                    ? 'No projects in this channel yet. Create a project to inherit this channel profile.'
                    : 'Create a new project to start building your video workflow, or open an existing project from SQLite.'}
                </p>
                <div className="mt-5 flex items-center gap-3">
                  <Button
                    onClick={() => openCreateDialog()}
                    className="gap-1.5"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Create Named Project
                  </Button>
                  {visibleProjects.length > 0 && (
                    <Button
                      variant="secondary"
                      onClick={() => setIsProjectsModalOpen(true)}
                    >
                      Open Existing ({visibleProjects.length})
                    </Button>
                  )}
                </div>
              </div>
            )}
          </main>

          {/* Right Inspector */}
          {currentView !== 'channels' && currentView !== 'providers' && activeProject && (
            <Inspector
              key={activeProject.id}
              isCollapsed={!isInspectorOpen}
              onToggleCollapse={() => setIsInspectorOpen((open) => !open)}
              selectedStage={selectedStage}
              stageMode={isStageId(selectedStage)
                ? workflow.stageStates?.[selectedStage]?.mode ?? stageModes?.[selectedStage] ?? 'auto'
                : 'auto'}
              onStageModeChange={(mode) => {
                if (isStageId(selectedStage)) {
                  handleStageModeChange(selectedStage, mode);
                }
              }}
              project={activeProject}
              projectSettings={activeProjectSettings}
              onUpdateSettings={handleUpdateProjectSettings}
              projectAssets={activeProjectAssets}
              mediaController={media}
              workflowController={workflow}
              providers={providerSettings.providers}
              onOpenMediaTab={(tab) => setActiveCanvasTab(tab)}
            />
          )}
        </>
      )}

      {/* Projects List Modal */}
      <ProjectListModal
        isOpen={isProjectsModalOpen}
        onClose={() => setIsProjectsModalOpen(false)}
        projects={visibleProjects}
        activeProjectId={activeProject?.id}
        onSelectProject={handleSelectProject}
        onOpenCreateDialog={() => openCreateDialog()}
      />

      {/* Create Project Dialog */}
      <CreateProjectDialog
        isOpen={isCreateDialogOpen}
        onClose={() => setIsCreateDialogOpen(false)}
        onProjectCreated={handleProjectCreated}
        channels={channels}
        presets={presets}
        defaultChannelId={createDialogChannelId}
      />
    </div>
  );
}

export default App;
