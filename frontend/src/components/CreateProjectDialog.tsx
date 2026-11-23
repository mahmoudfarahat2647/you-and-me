import React, { useId, useRef, useState } from 'react';
import { FolderPlus, Loader2 } from 'lucide-react';
import { createProject } from '../api/client';
import type { Project } from '../types';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';

interface CreateProjectDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onProjectCreated: (project: Project) => void;
}

export const CreateProjectDialog: React.FC<CreateProjectDialogProps> = ({
  isOpen,
  onClose,
  onProjectCreated,
}) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nameId = useId();
  const descriptionId = useId();
  const submitting = useRef(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting.current) return;
    if (!name.trim()) {
      setError('Project name is required.');
      return;
    }

    submitting.current = true;
    setIsSubmitting(true);
    setError(null);

    try {
      const newProject = await createProject({
        name: name.trim(),
        description: description.trim(),
      });
      setName('');
      setDescription('');
      onProjectCreated(newProject);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : 'Failed to create project.');
    } finally {
      submitting.current = false;
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <FolderPlus className="h-4 w-4 text-emerald-400" />
            <DialogTitle>Create New Project</DialogTitle>
          </div>
          <DialogDescription>
            Enter a project name to start your video production workflow. Persisted locally in SQLite.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div role="alert" className="rounded-md border border-red-900/50 bg-red-950/30 p-2.5 text-xs text-red-300">
              {error}
            </div>
          )}

          <div>
            <label htmlFor={nameId} className="block text-xs font-medium text-neutral-300 mb-1.5">
              Project Name <span className="text-red-400">*</span>
            </label>
            <Input
              id={nameId}
              type="text"
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. The Pyramids Mystery"
            />
          </div>

          <div>
            <label htmlFor={descriptionId} className="block text-xs font-medium text-neutral-300 mb-1.5">
              Description <span className="text-neutral-500">(Optional)</span>
            </label>
            <textarea
              id={descriptionId}
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief overview or topic notes..."
              className="w-full rounded-lg border border-[#2e2e2e] bg-[#191919] px-3 py-2 text-xs text-neutral-100 placeholder-neutral-500 focus:border-emerald-500/50 focus:outline-none transition-colors resize-none"
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting || !name.trim()}
            >
              {isSubmitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Create Project
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
