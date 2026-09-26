"use client";

export function Segmented<T extends string>({ value, options, onChange, label }: {
  value: T; options: { value: T; label: React.ReactNode }[]; onChange: (v: T) => void; label: string;
}) {
  return (
    <div className="seg" role="tablist" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} role="tab" aria-selected={value === o.value} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}
