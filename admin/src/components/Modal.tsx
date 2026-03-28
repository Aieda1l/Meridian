import { type ReactNode } from 'react';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}

export default function Modal({ open, onClose, title, children }: ModalProps) {
  if (!open) return null;

  return (
    <div className="neo-modal-overlay" onClick={onClose}>
      <div
        className="neo-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-lg font-bold text-neo-dark">{title}</h3>
          <button
            onClick={onClose}
            className="neo-btn neo-btn-icon text-neo-muted hover:text-neo-dark"
            style={{ width: '2rem', height: '2rem', fontSize: '1.25rem' }}
          >
            &times;
          </button>
        </div>
        <div>{children}</div>
      </div>
    </div>
  );
}
