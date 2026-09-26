import { avatarColor } from "@/lib/color";

export function Avatar({ id, name, size = 30 }: { id: string; name: string; size?: number }) {
  const initial = name.trim().split(/\s+/).pop()?.charAt(0).toUpperCase() ?? "?";
  return (
    <span
      className="ico"
      aria-hidden="true"
      style={{ background: avatarColor(id), borderRadius: "50%", width: size, height: size, fontWeight: 600, fontSize: Math.round(size * 0.45) }}
    >
      {initial}
    </span>
  );
}
