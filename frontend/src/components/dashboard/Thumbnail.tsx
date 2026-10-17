import { useState } from 'react';
import { useSettings } from '../../contexts/SettingsContext';
import { thumbnailUrl, useStreamInfo } from '../../lib/stream';

interface ThumbnailProps {
  messageId: number;
  folderId: number | null;
  className?: string;
  /** Called once the image has loaded (e.g. to switch overlay styles). */
  onLoaded?: (loaded: boolean) => void;
}

/**
 * Lazy-loaded file thumbnail served by the local media server.
 *
 * Loading thumbnails as plain image URLs (instead of base64 strings over the
 * JS bridge) lets the webview fetch, decode and cache them natively and keeps
 * them out of the JavaScript heap. Renders nothing when there's no thumbnail.
 */
export function Thumbnail({ messageId, folderId, className, onLoaded }: ThumbnailProps) {
  const info = useStreamInfo();
  const { settings } = useSettings();
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);

  if (!info || failed) return null;
  return (
    <img
      src={thumbnailUrl(info, folderId, messageId, settings.thumbnailQuality)}
      alt=""
      loading="lazy"
      decoding="async"
      draggable={false}
      className={className}
      style={{ opacity: loaded ? 1 : 0, transition: 'opacity 150ms ease-out' }}
      onLoad={() => {
        setLoaded(true);
        onLoaded?.(true);
      }}
      onError={() => {
        setFailed(true);
        onLoaded?.(false);
      }}
    />
  );
}
