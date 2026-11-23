import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../../lib/utils';

const badgeVariants = cva(
  'inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-semibold transition-colors focus:outline-none select-none',
  {
    variants: {
      variant: {
        default:
          'border-transparent bg-emerald-500/15 text-emerald-400 border border-emerald-500/25',
        secondary:
          'border-transparent bg-[#282828] text-neutral-300',
        destructive:
          'border-transparent bg-red-950/40 text-red-400 border border-red-800/30',
        outline:
          'border-[#2e2e2e] text-neutral-300',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
