import React from 'react';
import { cn } from '../../lib/utils';

interface SpinnerProps {
  className?: string;
}

export const Spinner: React.FC<SpinnerProps> = ({ className }) => {
  return (
    <div className={cn("animate-spin h-5 w-5 border-2 border-current border-t-transparent text-primary rounded-full", className)}>
      <span className="sr-only">Loading...</span>
    </div>
  );
};
