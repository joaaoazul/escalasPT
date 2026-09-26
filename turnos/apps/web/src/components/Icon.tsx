const PATHS: Record<string, string> = {
  today: "M12 8a4 4 0 100 8 4 4 0 000-8zM12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4",
  cal: "M6.5 5h11a3 3 0 013 3v9.5a3 3 0 01-3 3h-11a3 3 0 01-3-3V8a3 3 0 013-3zM3.5 9.5h17M8 3v4M16 3v4M8 13.5h2M14 13.5h2M8 17h2",
  group: "M9 5.2a3.3 3.3 0 110 6.6 3.3 3.3 0 010-6.6zM3 19.5c.6-3.3 3-5.3 6-5.3s5.4 2 6 5.3M16.8 6.7a2.6 2.6 0 110 5.2M16.5 14.3c2.4.2 4 1.8 4.5 4.5",
  posto: "M12 3l7.5 3v5.5c0 4.6-3.2 8.2-7.5 9.5-4.3-1.3-7.5-4.9-7.5-9.5V6zM8.5 12l2.5 2.5 4.5-5",
  chart: "M4 20.5h16M6.5 11h1.2a1 1 0 011 1v5a1 1 0 01-1 1H6.5a1 1 0 01-1-1v-5a1 1 0 011-1zM11.4 6h1.2a1 1 0 011 1v10a1 1 0 01-1 1h-1.2a1 1 0 01-1-1V7a1 1 0 011-1zM16.3 13.5h1.2a1 1 0 011 1V17a1 1 0 01-1 1h-1.2a1 1 0 01-1-1v-2.5a1 1 0 011-1z",
  brush: "M14.5 4.5l5 5-8.2 8.2-5-5zM6.3 12.7c-2.3.2-3.3 2-3.3 4.3 0 1.5-.5 2.3-1 3 3.2.3 6.3-.4 7.3-2.3",
  chev: "M9 5l7 7-7 7",
  chevl: "M15 5l-7 7 7 7",
  x: "M6 6l12 12M18 6L6 18",
  warn: "M12 3.5l9.5 16.5h-19zM12 10v4.5M12 17.3v.2",
  swap: "M7 4L3.5 7.5 7 11M3.5 7.5h14M17 13l3.5 3.5L17 20M20.5 16.5h-14",
  check: "M12 2.5a9.5 9.5 0 110 19 9.5 9.5 0 010-19zM7.5 12.3l3 3 6-6.3",
  tick: "M5 12.5l4.5 4.5L19 7.5",
  note: "M5 4.5h14v10l-5 5H5zM14 19.5v-5h5M8.5 9h7M8.5 12.5h4",
  person: "M12 4a4 4 0 110 8 4 4 0 010-8zM4.5 20.5c.8-4 3.8-6.3 7.5-6.3s6.7 2.3 7.5 6.3",
  doc: "M7 3h7l5 5v13H7zM14 3v5h5M9.5 13h7M9.5 16.5h7",
  plus: "M12 5v14M5 12h14",
  undo: "M9 14L4 9l5-5M4 9h10.5a5.5 5.5 0 010 11H11",
};

export function Icon({ name, size = 22, className, style }: { name: keyof typeof PATHS; size?: number; className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={`i ${className ?? ""}`} width={size} height={size} viewBox="0 0 24 24" style={{ width: size, height: size, ...style }} aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  );
}
