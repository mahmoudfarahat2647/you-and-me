import React, { useState } from 'react';
import {
  Play,
  MoreHorizontal,
  Lightbulb,
  FileText,
  Mic,
  Image as ImageIcon,
  Film,
  Upload,
  CheckCircle2,
  MousePointer,
  Hand,
  Maximize2,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import type { Project } from '../types';
import { Button } from './ui/button';

interface WorkflowCanvasProps {
  project: Project;
  onOpenProjectsModal: () => void;
  selectedStage: string;
  onSelectStage: (stage: string) => void;
}

export const WorkflowCanvas: React.FC<WorkflowCanvasProps> = ({
  project,
  onOpenProjectsModal,
  selectedStage,
  onSelectStage,
}) => {
  const [activeTab, setActiveTab] = useState<'workflow' | 'assets' | 'output' | 'logs'>('workflow');
  const [zoom, setZoom] = useState(100);

  const stages = [
    { id: 'idea', label: 'Idea', icon: Lightbulb, status: 'completed' },
    { id: 'script', label: 'Script', icon: FileText, status: 'in_progress' },
    { id: 'voice', label: 'Voice', icon: Mic, status: 'pending' },
    { id: 'scenes', label: 'Scenes', icon: ImageIcon, status: 'pending' },
    { id: 'edit', label: 'Edit', icon: Film, status: 'pending' },
    { id: 'export', label: 'Export', icon: Upload, status: 'pending' },
  ];

  return (
    <div className="flex-1 flex flex-col bg-[#191919] select-none min-w-0 overflow-hidden">
      {/* Top Header Bar */}
      <div className="border-b border-[#2e2e2e] bg-[#191919] px-6 pt-3.5 pb-0">
        {/* Breadcrumb */}
        <div className="flex items-center gap-1 text-[11px] text-neutral-400">
          <button
            onClick={onOpenProjectsModal}
            className="hover:text-neutral-200 transition-colors"
          >
            〈Projects
          </button>
          <span>/</span>
          <span className="text-neutral-300 font-medium truncate">{project.name}</span>
        </div>

        {/* Project Title and Run Button */}
        <div className="mt-2 flex items-center justify-between pb-3">
          <div className="flex items-center gap-3">
            <h1 className="text-base font-bold text-neutral-100 truncate">
              {project.name}
            </h1>
            <Button variant="ghost" size="icon" className="text-neutral-400">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </div>

          <Button variant="workflow" className="gap-2">
            <Play className="h-3 w-3 fill-emerald-400" />
            <span>Run Workflow</span>
          </Button>
        </div>

        {/* Header Tabs */}
        <div className="flex items-center gap-6 text-xs border-t border-[#252525]">
          {(['workflow', 'assets', 'output', 'logs'] as const).map((tab) => {
            const isActive = activeTab === tab;
            return (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`py-2 font-medium capitalize transition-colors relative ${
                  isActive
                    ? 'text-neutral-100'
                    : 'text-neutral-400 hover:text-neutral-200'
                }`}
              >
                {tab}
                {isActive && (
                  <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-neutral-100" />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Canvas View */}
      <div className="flex-1 relative overflow-hidden canvas-dots flex items-center justify-center p-8">
        {/* Connected Stages */}
        <div className="flex items-center gap-3 max-w-full overflow-x-auto p-4">
          {stages.map((stage, idx) => {
            const isSelected = selectedStage === stage.id;
            const Icon = stage.icon;

            return (
              <React.Fragment key={stage.id}>
                {/* Stage Node Box */}
                <div
                  onClick={() => onSelectStage(stage.id)}
                  className={`relative flex flex-col items-center justify-center w-20 h-24 rounded-xl border transition-all cursor-pointer ${
                    isSelected
                      ? 'border-emerald-500/80 bg-[#202020] shadow-[0_0_15px_rgba(16,185,129,0.15)] ring-1 ring-emerald-500/50'
                      : 'border-[#2e2e2e] bg-[#202020] hover:border-[#3a3a3a] hover:bg-[#242424]'
                  }`}
                >
                  {/* Status Badge */}
                  {stage.status === 'completed' && (
                    <div className="absolute top-1.5 right-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400">
                      <CheckCircle2 className="h-3 w-3" />
                    </div>
                  )}
                  {stage.status === 'in_progress' && (
                    <div className="absolute top-1.5 right-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400">
                      <Play className="h-2.5 w-2.5 fill-emerald-400" />
                    </div>
                  )}

                  <div className={`mt-1 p-2 rounded-lg ${isSelected ? 'text-emerald-400' : 'text-neutral-300'}`}>
                    <Icon className="h-6 w-6 stroke-[1.75]" />
                  </div>
                  <span className="mt-1 text-xs font-medium text-neutral-200">
                    {stage.label}
                  </span>
                </div>

                {/* Connecting arrow */}
                {idx < stages.length - 1 && (
                  <div className="flex items-center text-neutral-600 px-0.5">
                    <svg width="20" height="12" viewBox="0 0 20 12" fill="none" className="stroke-current">
                      <path d="M0 6H16M16 6L11 1M16 6L11 11" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>

        {/* Floating Bottom Canvas Toolbar */}
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-1 rounded-xl border border-[#2e2e2e] bg-[#202020]/95 px-2 py-1.5 shadow-xl backdrop-blur-xs text-neutral-400">
          <Button variant="ghost" size="icon" className="h-6 w-6">
            <MousePointer className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="icon" className="h-6 w-6">
            <Hand className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="icon" className="h-6 w-6">
            <Maximize2 className="h-3.5 w-3.5" />
          </Button>
          <div className="h-4 w-[1px] bg-[#2e2e2e] mx-1" />
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={() => setZoom(Math.max(25, zoom - 10))}
          >
            <ZoomOut className="h-3.5 w-3.5" />
          </Button>
          <span className="px-1 text-[11px] font-mono text-neutral-300 min-w-[3.5rem] text-center">
            {zoom}%
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={() => setZoom(Math.min(200, zoom + 10))}
          >
            <ZoomIn className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
};
