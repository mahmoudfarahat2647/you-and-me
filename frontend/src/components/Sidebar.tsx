import React from 'react';
import {
  Clapperboard,
  Network,
  Layers,
  Tv,
  Plug,
  LayoutGrid,
  Settings,
  Clock,
  Film,
  ChevronDown,
  Plus,
} from 'lucide-react';
import type { ChannelProfile, Project } from '../types';

interface SidebarProps {
  currentView: string;
  onSelectView: (view: string) => void;
  projects: Project[];
  activeProject: Project | null;
  onSelectProject: (project: Project) => void;
  onOpenProjectsModal: () => void;
  onOpenCreateDialog: () => void;
  channels?: ChannelProfile[];
  activeChannelId?: string | null;
  onSelectActiveChannel?: (channelId: string | null) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentView,
  onSelectView,
  projects,
  activeProject,
  onSelectProject,
  onOpenProjectsModal,
  onOpenCreateDialog,
  channels = [],
  activeChannelId = null,
  onSelectActiveChannel,
}) => {
  const recentProjects = projects.slice(0, 5);

  return (
    <aside className="w-56 shrink-0 border-r border-[#2e2e2e] bg-[#202020] flex flex-col justify-between select-none">
      {/* Top Header & Main Navigation */}
      <div>
        <div className="flex items-center gap-2.5 px-4 py-4 border-b border-[#2e2e2e]">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-[#282828] text-neutral-100">
            <Clapperboard className="h-4 w-4" />
          </div>
          <span className="text-xs font-semibold text-neutral-100 tracking-tight">
            AI Video Studio
          </span>
        </div>

        {/* Navigation Items */}
        <nav className="p-2 space-y-0.5">
          <button
            onClick={() => onSelectView('workflow')}
            className={`w-full flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              currentView === 'workflow'
                ? 'bg-[#282828] text-neutral-100'
                : 'text-neutral-400 hover:text-neutral-200 hover:bg-[#252525]'
            }`}
          >
            <Network className="h-4 w-4" />
            <span>Workflow</span>
          </button>

          <button
            onClick={onOpenProjectsModal}
            className={`w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              currentView === 'projects'
                ? 'bg-[#282828] text-neutral-100'
                : 'text-neutral-400 hover:text-neutral-200 hover:bg-[#252525]'
            }`}
          >
            <div className="flex items-center gap-2.5">
              <Layers className="h-4 w-4" />
              <span>Projects</span>
            </div>
            <span className="text-[10px] bg-[#282828] px-1.5 py-0.2 rounded text-neutral-400">
              {projects.length}
            </span>
          </button>

          <button
            onClick={() => onSelectView('channels')}
            className={`w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              currentView === 'channels'
                ? 'bg-[#282828] text-neutral-100'
                : 'text-neutral-400 hover:text-neutral-200 hover:bg-[#252525]'
            }`}
          >
            <div className="flex items-center gap-2.5">
              <Tv className="h-4 w-4" />
              <span>Channels</span>
            </div>
            {channels.length > 0 && (
              <span className="text-[10px] bg-[#282828] px-1.5 py-0.2 rounded text-neutral-400">
                {channels.length}
              </span>
            )}
          </button>

          <button
            onClick={() => onSelectView('providers')}
            className="w-full flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-xs font-medium text-neutral-400 hover:text-neutral-200 hover:bg-[#252525] transition-colors"
          >
            <Plug className="h-4 w-4" />
            <span>Providers</span>
          </button>

          <button
            onClick={() => onSelectView('templates')}
            className="w-full flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-xs font-medium text-neutral-400 hover:text-neutral-200 hover:bg-[#252525] transition-colors"
          >
            <LayoutGrid className="h-4 w-4" />
            <span>Templates</span>
          </button>

          <button
            onClick={() => onSelectView('settings')}
            className="w-full flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-xs font-medium text-neutral-400 hover:text-neutral-200 hover:bg-[#252525] transition-colors"
          >
            <Settings className="h-4 w-4" />
            <span>Settings</span>
          </button>
        </nav>

        {/* Active Channel Switcher */}
        {channels.length > 0 && onSelectActiveChannel && (
          <div className="mt-2 px-3">
            <label
              htmlFor="sidebar-active-channel"
              className="block px-2 py-1 text-[11px] font-medium text-neutral-400"
            >
              Active Channel
            </label>
            <select
              id="sidebar-active-channel"
              aria-label="Active Channel"
              value={activeChannelId ?? ''}
              onChange={(e) => onSelectActiveChannel(e.target.value || null)}
              className="w-full rounded-lg border border-[#2e2e2e] bg-[#191919] px-2.5 py-1.5 text-xs text-neutral-200 focus:border-emerald-500/50 focus:outline-none"
            >
              <option value="">All Channels</option>
              {channels.map((channel) => (
                <option key={channel.id} value={channel.id}>
                  {channel.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Recent Projects Section */}
        <div className="mt-4 px-3">
          <div className="flex items-center justify-between px-2 py-1 text-neutral-400">
            <div className="flex items-center gap-1.5 text-[11px] font-medium">
              <Clock className="h-3 w-3" />
              <span>Recent Projects</span>
            </div>
            <button
              onClick={onOpenCreateDialog}
              title="Create New Project"
              className="p-0.5 hover:text-neutral-100 rounded hover:bg-[#282828] transition-colors"
            >
              <Plus className="h-3 w-3" />
            </button>
          </div>

          <div className="mt-1 space-y-0.5">
            {recentProjects.length === 0 ? (
              <div className="px-2 py-2 text-[11px] text-neutral-500 italic">
                No saved projects
              </div>
            ) : (
              recentProjects.map((p) => {
                const isSelected = activeProject?.id === p.id;
                return (
                  <button
                    key={p.id}
                    onClick={() => {
                      onSelectProject(p);
                      onSelectView('workflow');
                    }}
                    className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-xs transition-colors truncate text-left ${
                      isSelected
                        ? 'bg-[#282828] text-neutral-100 font-medium'
                        : 'text-neutral-400 hover:text-neutral-200 hover:bg-[#252525]'
                    }`}
                  >
                    <Film className={`h-3 w-3 shrink-0 ${isSelected ? 'text-emerald-400' : 'text-neutral-500'}`} />
                    <span className="truncate">{p.name}</span>
                  </button>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* User Profile at Bottom */}
      <div className="p-3 border-t border-[#2e2e2e]">
        <div className="flex items-center justify-between px-2 py-1.5 rounded-lg hover:bg-[#252525] transition-colors cursor-pointer">
          <div className="flex items-center gap-2.5">
            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-neutral-700 text-[11px] font-medium text-neutral-200">
              M
            </div>
            <span className="text-xs font-medium text-neutral-200">Mahmoud</span>
          </div>
          <ChevronDown className="h-3.5 w-3.5 text-neutral-500" />
        </div>
      </div>
    </aside>
  );
};
