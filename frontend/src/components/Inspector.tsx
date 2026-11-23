import React, { useState } from 'react';
import {
  FileText,
  X,
  Zap,
  Edit3,
  UserCheck,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';

interface InspectorProps {
  onClose?: () => void;
}

export const Inspector: React.FC<InspectorProps> = ({ onClose }) => {
  const [activeTab, setActiveTab] = useState<'settings' | 'output' | 'logs'>('settings');
  const [mode, setMode] = useState<'auto' | 'manual' | 'approval'>('auto');
  const [provider, setProvider] = useState('ChatGPT');
  const [model, setModel] = useState('GPT-4o');
  const [scriptLength, setScriptLength] = useState('~ 8 minutes');
  const [advancedOpen, setAdvancedOpen] = useState(false);

  return (
    <aside className="w-72 shrink-0 border-l border-[#2e2e2e] bg-[#202020] flex flex-col justify-between select-none">
      <div className="flex-1 overflow-y-auto">
        {/* Header */}
        <div className="flex items-start justify-between p-4 border-b border-[#2e2e2e]">
          <div className="flex items-start gap-2.5">
            <div className="mt-0.5 text-neutral-300">
              <FileText className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-xs font-semibold text-neutral-100">Script</h3>
              <p className="text-[11px] text-neutral-400 mt-0.5">
                Generate or edit the video script.
              </p>
            </div>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="text-neutral-400 hover:text-neutral-200 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Sub-tabs: Settings / Output / Logs */}
        <div className="flex items-center px-4 border-b border-[#2e2e2e] text-xs">
          {(['settings', 'output', 'logs'] as const).map((tab) => {
            const isActive = activeTab === tab;
            return (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`py-2 px-2.5 font-medium capitalize transition-colors relative ${
                  isActive
                    ? 'text-neutral-100'
                    : 'text-neutral-400 hover:text-neutral-200'
                }`}
              >
                {tab}
                {isActive && (
                  <span className="absolute bottom-0 left-0 right-0 h-[1.5px] bg-neutral-100" />
                )}
              </button>
            );
          })}
        </div>

        {/* Tab Content */}
        {activeTab === 'settings' && (
          <div className="p-4 space-y-4">
            {/* Mode selection */}
            <div>
              <label className="block text-[11px] font-medium text-neutral-400 mb-1.5">
                Mode
              </label>
              <div className="grid grid-cols-3 gap-1 rounded-lg border border-[#2e2e2e] bg-[#191919] p-0.5">
                <button
                  type="button"
                  onClick={() => setMode('auto')}
                  className={`flex items-center justify-center gap-1.5 py-1 px-1.5 rounded-md text-[11px] font-medium transition-all ${
                    mode === 'auto'
                      ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-500/30'
                      : 'text-neutral-400 hover:text-neutral-200'
                  }`}
                >
                  <Zap className="h-3 w-3" />
                  Auto
                </button>
                <button
                  type="button"
                  onClick={() => setMode('manual')}
                  className={`flex items-center justify-center gap-1.5 py-1 px-1.5 rounded-md text-[11px] font-medium transition-all ${
                    mode === 'manual'
                      ? 'bg-[#282828] text-neutral-100 border border-[#383838]'
                      : 'text-neutral-400 hover:text-neutral-200'
                  }`}
                >
                  <Edit3 className="h-3 w-3" />
                  Manual
                </button>
                <button
                  type="button"
                  onClick={() => setMode('approval')}
                  className={`flex items-center justify-center gap-1.5 py-1 px-1.5 rounded-md text-[11px] font-medium transition-all ${
                    mode === 'approval'
                      ? 'bg-[#282828] text-neutral-100 border border-[#383838]'
                      : 'text-neutral-400 hover:text-neutral-200'
                  }`}
                >
                  <UserCheck className="h-3 w-3" />
                  Approval
                </button>
              </div>
            </div>

            {/* Provider */}
            <div>
              <label className="block text-[11px] font-medium text-neutral-400 mb-1.5">
                Provider
              </label>
              <div className="relative">
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  className="w-full appearance-none rounded-lg border border-[#2e2e2e] bg-[#191919] px-3 py-2 text-xs text-neutral-100 focus:border-emerald-500/50 focus:outline-none transition-colors pr-8 cursor-pointer"
                >
                  <option value="ChatGPT">ChatGPT</option>
                  <option value="Claude">Claude</option>
                  <option value="Gemini">Gemini</option>
                  <option value="Local">Local Ollama</option>
                </select>
                <ChevronDown className="absolute right-3 top-2.5 h-3.5 w-3.5 text-neutral-400 pointer-events-none" />
              </div>
            </div>

            {/* Model */}
            <div>
              <label className="block text-[11px] font-medium text-neutral-400 mb-1.5">
                Model
              </label>
              <div className="relative">
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="w-full appearance-none rounded-lg border border-[#2e2e2e] bg-[#191919] px-3 py-2 text-xs text-neutral-100 focus:border-emerald-500/50 focus:outline-none transition-colors pr-8 cursor-pointer"
                >
                  <option value="GPT-4o">GPT-4o</option>
                  <option value="GPT-4o-mini">GPT-4o-mini</option>
                  <option value="Claude-3-5-Sonnet">Claude 3.5 Sonnet</option>
                  <option value="Gemini-2.0-Flash">Gemini 2.0 Flash</option>
                </select>
                <ChevronDown className="absolute right-3 top-2.5 h-3.5 w-3.5 text-neutral-400 pointer-events-none" />
              </div>
            </div>

            {/* Script Length */}
            <div>
              <label className="block text-[11px] font-medium text-neutral-400 mb-1.5">
                Script Length
              </label>
              <div className="relative">
                <select
                  value={scriptLength}
                  onChange={(e) => setScriptLength(e.target.value)}
                  className="w-full appearance-none rounded-lg border border-[#2e2e2e] bg-[#191919] px-3 py-2 text-xs text-neutral-100 focus:border-emerald-500/50 focus:outline-none transition-colors pr-8 cursor-pointer"
                >
                  <option value="~ 1 minute (Short)">~ 1 minute (Short)</option>
                  <option value="~ 3 minutes">~ 3 minutes</option>
                  <option value="~ 5 minutes">~ 5 minutes</option>
                  <option value="~ 8 minutes">~ 8 minutes</option>
                  <option value="~ 12 minutes">~ 12 minutes</option>
                </select>
                <ChevronDown className="absolute right-3 top-2.5 h-3.5 w-3.5 text-neutral-400 pointer-events-none" />
              </div>
            </div>

            {/* Advanced Options Accordion */}
            <div className="pt-2 border-t border-[#2e2e2e]">
              <button
                type="button"
                onClick={() => setAdvancedOpen(!advancedOpen)}
                className="w-full flex items-center justify-between text-[11px] font-medium text-neutral-400 hover:text-neutral-200 transition-colors py-1"
              >
                <span>Advanced Options</span>
                {advancedOpen ? (
                  <ChevronDown className="h-3.5 w-3.5" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5" />
                )}
              </button>

              {advancedOpen && (
                <div className="mt-2 space-y-2 text-[11px] text-neutral-400 bg-[#191919] p-2.5 rounded-lg border border-[#2e2e2e]">
                  <div>
                    <label className="block mb-1 text-neutral-500">Tone & Audience</label>
                    <input
                      type="text"
                      defaultValue="Educational Arabic with historical narrative"
                      className="w-full bg-[#202020] border border-[#2e2e2e] rounded px-2 py-1 text-xs text-neutral-200"
                    />
                  </div>
                  <div>
                    <label className="block mb-1 text-neutral-500">Temperature</label>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      defaultValue="0.7"
                      className="w-full accent-emerald-500"
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'output' && (
          <div className="p-4 text-xs text-neutral-400">
            <p className="italic text-neutral-500">No output generated yet for this stage.</p>
          </div>
        )}

        {activeTab === 'logs' && (
          <div className="p-4 text-xs font-mono text-neutral-400">
            <p className="text-neutral-500">[00:00:00] Stage initialized in Auto mode.</p>
          </div>
        )}
      </div>
    </aside>
  );
};
