/** Cor do texto (branco ou quase preto) com o melhor contraste WCAG sobre a cor do serviço. */
export function onColor(hex: string): string {
  const c = [1, 3, 5]
    .map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  const L = 0.2126 * c[0]! + 0.7152 * c[1]! + 0.0722 * c[2]!;
  return 1.05 / (L + 0.05) >= (L + 0.05) / 0.05 ? "#FFFFFF" : "#1C1C1E";
}

const PALETTE = ["#5856D6", "#1FA2B8", "#FF9F0A", "#30B35A", "#FF375F", "#0A84FF", "#BF5AF2", "#AC8E68", "#64D2FF", "#FF6482"];

/** Cor estável do avatar de um militar. */
export function avatarColor(id: string): string {
  let h = 0;
  for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return PALETTE[h % PALETTE.length]!;
}
