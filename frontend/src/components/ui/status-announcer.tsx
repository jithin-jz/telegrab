/**
 * StatusAnnouncer — Hidden ARIA live regions for screen reader announcements.
 *
 * Provides two regions:
 * - `aria-live="polite"` (id="status-polite") for success/status messages
 * - `aria-live="assertive"` (id="status-assertive") for error/alert messages
 *
 * Other components can announce messages by setting the textContent of these
 * elements via `document.getElementById('status-polite')` or using the
 * `announce` utility.
 */
export function StatusAnnouncer() {
  return (
    <>
      <div
        id="status-polite"
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      />
      <div
        id="status-assertive"
        role="alert"
        aria-live="assertive"
        aria-atomic="true"
        className="sr-only"
      />
    </>
  );
}

/**
 * Programmatically announce a message to screen readers.
 *
 * @param message - The text to announce
 * @param priority - "polite" for non-urgent status, "assertive" for errors/alerts
 */
export function announce(message: string, priority: 'polite' | 'assertive' = 'polite') {
  const id = priority === 'assertive' ? 'status-assertive' : 'status-polite';
  const el = document.getElementById(id);
  if (el) {
    // Clear then set to ensure re-announcement of the same message
    el.textContent = '';
    requestAnimationFrame(() => {
      el.textContent = message;
    });
  }
}
