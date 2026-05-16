import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge Tailwind classes with proper conflict resolution.
 * Used by every shadcn-style component.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
