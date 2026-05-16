import * as React from 'react';
import { cn } from '../../lib/cn';

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        ref={ref}
        className={cn(
          'border-hairline-strong bg-background text-foreground flex h-11 w-full rounded-md border px-3 py-2 text-sm',
          'transition-colors',
          'file:text-foreground file:border-0 file:bg-transparent file:text-sm file:font-medium',
          'placeholder:text-stone',
          'focus-visible:border-primary focus-visible:ring-primary/20 focus-visible:ring-2 focus-visible:outline-none',
          'disabled:cursor-not-allowed disabled:opacity-50',
          className
        )}
        {...props}
      />
    );
  }
);
Input.displayName = 'Input';

export { Input };
