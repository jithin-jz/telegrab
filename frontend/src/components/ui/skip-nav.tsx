/**
 * SkipNav — Accessibility skip-navigation link.
 * Renders as a visually hidden link that becomes visible on focus,
 * allowing keyboard users to jump directly to the file explorer main content.
 */
export function SkipNav() {
  return (
    <a
      href="#file-explorer-main"
      className="skip-nav"
    >
      Skip to content
    </a>
  );
}
