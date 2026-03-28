import { createContext, useContext, useState, useCallback, useRef, useEffect, type ReactNode } from 'react';

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

type ToastVariant = 'success' | 'error' | 'warning' | 'info';

interface Toast {
  id: number;
  variant: ToastVariant;
  title?: string;
  message: string;
  duration: number; // ms
  exiting?: boolean;
}

interface ToastContextValue {
  toast: {
    success: (message: string, options?: ToastOptions) => void;
    error:   (message: string, options?: ToastOptions) => void;
    warning: (message: string, options?: ToastOptions) => void;
    info:    (message: string, options?: ToastOptions) => void;
  };
}

interface ToastOptions {
  title?: string;
  duration?: number;
}

/* ------------------------------------------------------------------ */
/* Icons                                                               */
/* ------------------------------------------------------------------ */

const ICONS: Record<ToastVariant, string> = {
  success: '\u2714',  // check mark
  error:   '\u2718',  // cross
  warning: '\u26A0',  // warning
  info:    '\u2139',  // info
};

const TITLES: Record<ToastVariant, string> = {
  success: 'Success',
  error:   'Error',
  warning: 'Warning',
  info:    'Info',
};

/* ------------------------------------------------------------------ */
/* Context                                                             */
/* ------------------------------------------------------------------ */

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within a ToastProvider');
  return ctx;
}

/* ------------------------------------------------------------------ */
/* Single toast item                                                   */
/* ------------------------------------------------------------------ */

function ToastItem({ toast: t, onDismiss }: { toast: Toast; onDismiss: (id: number) => void }) {
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    timerRef.current = setTimeout(() => onDismiss(t.id), t.duration);
    return () => clearTimeout(timerRef.current);
  }, [t.id, t.duration, onDismiss]);

  return (
    <div
      className={`neo-toast neo-toast-${t.variant}${t.exiting ? ' neo-toast-exiting' : ''}`}
      role="alert"
      style={{ position: 'relative' }}
    >
      <span className="neo-toast-icon">{ICONS[t.variant]}</span>
      <div className="neo-toast-body">
        <div className="neo-toast-title">{t.title ?? TITLES[t.variant]}</div>
        <div className="neo-toast-message">{t.message}</div>
      </div>
      <button
        className="neo-toast-close"
        onClick={() => onDismiss(t.id)}
        aria-label="Dismiss"
      >
        &times;
      </button>
      <div
        className="neo-toast-progress"
        style={{ animationDuration: `${t.duration}ms` }}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Provider                                                            */
/* ------------------------------------------------------------------ */

const EXIT_DURATION = 300; // match CSS animation

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id: number) => {
    // Mark as exiting for fade-out animation
    setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, exiting: true } : t)));
    // Remove after animation completes
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, EXIT_DURATION);
  }, []);

  const addToast = useCallback((variant: ToastVariant, message: string, options?: ToastOptions) => {
    const id = nextId.current++;
    setToasts((prev) => [
      ...prev,
      {
        id,
        variant,
        message,
        title: options?.title,
        duration: options?.duration ?? 4000,
      },
    ]);
  }, []);

  const contextValue: ToastContextValue = {
    toast: {
      success: (msg, opts) => addToast('success', msg, opts),
      error:   (msg, opts) => addToast('error', msg, opts),
      warning: (msg, opts) => addToast('warning', msg, opts),
      info:    (msg, opts) => addToast('info', msg, opts),
    },
  };

  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      <div className="neo-toast-container">
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}
