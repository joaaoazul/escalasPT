/** Datas locais do calendário como strings ISO (YYYY-MM-DD); as contas fazem-se em UTC para não haver saltos de fuso. */

export const MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
export const WEEKDAYS = ["domingo", "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado"];
export const WD_SHORT = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];
export const WD_LETTER = ["D", "S", "T", "Q", "Q", "S", "S"];

export const iso = (y: number, m: number, d: number) => `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;

function parse(s: string): Date {
  const [y, m, d] = s.split("-").map(Number) as [number, number, number];
  return new Date(Date.UTC(y, m - 1, d));
}

const fmt = (d: Date) => iso(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate());

export function addDays(s: string, n: number): string {
  const d = parse(s);
  d.setUTCDate(d.getUTCDate() + n);
  return fmt(d);
}

export const weekday = (s: string) => parse(s).getUTCDay();
export const dayNum = (s: string) => Number(s.slice(8));
export const monthIdx = (s: string) => Number(s.slice(5, 7)) - 1;
export const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
export const mondayOf = (s: string) => addDays(s, -((weekday(s) + 6) % 7));

export function today(): string {
  const n = new Date();
  return iso(n.getFullYear(), n.getMonth() + 1, n.getDate());
}

export const longDate = (s: string) => `${WEEKDAYS[weekday(s)]}, ${dayNum(s)} de ${MONTHS[monthIdx(s)]}`;
export const shortDate = (s: string) => `${WD_SHORT[weekday(s)]}, ${dayNum(s)} ${MONTHS[monthIdx(s)]!.slice(0, 3)}`;

export function relDate(s: string): string {
  const t = today();
  if (s === t) return "Hoje";
  if (s === addDays(t, 1)) return "Amanhã";
  return shortDate(s);
}

export function monthRange(year: number, month: number): { from: string; to: string } {
  const last = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return { from: iso(year, month, 1), to: iso(year, month, last) };
}

/** Células da grelha do mês (semana começa à segunda), incluindo os dias dos meses vizinhos. */
export function monthCells(year: number, month: number): string[] {
  const first = iso(year, month, 1);
  const lead = (weekday(first) + 6) % 7;
  const start = addDays(first, -lead);
  const days = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return Array.from({ length: Math.ceil((lead + days) / 7) * 7 }, (_, i) => addDays(start, i));
}

export function shiftMonth(year: number, month: number, delta: number): [number, number] {
  const idx = year * 12 + (month - 1) + delta;
  return [Math.floor(idx / 12), (idx % 12) + 1];
}

/** "08:00:00" → "08:00" */
export const hhmm = (t: string | null | undefined) => (t ? t.slice(0, 5) : "");

export function endTime(start: string | null, minutes: number | null): string {
  if (!start || minutes == null) return "";
  const [h, m] = start.split(":").map(Number) as [number, number];
  const total = (h * 60 + m + minutes) % 1440;
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

export const hours = (min: number) => (min / 60).toLocaleString("pt-PT", { maximumFractionDigits: 1 });

export function stamp(isoInstant: string): string {
  const d = new Date(isoInstant);
  return `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
