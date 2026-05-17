/**
 * ExternalDropBlocker - Now a no-op since drag-and-drop is handled by useFileDrop.
 * Kept for backward compatibility with Dashboard imports.
 */
export function ExternalDropBlocker({ onUploadClick: _ }: { onUploadClick: () => void }) {
  return null;
}
