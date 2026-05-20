'use client';

import React, { createContext, useContext, useState, ReactNode } from 'react';

interface ConfirmOptions {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
}

interface DialogContextType {
  confirm: (options: ConfirmOptions) => Promise<boolean>;
}

const DialogContext = createContext<DialogContextType | undefined>(undefined);

export const DialogProvider = ({ children }: { children: ReactNode }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [options, setOptions] = useState<ConfirmOptions | null>(null);
  const [resolveRef, setResolveRef] = useState<((value: boolean) => void) | null>(null);

  const confirm = (opts: ConfirmOptions): Promise<boolean> => {
    setOptions(opts);
    setIsOpen(true);
    return new Promise<boolean>((resolve) => {
      setResolveRef(() => resolve);
    });
  };

  const handleClose = (value: boolean) => {
    setIsOpen(false);
    if (resolveRef) {
      resolveRef(value);
    }
  };

  return (
    <DialogContext.Provider value={{ confirm }}>
      {children}
      {isOpen && options && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="w-full max-w-md overflow-hidden bg-slate-900 border border-slate-800 rounded-xl shadow-2xl">
            <div className="p-6">
              <h3 className="text-lg font-semibold text-slate-100">{options.title}</h3>
              <p className="mt-2 text-sm text-slate-400">{options.message}</p>
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 bg-slate-950/50 border-t border-slate-800/50">
              <button
                type="button"
                onClick={() => handleClose(false)}
                className="px-4 py-2 text-sm font-medium text-slate-400 hover:text-slate-200 transition-colors duration-150 rounded-lg hover:bg-slate-800"
              >
                {options.cancelText || 'Cancel'}
              </button>
              <button
                type="button"
                onClick={() => handleClose(true)}
                className="px-4 py-2 text-sm font-semibold text-white bg-violet-600 hover:bg-violet-500 active:bg-violet-700 transition-colors duration-150 rounded-lg shadow-lg shadow-violet-500/10"
              >
                {options.confirmText || 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}
    </DialogContext.Provider>
  );
};

export const useConfirm = () => {
  const context = useContext(DialogContext);
  if (!context) {
    throw new Error('useConfirm must be used within a DialogProvider');
  }
  return context.confirm;
};
