/** Partilha pelo menu do sistema (WhatsApp, SMS, …) ou, sem ele, copia a ligação. Devolve false se o utilizador cancelar. */
export async function shareLink(url: string, title: string, text: string, onCopied: () => void): Promise<void> {
  try {
    if (navigator.share) await navigator.share({ title, text, url });
    else {
      await navigator.clipboard.writeText(url);
      onCopied();
    }
  } catch {
    /* partilha cancelada */
  }
}
