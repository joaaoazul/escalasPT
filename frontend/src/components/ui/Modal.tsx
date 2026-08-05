/**
 * Modal — shared overlay + accessibility chrome for dialogs and side panels.
 *
 * Handles what every ad-hoc modal in this app was missing: focus trap,
 * Escape-to-close, role="dialog"/aria-modal, and returning focus to the
 * trigger element on close. Callers keep full control of visual layout
 * (side panel vs centered dialog) via `panelClassName` + `children`.
 */

import { useEffect, useRef, type ReactNode } from 'react';

interface ModalProps {
  onClose: () => void;
  children: ReactNode;
  /** Class for the panel element (e.g. 'shift-detail-panel', 'modal-container'). */
  panelClassName: string;
  /** Extra class(es) appended to the panel, e.g. an entrance animation. */
  className?: string;
  /** Accessible label for the dialog (falls back to aria-labelledby via the caller's own heading if omitted). */
  ariaLabel?: string;
  /** Disable overlay-click / Escape close while a submit is pending. */
  closeDisabled?: boolean;
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function Modal({
  onClose,
  children,
  panelClassName,
  className = '',
  ariaLabel,
  closeDisabled = false,
}: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    previouslyFocused.current = document.activeElement as HTMLElement | null;

    const panel = panelRef.current;
    const focusable = panel?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
    (focusable?.[0] ?? panel)?.focus();

    return () => {
      previouslyFocused.current?.focus?.();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (closeDisabled) return;

      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
        return;
      }

      if (e.key === 'Tab') {
        const panel = panelRef.current;
        if (!panel) return;
        const focusable = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
        if (focusable.length === 0) return;

        const first = focusable[0]!;
        const last = focusable[focusable.length - 1]!;

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose, closeDisabled]);

  return (
    <>
      <div className="modal-overlay" onClick={closeDisabled ? undefined : onClose} />
      <div
        ref={panelRef}
        className={`${panelClassName}${className ? ` ${className}` : ''}`}
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel}
        tabIndex={-1}
      >
        {children}
      </div>
    </>
  );
}
