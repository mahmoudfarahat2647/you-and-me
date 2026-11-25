import React, { useId, useState } from 'react';
import {
  CheckCircle2,
  FolderPlus,
  Globe,
  Mic,
  Palette,
  Plus,
  Tv,
  Upload,
  Wallet,
} from 'lucide-react';
import type {
  ChannelProfile,
  CreateChannelPayload,
  Project,
  UpdateChannelPayload,
} from '../types';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';

interface ChannelsViewProps {
  channels: ChannelProfile[];
  projects: Project[];
  activeChannelId: string | null;
  onSelectActiveChannel: (channelId: string | null) => void;
  onCreateChannel: (payload: CreateChannelPayload) => Promise<ChannelProfile>;
  onUpdateChannel?: (channelId: string, payload: UpdateChannelPayload) => Promise<ChannelProfile>;
  onSelectProject: (project: Project) => void;
  onOpenCreateProjectForChannel: (channelId: string) => void;
}

export const ChannelsView: React.FC<ChannelsViewProps> = ({
  channels,
  projects,
  activeChannelId,
  onSelectActiveChannel,
  onCreateChannel,
  onUpdateChannel,
  onSelectProject,
  onOpenCreateProjectForChannel,
}) => {
  const [name, setName] = useState('');
  const [topicFocus, setTopicFocus] = useState('');
  const [language, setLanguage] = useState('Arabic');
  const [defaultNarrator, setDefaultNarrator] = useState('arabic-narrator-v2');
  const [visualStyle, setVisualStyle] = useState('Cinematic Documentary');
  const [videoFormat, setVideoFormat] = useState('16:9');
  const [budgetLimitUsd, setBudgetLimitUsd] = useState('15');
  const [uploadDestination, setUploadDestination] = useState('YouTube');
  const [editingChannelId, setEditingChannelId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nameId = useId();
  const topicId = useId();
  const languageId = useId();
  const narratorId = useId();
  const styleId = useId();
  const formatId = useId();
  const budgetId = useId();
  const destinationId = useId();

  const resetForm = () => {
    setName('');
    setTopicFocus('');
    setLanguage('Arabic');
    setDefaultNarrator('arabic-narrator-v2');
    setVisualStyle('Cinematic Documentary');
    setVideoFormat('16:9');
    setBudgetLimitUsd('15');
    setUploadDestination('YouTube');
    setEditingChannelId(null);
    setError(null);
  };

  const startEdit = (channel: ChannelProfile) => {
    setEditingChannelId(channel.id);
    setName(channel.name);
    setTopicFocus(channel.topic_focus);
    setLanguage(channel.language);
    setDefaultNarrator(channel.default_narrator);
    setVisualStyle(channel.visual_style);
    setVideoFormat(channel.video_format);
    setBudgetLimitUsd(String(channel.budget_limit_usd));
    setUploadDestination(channel.upload_destination);
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;
    if (!name.trim()) {
      setError('Channel name is required.');
      return;
    }

    const parsedBudget = Number(budgetLimitUsd);
    if (!Number.isFinite(parsedBudget) || parsedBudget < 0) {
      setError('Budget limit must be a non-negative number.');
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const payload: CreateChannelPayload = {
        name: name.trim(),
        topic_focus: topicFocus.trim(),
        language: language.trim() || 'Arabic',
        default_narrator: defaultNarrator.trim() || 'arabic-narrator-v2',
        visual_style: visualStyle.trim() || 'Cinematic Documentary',
        video_format: videoFormat.trim() || '16:9',
        budget_limit_usd: parsedBudget,
        upload_destination: uploadDestination.trim() || 'YouTube',
      };

      if (editingChannelId && onUpdateChannel) {
        await onUpdateChannel(editingChannelId, payload);
      } else {
        const created = await onCreateChannel(payload);
        onSelectActiveChannel(created.id);
      }
      resetForm();
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : 'Failed to save channel profile.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const activeChannel = channels.find((c) => c.id === activeChannelId) ?? null;

  return (
    <div className="flex-1 overflow-y-auto bg-[#191919] p-6">
      <div className="mx-auto max-w-5xl space-y-6">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#2e2e2e] pb-4">
          <div>
            <div className="flex items-center gap-2">
              <Tv className="h-5 w-5 text-emerald-400" />
              <h1 className="text-base font-bold text-neutral-100">Channel Profiles</h1>
            </div>
            <p className="mt-1 text-xs text-neutral-400">
              Keep channel defaults isolated. New projects copy these defaults into project-specific settings without mutating the channel or sibling projects.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant={activeChannelId === null ? 'default' : 'outline'}
              size="sm"
              onClick={() => onSelectActiveChannel(null)}
            >
              All Channels ({projects.length})
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Channel List */}
          <div className="lg:col-span-7 space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-neutral-400">
              Saved Channels ({channels.length})
            </h2>

            {channels.length === 0 ? (
              <div className="rounded-xl border border-dashed border-[#2e2e2e] bg-[#202020] p-6 text-center text-xs text-neutral-400">
                No channel profiles yet. Create your first channel profile using the form to establish reusable defaults.
              </div>
            ) : (
              <div className="space-y-3">
                {channels.map((channel) => {
                  const isActive = channel.id === activeChannelId;
                  const channelProjects = projects.filter(
                    (p) => p.channel_profile_id === channel.id
                  );

                  return (
                    <div
                      key={channel.id}
                      data-testid={`channel-card-${channel.id}`}
                      className={`rounded-xl border p-4 transition-colors ${
                        isActive
                          ? 'border-emerald-500/50 bg-emerald-950/15'
                          : 'border-[#2e2e2e] bg-[#202020]'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <h3 className="text-sm font-semibold text-neutral-100 truncate">
                              {channel.name}
                            </h3>
                            {isActive && <Badge>Active Channel</Badge>}
                          </div>
                          {channel.topic_focus && (
                            <p className="mt-0.5 text-xs text-neutral-400">
                              {channel.topic_focus}
                            </p>
                          )}
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <Button
                            type="button"
                            size="sm"
                            variant={isActive ? 'secondary' : 'outline'}
                            onClick={() => onSelectActiveChannel(channel.id)}
                          >
                            {isActive ? (
                              <>
                                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                                Active
                              </>
                            ) : (
                              'Switch To Channel'
                            )}
                          </Button>
                          {onUpdateChannel && (
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => startEdit(channel)}
                            >
                              Edit
                            </Button>
                          )}
                        </div>
                      </div>

                      <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-neutral-300 sm:grid-cols-3">
                        <div className="flex items-center gap-1.5 rounded-md bg-[#191919] px-2.5 py-1.5 border border-[#2a2a2a]">
                          <Globe className="h-3 w-3 text-neutral-400 shrink-0" />
                          <span className="truncate">{channel.language}</span>
                        </div>
                        <div className="flex items-center gap-1.5 rounded-md bg-[#191919] px-2.5 py-1.5 border border-[#2a2a2a]">
                          <Mic className="h-3 w-3 text-neutral-400 shrink-0" />
                          <span className="truncate font-mono">{channel.default_narrator}</span>
                        </div>
                        <div className="flex items-center gap-1.5 rounded-md bg-[#191919] px-2.5 py-1.5 border border-[#2a2a2a]">
                          <Palette className="h-3 w-3 text-neutral-400 shrink-0" />
                          <span className="truncate">{channel.visual_style}</span>
                        </div>
                        <div className="flex items-center gap-1.5 rounded-md bg-[#191919] px-2.5 py-1.5 border border-[#2a2a2a]">
                          <span className="text-neutral-500">Fmt</span>
                          <span className="font-mono">{channel.video_format}</span>
                        </div>
                        <div className="flex items-center gap-1.5 rounded-md bg-[#191919] px-2.5 py-1.5 border border-[#2a2a2a]">
                          <Wallet className="h-3 w-3 text-neutral-400 shrink-0" />
                          <span className="font-mono">${channel.budget_limit_usd.toFixed(2)}</span>
                        </div>
                        <div className="flex items-center gap-1.5 rounded-md bg-[#191919] px-2.5 py-1.5 border border-[#2a2a2a]">
                          <Upload className="h-3 w-3 text-neutral-400 shrink-0" />
                          <span className="truncate">{channel.upload_destination}</span>
                        </div>
                      </div>

                      {/* Channel Projects */}
                      <div className="mt-3 border-t border-[#2a2a2a] pt-3 flex items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-neutral-400">
                          <span>Projects ({channelProjects.length}):</span>
                          {channelProjects.length === 0 ? (
                            <span className="italic text-neutral-500">None yet</span>
                          ) : (
                            channelProjects.map((proj) => (
                              <button
                                key={proj.id}
                                type="button"
                                onClick={() => {
                                  onSelectActiveChannel(channel.id);
                                  onSelectProject(proj);
                                }}
                                className="rounded bg-[#282828] px-2 py-0.5 text-neutral-200 hover:bg-[#323232] transition-colors"
                              >
                                {proj.name}
                              </button>
                            ))
                          )}
                        </div>
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          className="h-7 gap-1 text-[11px]"
                          onClick={() => onOpenCreateProjectForChannel(channel.id)}
                        >
                          <FolderPlus className="h-3 w-3" />
                          New Project
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {activeChannel && (
              <div className="rounded-lg border border-[#2e2e2e] bg-[#202020] px-4 py-3 text-xs text-neutral-300">
                Active Channel Filter: <span className="font-semibold text-emerald-400">{activeChannel.name}</span>
              </div>
            )}
          </div>

          {/* Create / Edit Channel Form */}
          <div className="lg:col-span-5">
            <form
              onSubmit={handleSubmit}
              className="rounded-xl border border-[#2e2e2e] bg-[#202020] p-4 space-y-3.5"
            >
              <div className="flex items-center justify-between">
                <h2 className="text-xs font-semibold text-neutral-100">
                  {editingChannelId ? 'Edit Channel Profile' : 'Create Channel Profile'}
                </h2>
                {editingChannelId && (
                  <button
                    type="button"
                    onClick={resetForm}
                    className="text-[11px] text-neutral-400 hover:text-neutral-200"
                  >
                    Cancel Edit
                  </button>
                )}
              </div>

              {error && (
                <div
                  role="alert"
                  className="rounded-md border border-red-900/50 bg-red-950/30 p-2.5 text-xs text-red-300"
                >
                  {error}
                </div>
              )}

              <div>
                <label htmlFor={nameId} className="block text-[11px] font-medium text-neutral-300 mb-1">
                  Channel Name <span className="text-red-400">*</span>
                </label>
                <Input
                  id={nameId}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. History Deep Dives"
                />
              </div>

              <div>
                <label htmlFor={topicId} className="block text-[11px] font-medium text-neutral-300 mb-1">
                  Topic Focus
                </label>
                <Input
                  id={topicId}
                  value={topicFocus}
                  onChange={(e) => setTopicFocus(e.target.value)}
                  placeholder="e.g. Ancient civilizations & archaeology"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor={languageId} className="block text-[11px] font-medium text-neutral-300 mb-1">
                    Language
                  </label>
                  <Input
                    id={languageId}
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    placeholder="Arabic"
                  />
                </div>
                <div>
                  <label htmlFor={formatId} className="block text-[11px] font-medium text-neutral-300 mb-1">
                    Video Format
                  </label>
                  <select
                    id={formatId}
                    value={videoFormat}
                    onChange={(e) => setVideoFormat(e.target.value)}
                    className="w-full rounded-lg border border-[#2e2e2e] bg-[#191919] px-3 py-2 text-xs text-neutral-100 focus:border-emerald-500/50 focus:outline-none"
                  >
                    <option value="16:9">16:9 (Landscape)</option>
                    <option value="9:16">9:16 (Shorts / Vertical)</option>
                    <option value="1:1">1:1 (Square)</option>
                  </select>
                </div>
              </div>

              <div>
                <label htmlFor={narratorId} className="block text-[11px] font-medium text-neutral-300 mb-1">
                  Default Narrator
                </label>
                <Input
                  id={narratorId}
                  value={defaultNarrator}
                  onChange={(e) => setDefaultNarrator(e.target.value)}
                  placeholder="arabic-narrator-v2"
                />
              </div>

              <div>
                <label htmlFor={styleId} className="block text-[11px] font-medium text-neutral-300 mb-1">
                  Visual Style
                </label>
                <Input
                  id={styleId}
                  value={visualStyle}
                  onChange={(e) => setVisualStyle(e.target.value)}
                  placeholder="Cinematic Documentary"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor={budgetId} className="block text-[11px] font-medium text-neutral-300 mb-1">
                    Budget Limit (USD)
                  </label>
                  <Input
                    id={budgetId}
                    type="number"
                    min="0"
                    step="0.5"
                    value={budgetLimitUsd}
                    onChange={(e) => setBudgetLimitUsd(e.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor={destinationId} className="block text-[11px] font-medium text-neutral-300 mb-1">
                    Upload Destination
                  </label>
                  <Input
                    id={destinationId}
                    value={uploadDestination}
                    onChange={(e) => setUploadDestination(e.target.value)}
                    placeholder="YouTube"
                  />
                </div>
              </div>

              <Button type="submit" disabled={isSubmitting || !name.trim()} className="w-full gap-1.5">
                <Plus className="h-3.5 w-3.5" />
                {editingChannelId ? 'Save Channel Changes' : 'Create Channel Profile'}
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};
