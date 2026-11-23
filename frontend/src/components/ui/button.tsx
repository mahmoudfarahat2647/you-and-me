import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../../lib/utils';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-emerald-500 disabled:pointer-events-none disabled:opacity-50 select-none',
  {
    variants: {
      variant: {
        default:
          'bg-emerald-600 text-white shadow-xs hover:bg-emerald-500',
        destructive:
          'bg-red-900/40 text-red-300 border border-red-800/50 hover:bg-red-900/60',
        outline:
          'border border-[#2e2e2e] bg-transparent text-neutral-200 hover:bg-[#282828] hover:text-white',
        secondary:
          'bg-[#282828] text-neutral-200 hover:bg-[#323232] hover:text-white',
        ghost:
          'text-neutral-400 hover:bg-[#282828] hover:text-neutral-100',
        link:
          'text-emerald-400 underline-offset-4 hover:underline',
        workflow:
          'rounded-full border border-emerald-500/30 bg-emerald-950/20 px-3.5 py-1.5 text-emerald-400 hover:bg-emerald-950/40 hover:border-emerald-500/50 shadow-xs',
      },
      size: {
        default: 'h-8 px-3.5 py-1.5',
        sm: 'h-7 rounded-md px-2.5 text-[11px]',
        lg: 'h-9 rounded-lg px-5 text-sm',
        icon: 'h-7 w-7 rounded-md',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = 'Button';

export { Button, buttonVariants };
