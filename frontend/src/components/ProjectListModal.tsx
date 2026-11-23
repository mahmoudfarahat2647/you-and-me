import React, { useState } from 'react';
import { Layers, Plus, Calendar, Hash, ArrowRight, Search, Check } from 'lucide-react';
import type { Project } from '../types';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';

interface ProjectListModalProps {
  isOpen: boolean;
  onClose: () => void;
  projects: Project[];
  activeProjectId?: string | null;
  onSelectProject: (project: Project) => void;
  onOpenCreateDialog: () => void;
}

export const ProjectListModal: React.FC<ProjectListModalProps> = ({
  isOpen,
  onClose,
  projects,
  activeProjectId,
  onSelectProject,
  onOpenCreateDialog,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const filteredProjects = projects.filter((p) =>
    p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleCopyId = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <DialogHeader className="border-b border-[#2e2e2e] pb-3">
          <div className="flex items-center justify-between pr-6">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#282828] text-neutral-300">
                <Layers className="h-4 w-4" />
              </div>
              <div>
                <DialogTitle>All Projects</DialogTitle>
                <DialogDescription className="mt-0.5">
                  {projects.length} {projects.length === 1 ? 'project' : 'projects'} saved in local SQLite storage
                </DialogDescription>
              </div>
            </div>
            <Button
              size="sm"
              onClick={() => {
                onClose();
                onOpenCreateDialog();
              }}
              className="gap-1.5"
            >
              <Plus className="h-3.5 w-3.5" />
              New Project
            </Button>
          </div>
        </DialogHeader>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-neutral-500" />
          <Input
            type="text"
            placeholder="Search projects by name, description or ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9"
          />
        </div>

        {/* Project List */}
        <div className="flex-1 overflow-y-auto space-y-2 pr-1 min-h-[160px]">
          {filteredProjects.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center">
              <p className="text-xs text-neutral-400">No projects found.</p>
              <Button
                variant="link"
                size="sm"
                onClick={() => {
                  onClose();
                  onOpenCreateDialog();
                }}
                className="mt-2"
              >
                Create your first project
              </Button>
            </div>
          ) : (
            filteredProjects.map((p) => {
              const isActive = p.id === activeProjectId;
              return (
                <div
                  key={p.id}
                  onClick={() => {
                    onSelectProject(p);
                    onClose();
                  }}
                  className={`group relative flex items-center justify-between rounded-lg border p-3.5 transition-all cursor-pointer ${
                    isActive
                      ? 'border-emerald-500/40 bg-emerald-950/15'
                      : 'border-[#2e2e2e] bg-[#191919] hover:border-[#383838] hover:bg-[#222222]'
                  }`}
                >
                  <div className="flex-1 min-w-0 pr-4">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-xs text-neutral-100 truncate">
                        {p.name}
                      </span>
                      {isActive && <Badge variant="default">Active</Badge>}
                    </div>
                    {p.description && (
                      <p className="mt-1 text-[11px] text-neutral-400 truncate">
                        {p.description}
                      </p>
                    )}
                    <div className="mt-2 flex items-center gap-4 text-[11px] text-neutral-500">
                      <div
                        onClick={(e) => handleCopyId(e, p.id)}
                        className="flex items-center gap-1 hover:text-neutral-300 font-mono transition-colors"
                        title="Click to copy full ID"
                      >
                        <Hash className="h-3 w-3" />
                        <span>{p.id.slice(0, 8)}...</span>
                        {copiedId === p.id && <Check className="h-3 w-3 text-emerald-400" />}
                      </div>
                      <div className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        <span>{new Date(p.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 text-neutral-400 group-hover:text-emerald-400 transition-colors">
                    <span className="text-xs font-medium opacity-0 group-hover:opacity-100 transition-opacity">
                      Open
                    </span>
                    <ArrowRight className="h-4 w-4" />
                  </div>
                </div>
              );
            })
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
