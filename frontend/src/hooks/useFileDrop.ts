/**
 * File drop hook. Drag-and-drop is handled via the ExternalDropBlocker
 * and manual upload dialog for now.
 */
export function useFileDrop() {
  return { isDragging: false, droppedPaths: [] as string[], clearDropped: () => {} };
}
