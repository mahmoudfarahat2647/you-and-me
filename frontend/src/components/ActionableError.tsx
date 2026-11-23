import React from 'react';
import { AlertTriangle, RefreshCw, Terminal, CheckCircle2 } from 'lucide-react';
import { Button } from './ui/button';

interface ActionableErrorProps {
  error: string;
  onRetry: () => void;
  isRetrying: boolean;
}

export const ActionableError: React.FC<ActionableErrorProps> = ({
  error,
  onRetry,
  isRetrying,
}) => {
  const [copied, setCopied] = React.useState(false);
  const commandToRun = 'd:\\you-and-me\\.venv\\Scripts\\python.exe -m src.adapters.api.server --port 8000';

  const copyCommand = () => {
    navigator.clipboard.writeText(commandToRun);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#191919]/90 backdrop-blur-sm p-6">
      <div className="w-full max-w-lg rounded-xl border border-[#383838] bg-[#202020] p-6 shadow-2xl">
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-amber-500/10 text-amber-500 border border-amber-500/20">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div className="flex-1">
            <h2 className="text-base font-semibold text-neutral-100">
              Local Backend Unavailable
            </h2>
            <p className="mt-1 text-xs text-neutral-400">
              The desktop application could not connect to its local FastAPI backend.
            </p>
          </div>
        </div>

        {/* Error Detail */}
        <div className="mt-4 rounded-lg border border-[#2e2e2e] bg-[#191919] p-3 text-xs font-mono text-red-400 break-words">
          {error}
        </div>

        {/* Actionable Troubleshooting Steps */}
        <div className="mt-5 space-y-2 text-xs text-neutral-300">
          <p className="font-medium text-neutral-200">Actionable steps to resolve:</p>
          <ol className="list-decimal list-inside space-y-1 text-neutral-400 pl-1">
            <li>Ensure the Python virtual environment exists at <code className="text-neutral-200 bg-[#282828] px-1 py-0.5 rounded">.venv</code>.</li>
            <li>Verify port <code className="text-neutral-200 bg-[#282828] px-1 py-0.5 rounded">8000</code> is open and not blocked by a firewall or another service.</li>
            <li>You can manually launch the backend using the command below:</li>
          </ol>

          <div className="mt-2 flex items-center justify-between rounded border border-[#2e2e2e] bg-[#161616] px-3 py-2">
            <div className="flex items-center gap-2 text-neutral-400 overflow-hidden text-ellipsis whitespace-nowrap">
              <Terminal className="h-3.5 w-3.5 shrink-0 text-neutral-500" />
              <code className="text-[11px] text-neutral-300">{commandToRun}</code>
            </div>
            <button
              onClick={copyCommand}
              className="ml-2 shrink-0 text-[11px] font-medium text-neutral-400 hover:text-neutral-100 transition-colors"
            >
              {copied ? (
                <span className="flex items-center gap-1 text-emerald-400">
                  <CheckCircle2 className="h-3 w-3" /> Copied
                </span>
              ) : (
                'Copy'
              )}
            </button>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="mt-6 flex items-center justify-end gap-3">
          <Button
            onClick={onRetry}
            disabled={isRetrying}
            className="gap-2"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isRetrying ? 'animate-spin' : ''}`} />
            {isRetrying ? 'Checking Connection...' : 'Retry Connection'}
          </Button>
        </div>
      </div>
    </div>
  );
};
