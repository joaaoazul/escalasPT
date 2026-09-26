import { onColor } from "@/lib/color";

type Kind = "WORK" | "OFF" | "ABSENCE" | string;

/** Pastilha de serviço: abreviatura sobre a cor do tipo (folga neutra, ausências às riscas). */
export function Pill({ code, color, kind, size, pending }: { code: string; color: string; kind: Kind; size?: "md" | "lg"; pending?: boolean }) {
  const cls = ["pill", size ?? "", kind === "OFF" ? "off" : "", kind === "ABSENCE" ? "abs" : "", pending ? "pending" : ""].join(" ");
  const style = kind === "OFF" ? undefined : ({ "--c": color, "--on": onColor(color) } as React.CSSProperties);
  return (
    <span className={cls} style={style}>
      {code}
    </span>
  );
}
