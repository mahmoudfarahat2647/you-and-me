import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
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
            <li>Confirm the backend dependencies are installed for this application.</li>
            <li>Make sure no firewall or security tool is blocking the local backend.</li>
            <li>Use Retry Connection to restart the backend and check again.</li>
          </ol>
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
