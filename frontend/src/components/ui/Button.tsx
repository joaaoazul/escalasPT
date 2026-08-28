/**
 * Button — thin wrapper around the global .btn utility classes (index.css)
 * so variants/sizes are typed instead of hand-typed className strings.
 */

import { forwardRef, type ButtonHTMLAttributes } from 'react';

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost';
type Size = 'sm' | 'md' | 'lg' | 'icon';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

const SIZE_CLASS: Record<Size, string> = {
  sm: 'btn-sm',
  md: '',
  lg: 'btn-lg',
  icon: 'btn-icon',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', loading = false, disabled, className = '', children, ...rest },
  ref,
) {
  const classes = ['btn', `btn-${variant}`, SIZE_CLASS[size], className]
    .filter(Boolean)
    .join(' ');

  return (
    <button ref={ref} className={classes} disabled={disabled || loading} {...rest}>
      {loading ? <span className="spinner spinner-sm" /> : null}
      {children}
    </button>
  );
});
