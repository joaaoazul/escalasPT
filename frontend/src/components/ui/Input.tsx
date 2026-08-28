/**
 * Input — thin wrapper around the global .input-group/.input-field utility
 * classes (index.css), covering the label + field + error-text pattern that
 * was hand-duplicated across every form in the app.
 */

import { forwardRef, useId, type InputHTMLAttributes, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, id, className = '', ...rest },
  ref,
) {
  const autoId = useId();
  const inputId = id ?? autoId;

  return (
    <div className="input-group">
      {label && (
        <label className="input-label" htmlFor={inputId}>
          {label}
        </label>
      )}
      <input
        ref={ref}
        id={inputId}
        className={`input-field${error ? ' input-error' : ''}${className ? ` ${className}` : ''}`}
        {...rest}
      />
      {error && <span className="input-error-text">{error}</span>}
    </div>
  );
});

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, error, id, className = '', children, ...rest },
  ref,
) {
  const autoId = useId();
  const inputId = id ?? autoId;

  return (
    <div className="input-group">
      {label && (
        <label className="input-label" htmlFor={inputId}>
          {label}
        </label>
      )}
      <select
        ref={ref}
        id={inputId}
        className={`input-field${error ? ' input-error' : ''}${className ? ` ${className}` : ''}`}
        {...rest}
      >
        {children}
      </select>
      {error && <span className="input-error-text">{error}</span>}
    </div>
  );
});

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, error, id, className = '', ...rest },
  ref,
) {
  const autoId = useId();
  const inputId = id ?? autoId;

  return (
    <div className="input-group">
      {label && (
        <label className="input-label" htmlFor={inputId}>
          {label}
        </label>
      )}
      <textarea
        ref={ref}
        id={inputId}
        className={`input-field${error ? ' input-error' : ''}${className ? ` ${className}` : ''}`}
        {...rest}
      />
      {error && <span className="input-error-text">{error}</span>}
    </div>
  );
});
