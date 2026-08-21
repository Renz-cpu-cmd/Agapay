import React from 'react';
import { AlertTriangle, X } from 'lucide-react';

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  isDanger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  isOpen,
  title,
  message,
  confirmLabel = 'Confirm Action',
  cancelLabel = 'Cancel',
  isDanger = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-border-light animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div
              className={`p-3 rounded-full ${
                isDanger ? 'bg-alert-evacuateBg text-alert-evacuate' : 'bg-brand-secondaryLight text-brand-primary'
              }`}
            >
              <AlertTriangle size={24} />
            </div>
            <h3 className="text-lg font-extrabold text-typography-primary">{title}</h3>
          </div>
          <button
            onClick={onCancel}
            className="text-typography-muted hover:text-typography-primary p-1 rounded-lg transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <p className="text-sm text-typography-secondary mt-4 leading-relaxed">{message}</p>

        <div className="mt-6 flex items-center justify-end gap-3">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm font-bold text-typography-secondary hover:text-typography-primary bg-surface-secondary hover:bg-border-light rounded-xl transition-colors"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className={`px-5 py-2 text-sm font-extrabold text-white rounded-xl shadow-md transition-transform active:scale-95 ${
              isDanger
                ? 'bg-alert-evacuate hover:bg-red-700'
                : 'bg-brand-primary hover:bg-brand-primaryDark'
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
