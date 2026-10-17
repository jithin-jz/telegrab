import { beforeAll, describe, expect, it } from 'vitest';

type StreamModule = typeof import('../lib/stream');
let stream: StreamModule;

beforeAll(async () => {
  // The module imports the bridge shim, which touches `window` on load.
  (globalThis as unknown as { window: unknown }).window = { addEventListener: () => {} };
  stream = await import('../lib/stream');
});

const info = { token: 'tok', base_url: 'http://127.0.0.1:5000' };

describe('media URLs', () => {
  it('builds stream URLs for folders and Saved Messages', () => {
    expect(stream.streamUrl(info, 42, 7)).toBe('http://127.0.0.1:5000/stream/42/7?token=tok');
    expect(stream.streamUrl(info, null, 7)).toBe('http://127.0.0.1:5000/stream/home/7?token=tok');
  });

  it('includes the thumbnail quality setting', () => {
    expect(stream.thumbnailUrl(info, 42, 7, 'high')).toBe(
      'http://127.0.0.1:5000/thumb/42/7?q=high&token=tok'
    );
    expect(stream.thumbnailUrl(info, null, 7)).toContain('/thumb/home/7?q=medium');
  });
});
