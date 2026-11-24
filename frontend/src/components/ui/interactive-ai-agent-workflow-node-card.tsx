"use client";

import { forwardRef, useId } from "react";
import type { HTMLAttributes, KeyboardEvent, MouseEvent, ReactNode } from "react";
import { cn } from "@/lib/utils";

/* ==========================================================================
   Types
   ========================================================================== */

export type NodeStatus = "idle" | "running" | "completed" | "error";

export interface AgentNodeCardProps extends Omit<HTMLAttributes<HTMLDivElement>, "title" | "children" | "onSelect"> {
  /** Name of the step, for example "Web Scraper". */
  title: ReactNode;
  subtitle?: ReactNode;
  /** Icon shown in the tile at the left of the header. */
  icon?: ReactNode;
  status?: NodeStatus;
  /** Replaces the default status text ("Idle", "Running", "Completed", "Error"). */
  statusLabel?: string;
  /** Draws the highlight ring around the card. */
  selected?: boolean;
  /** The body of the card. Use AgentNodeParam and AgentNodeToggle, or anything you like. */
  children?: ReactNode;
  /** Shown at the left of the bottom bar. */
  footer?: ReactNode;
  /** Shown in a red box when the status is "error". */
  errorMessage?: string;
  /** Called when the run button is pressed. Leave it out to hide the button. */
  onRunNode?: () => void;
  /** Called when the card is clicked, or Enter or Space is pressed on it. */
  onSelect?: () => void;
  disabled?: boolean;

  showInputPort?: boolean;
  showOutputPort?: boolean;
  inputLabel?: string;
  outputLabel?: string;
  /** Fills the port in, to show that a line is attached. */
  inputConnected?: boolean;
  outputConnected?: boolean;
  /** When given, the port becomes a button. */
  onInputPortClick?: () => void;
  onOutputPortClick?: () => void;
  /** Distance of the ports from the top of the card, in pixels. Default 36, level with the header icon. */
  portOffset?: number;
}

interface PortProps {
  side: "left" | "right";
  label: string;
  top: number;
  connected: boolean;
  onClick?: () => void;
}

// end of types


/* ==========================================================================
   Constants
   ========================================================================== */

const STATUS_STYLES: Record<NodeStatus, { label: string; chip: string; border: string }> = {
  idle: {
    label: "Idle",
    chip: "bg-muted text-muted-foreground",
    border: "border-border",
  },
  running: {
    label: "Running",
    chip: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
    border: "border-transparent",
  },
  completed: {
    label: "Completed",
    chip: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    border: "border-emerald-500/30",
  },
  error: {
    label: "Error",
    chip: "bg-rose-500/10 text-rose-600 dark:text-rose-400",
    border: "border-rose-500/40",
  },
};

// Only added to the page while a node is running. The ring and glow turn with a registered angle.
const RUNNING_CSS = `
  @property --agent-angle {
    syntax: "<angle>";
    inherits: false;
    initial-value: 0deg;
  }

  @keyframes agent-spin { to { --agent-angle: 360deg; } }
  @keyframes agent-pulse { 0%, 100% { opacity: 0.35; } 50% { opacity: 0.7; } }
  @keyframes agent-sweep {
    from { transform: translateX(-100%); }
    to { transform: translateX(350%); }
  }

  /* A thin ring of moving color along the border, cut out with a mask */
  .agent-ring {
    padding: 1.5px;
    background: conic-gradient(from var(--agent-angle), #8b5cf6, #3b82f6, #22d3ee, #8b5cf6);
    -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
    -webkit-mask-composite: xor;
    mask: linear-gradient(#000 0 0) content-box exclude, linear-gradient(#000 0 0);
    animation: agent-spin 3s linear infinite;
  }

  /* The same colors, blurred, glowing behind the card */
  .agent-glow {
    background: conic-gradient(from var(--agent-angle), #8b5cf6, #3b82f6, #22d3ee, #8b5cf6);
    filter: blur(16px);
    animation: agent-spin 3s linear infinite, agent-pulse 2.2s ease-in-out infinite;
  }

  .agent-sweep { animation: agent-sweep 1.6s ease-in-out infinite; }

  /* Reduced motion: keep the colored ring and glow, but hold them still */
  @media (prefers-reduced-motion: reduce) {
    .agent-ring, .agent-glow, .agent-sweep { animation: none; }
    .agent-glow { opacity: 0.45; }
  }
`;

// end of constants


/* ==========================================================================
   Helpers and small icons
   ========================================================================== */

function Svg({ children, size = 14 }: { children: ReactNode; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

const PlayIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M7 4.5v15l12-7.5Z" />
  </svg>
);

const RetryIcon = () => (
  <Svg size={13}>
    <path d="M21 12a9 9 0 1 1-3-6.7L21 8" />
    <path d="M21 3v5h-5" />
  </Svg>
);

const CheckIcon = () => (
  <Svg size={12}>
    <path d="M20 6 9 17l-5-5" />
  </Svg>
);

const AlertIcon = () => (
  <Svg size={12}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 8v4" />
    <path d="M12 16h.01" />
  </Svg>
);

const SpinnerIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" className="animate-spin motion-reduce:animate-none" aria-hidden="true">
    <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
    <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
  </svg>
);

// end of helpers and small icons


/* ==========================================================================
   Connection port
   ========================================================================== */

function Port({ side, label, top, connected, onClick }: PortProps) {
  const isLeft = side === "left";
  const kind = isLeft ? "Input" : "Output";

  const dot = (
    <span
      className={cn(
        "block h-3.5 w-3.5 rounded-full border-2 transition-all duration-200",
        connected ? "border-primary bg-primary" : "border-muted-foreground/50 bg-card",
        "group-hover/port:scale-150 group-hover/port:border-primary group-hover/port:bg-primary/25",
        "group-focus-visible/port:scale-150 group-focus-visible/port:border-primary group-focus-visible/port:ring-2 group-focus-visible/port:ring-primary/50"
      )}
    />
  );

  const tooltip = (
    <span
      aria-hidden="true"
      className={cn(
        "pointer-events-none absolute top-1/2 -translate-y-1/2 whitespace-nowrap rounded-md border border-border bg-popover px-2 py-1 text-[11px] font-medium text-popover-foreground opacity-0 shadow-md transition-opacity duration-150",
        "group-hover/port:opacity-100 group-focus-visible/port:opacity-100",
        isLeft ? "right-full mr-2" : "left-full ml-2"
      )}
    >
      {label}
    </span>
  );

  const position = cn("group/port absolute z-20 flex h-6 w-6 items-center justify-center rounded-full outline-none", isLeft ? "-left-3" : "-right-3");

  // Without a click handler the port is a visual marker only, so it stays out of the tab order
  if (!onClick) {
    return (
      <span className={position} style={{ top: top - 12 }} title={`${kind}: ${label}`}>
        {dot}
        {tooltip}
      </span>
    );
  }

  return (
    <button
      type="button"
      onClick={(e: MouseEvent<HTMLButtonElement>) => {
        e.stopPropagation();
        onClick();
      }}
      aria-label={`${kind} port: ${label}`}
      className={cn("nodrag nopan", position)}
      style={{ top: top - 12 }}
    >
      {dot}
      {tooltip}
    </button>
  );
}

// end of connection port


/* ==========================================================================
   AgentNodeCard
   ========================================================================== */

export const AgentNodeCard = forwardRef<HTMLDivElement, AgentNodeCardProps>(function AgentNodeCard(
  {
    title,
    subtitle,
    icon,
    status = "idle",
    statusLabel,
    selected = false,
    children,
    footer,
    errorMessage,
    onRunNode,
    onSelect,
    disabled = false,
    showInputPort = true,
    showOutputPort = true,
    inputLabel = "Input",
    outputLabel = "Output",
    inputConnected = false,
    outputConnected = false,
    onInputPortClick,
    onOutputPortClick,
    portOffset = 36,
    className,
    onClick,
    onKeyDown,
    ...rest
  },
  ref
) {
  const titleId = useId();
  const running = status === "running";
  const style = STATUS_STYLES[status];

  // What the run button says depends on where the node is
  const runLabel = running ? "Running…" : status === "completed" ? "Run again" : status === "error" ? "Retry" : "Run node";

  const handleClick = (e: MouseEvent<HTMLDivElement>) => {
    onClick?.(e);
    // Clicking a button or switch inside the card should not also select the card
    if (onSelect && !(e.target as HTMLElement).closest("button, a, input, [role='switch']")) onSelect();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    onKeyDown?.(e);
    if (onSelect && e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      onSelect();
    }
  };

  return (
    <div
      ref={ref}
      role="group"
      aria-labelledby={titleId}
      aria-roledescription="workflow node"
      data-status={status}
      data-selected={selected || undefined}
      aria-current={selected ? 'step' : undefined}
      tabIndex={onSelect ? 0 : undefined}
      {...rest}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      className={cn(
        "group relative isolate w-full rounded-2xl outline-none",
        // The selection ring
        selected && "ring-2 ring-primary ring-offset-2 ring-offset-background",
        onSelect && "cursor-pointer focus-visible:ring-2 focus-visible:ring-primary/70 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        className
      )}
    >
      {running && <style>{RUNNING_CSS}</style>}

      {/* Glow behind the card while it runs */}
      {running && <span aria-hidden="true" className="agent-glow pointer-events-none absolute -inset-1.5 -z-10 rounded-[1.4rem]" />}

      {/* The card surface */}
      <div
        className={cn(
          "relative overflow-hidden rounded-2xl border bg-card text-card-foreground shadow-sm transition-[box-shadow,border-color] duration-200 group-hover:shadow-md",
          style.border
        )}
      >
        {/* A bright streak sliding across the top edge while running */}
        {running && (
          <span aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-0 h-0.5 overflow-hidden">
            <span className="agent-sweep block h-full w-1/3 bg-gradient-to-r from-transparent via-blue-500 to-transparent" />
          </span>
        )}

        {/* Header: icon, title and live status */}
        <header className="flex items-start gap-3 px-4 pb-3 pt-4">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-muted/60 text-foreground">{icon}</span>

          <div className="min-w-0 flex-1">
            <h3 id={titleId} className="truncate text-sm font-semibold leading-5">
              {title}
            </h3>
            {subtitle && <p className="mt-0.5 truncate text-xs text-muted-foreground">{subtitle}</p>}
          </div>

          <span
            role="status"
            aria-live="polite"
            className={cn("inline-flex shrink-0 items-center gap-1.5 rounded-full px-2 py-1 text-[11px] font-medium", style.chip)}
          >
            {status === "completed" ? (
              <CheckIcon />
            ) : status === "error" ? (
              <AlertIcon />
            ) : (
              <span className="relative flex h-2 w-2" aria-hidden="true">
                {running && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-500 opacity-70 motion-reduce:animate-none" />}
                <span className={cn("relative inline-flex h-2 w-2 rounded-full", running ? "bg-blue-500" : "bg-muted-foreground/50")} />
              </span>
            )}
            {statusLabel ?? style.label}
          </span>
        </header>

        {/* Body */}
        {children && <div className="px-4 pb-4 pt-1">{children}</div>}

        {status === "error" && errorMessage && (
          <div role="alert" className="mx-4 mb-4 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs leading-relaxed text-rose-700 dark:text-rose-300">
            {errorMessage}
          </div>
        )}

        {/* Bottom bar with the run button */}
        {(footer || onRunNode) && (
          <footer className="flex items-center justify-between gap-3 border-t border-border bg-muted/30 px-4 py-2.5">
            <div className="min-w-0 text-xs text-muted-foreground">{footer}</div>

            {onRunNode && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onRunNode();
                }}
                disabled={running || disabled}
                aria-busy={running}
                className={cn(
                  "nodrag nopan inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg px-3 text-xs font-medium outline-none transition-all duration-150 focus-visible:ring-2 focus-visible:ring-primary/70 focus-visible:ring-offset-2 focus-visible:ring-offset-card active:scale-[0.97] disabled:pointer-events-none",
                  running
                    ? "bg-muted text-muted-foreground"
                    : status === "idle"
                    ? "bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50"
                    : "border border-border bg-background hover:bg-muted disabled:opacity-50"
                )}
              >
                {running ? <SpinnerIcon /> : status === "idle" ? <PlayIcon /> : <RetryIcon />}
                {runLabel}
              </button>
            )}
          </footer>
        )}
      </div>

      {/* Moving colored ring along the border while running */}
      {running && <span aria-hidden="true" className="agent-ring pointer-events-none absolute -inset-px z-10 rounded-2xl" />}

      {/* Connection ports */}
      {showInputPort && <Port side="left" label={inputLabel} top={portOffset} connected={inputConnected} onClick={onInputPortClick} />}
      {showOutputPort && <Port side="right" label={outputLabel} top={portOffset} connected={outputConnected} onClick={onOutputPortClick} />}
    </div>
  );
});

// end of AgentNodeCard


/* ==========================================================================
   Body pieces: AgentNodeParams, AgentNodeParam, AgentNodeToggle
   ========================================================================== */

/** A list of settings shown as label and value pairs. */
export function AgentNodeParams({ children }: { children: ReactNode }) {
  return <dl className="space-y-2.5">{children}</dl>;
}

export function AgentNodeParam({ label, value, mono = false }: { label: string; value: ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 text-sm">
      <dt className="shrink-0 text-muted-foreground">{label}</dt>
      <dd className={cn("min-w-0 truncate rounded-md bg-muted px-2 py-0.5 text-xs font-medium text-foreground", mono && "font-mono")}>{value}</dd>
    </div>
  );
}

/** A setting you can switch on or off. */
export function AgentNodeToggle({
  label,
  description,
  checked,
  onCheckedChange,
  disabled = false,
}: {
  label: string;
  description?: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
}) {
  const labelId = useId();

  return (
    <div className="flex items-center justify-between gap-4 pt-1">
      <div className="min-w-0">
        <p id={labelId} className="text-sm text-foreground">
          {label}
        </p>
        {description && <p className="text-xs text-muted-foreground">{description}</p>}
      </div>

      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-labelledby={labelId}
        disabled={disabled}
        onClick={(e) => {
          e.stopPropagation();
          onCheckedChange(!checked);
        }}
        className={cn(
          "nodrag nopan relative h-5 w-9 shrink-0 rounded-full outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-primary/70 focus-visible:ring-offset-2 focus-visible:ring-offset-card disabled:cursor-not-allowed disabled:opacity-50",
          checked ? "bg-primary" : "bg-muted-foreground/30"
        )}
      >
        <span
          className={cn(
            "absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-background shadow transition-transform duration-200",
            checked ? "translate-x-4" : "translate-x-0"
          )}
        />
      </button>
    </div>
  );
}

export default AgentNodeCard;

// end of body pieces
