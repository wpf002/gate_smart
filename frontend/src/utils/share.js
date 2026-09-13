/**
 * Share a result using the device's native share sheet, falling back to copying
 * the text when the browser has no Web Share API (most desktop browsers).
 * Returns 'shared' | 'copied' | 'cancelled' | 'failed'.
 */
export async function shareResult({ title, text, url }) {
  const link = url || window.location.href;
  if (navigator.share) {
    try {
      await navigator.share({ title, text, url: link });
      return 'shared';
    } catch (err) {
      if (err && err.name === 'AbortError') return 'cancelled';
    }
  }
  try {
    await navigator.clipboard.writeText(`${text} ${link}`);
    return 'copied';
  } catch {
    return 'failed';
  }
}
