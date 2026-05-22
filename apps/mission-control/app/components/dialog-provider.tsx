"use client";

import { createContext, useContext, useId, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

interface ConfirmOptions {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  /** When true the confirm button uses danger styling (red). Default: false. */
  dangerous?: boolean;
}

interface DialogContextType {
  confirm: (options: ConfirmOptions) => Promise<boolean>;
}

const DialogContext = createContext<DialogContextType | undefined>(undefined);

export function DialogProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [options, setOptions] = useState<ConfirmOptions | null>(null);
  // useState stores functions via the updater-function protocol, so we wrap in
  // an arrow function: setResolveRef(() => resolve) stores the resolve fn as a value.
  const [resolveRef, setResolveRef] = useState<((value: boolean) => void) | null>(null);

  const dialogTitleId = useId();
  const confirmButtonRef = useRef<HTMLButtonElement | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  const confirm = (opts: ConfirmOptions): Promise<boolean> => {
    setOptions(opts);
    setIsOpen(true);
    return new Promise<boolean>((resolve) => {
      setResolveRef(() => resolve);
    });
  };

  const handleClose = (value: boolean) => {
    setIsOpen(false);
    resolveRef?.(value);
  };

  // Focus management: trap focus in dialog while open, restore on close.
  useEffect(() => {
    if (!isOpen) return undefined;

    previousFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    confirmButtonRef.current?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        handleClose(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      previousFocusRef.current?.focus();
    };
    // handleClose is stable across renders; isOpen is the dependency that matters.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  return (
    <DialogContext.Provider value={{ confirm }}>
      {children}
      {isOpen && options && (
        <div
          className="confirm-dialog-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) handleClose(false);
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby={dialogTitleId}
            className="confirm-dialog"
          >
            <div className="confirm-dialog-body">
              <h3 id={dialogTitleId}>{options.title}</h3>
              <p>{options.message}</p>
            </div>
            <div className="confirm-dialog-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => handleClose(false)}
              >
                {options.cancelText ?? "Keep Running"}
              </button>
              <button
                ref={confirmButtonRef}
                type="button"
                className={options.dangerous ? "danger-button" : "primary-button"}
                onClick={() => handleClose(true)}
              >
                {options.confirmText ?? "Confirm"}
              </button>
            </div>
          </div>
        </div>
      )}
    </DialogContext.Provider>
  );
}

export function useConfirm() {
  const context = useContext(DialogContext);
  if (!context) {
    throw new Error("useConfirm must be used within a DialogProvider");
  }
  return context.confirm;
}
