import React, { ReactNode } from 'react';
import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  message: string;
  icon?: ReactNode;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export function EmptyState({ title, message, icon, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center bg-white rounded-xl border border-border-light shadow-card">
      <div className="p-4 rounded-full bg-surface-secondary text-typography-secondary mb-3">
        {icon || <Inbox size={36} />}
      </div>
      <h4 className="text-base font-extrabold text-typography-primary">{title}</h4>
      <p className="text-sm text-typography-secondary max-w-sm mt-1">{message}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="mt-4 px-4 py-2 text-xs font-bold text-white bg-brand-primary hover:bg-brand-primaryDark rounded-lg transition-colors"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
