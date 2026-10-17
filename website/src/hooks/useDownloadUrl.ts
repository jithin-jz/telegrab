import { useEffect, useState } from 'react'

export const REPO = 'jithin-jz/telegrab'
export const REPO_URL = `https://github.com/${REPO}`
export const RELEASES_URL = `${REPO_URL}/releases/latest`

export type OS = 'windows' | 'mac' | 'linux' | 'unknown'
export type Platform = Exclude<OS, 'unknown'>
export type Build = 'windows' | 'windows-portable' | 'mac' | 'linux' | 'checksums'

interface ReleaseAsset {
  name: string
  browser_download_url: string
  size?: number
  download_count?: number
}

interface Release {
  tag_name: string
  draft: boolean
  prerelease: boolean
  published_at?: string
  assets?: ReleaseAsset[]
}

interface ReleaseInfo {
  version: string | null
  publishedAt: string | null
  downloadCount: number
  assets: ReleaseAsset[]
}

// One request per page load, shared by every component (the unauthenticated
// GitHub API allows only 60 requests per hour per visitor).
let releaseInfo: Promise<ReleaseInfo> | null = null

function loadReleaseInfo(): Promise<ReleaseInfo> {
  releaseInfo ??= fetch(`https://api.github.com/repos/${REPO}/releases?per_page=100`)
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`GitHub API ${r.status}`))))
    .then((data: unknown) => {
      const releases = Array.isArray(data) ? (data as Release[]) : []
      const latest = releases.find((r) => !r.draft && !r.prerelease)
      const downloadCount = releases
        .flatMap((r) => r.assets ?? [])
        .reduce((sum, a) => sum + (a.download_count ?? 0), 0)
      return {
        version: latest?.tag_name ?? null,
        publishedAt: latest?.published_at ?? null,
        downloadCount,
        assets: latest?.assets ?? [],
      }
    })
    .catch(() => {
      releaseInfo = null // retry on the next mount
      return { version: null, publishedAt: null, downloadCount: 0, assets: [] }
    })
  return releaseInfo
}

function detectOS(): OS {
  const uaData = (navigator as Navigator & { userAgentData?: { platform?: string } }).userAgentData
  const platform = (uaData?.platform || navigator.userAgent).toLowerCase()
  if (platform.includes('win')) return 'windows'
  if (platform.includes('mac')) return 'mac'
  // Android reports "Linux" too, but there is no Android build.
  if (platform.includes('linux') && !platform.includes('android')) return 'linux'
  return 'unknown'
}

const ASSET_FOR: Record<Build, (name: string) => boolean> = {
  windows: (n) => n.endsWith('-setup.exe'),
  'windows-portable': (n) => n.includes('portable'),
  mac: (n) => n.includes('macos'),
  linux: (n) => n.includes('linux'),
  checksums: (n) => n.startsWith('sha256'),
}

export const PLATFORM_NAME: Record<Platform, string> = {
  windows: 'Windows',
  mac: 'macOS',
  linux: 'Linux',
}

const LABEL: Record<OS, string> = {
  windows: 'Download for Windows',
  mac: 'Download for macOS',
  linux: 'Download for Linux',
  unknown: 'Download',
}

export function formatSize(bytes?: number): string | null {
  if (!bytes) return null
  return `${(bytes / 1024 / 1024).toFixed(0)} MB`
}

export function useDownloadUrl() {
  const [os] = useState(detectOS)
  const [info, setInfo] = useState<ReleaseInfo | null>(null)

  useEffect(() => {
    let active = true
    loadReleaseInfo().then((i) => {
      if (active) setInfo(i)
    })
    return () => {
      active = false
    }
  }, [])

  const find = (build: Build) => info?.assets.find((a) => ASSET_FOR[build](a.name.toLowerCase()))
  const asset = os === 'unknown' ? undefined : find(os)

  return {
    url: asset?.browser_download_url ?? RELEASES_URL,
    label: LABEL[os],
    os,
    version: info?.version ?? null,
    publishedAt: info?.publishedAt ?? null,
    downloadCount: info ? info.downloadCount : null,
    /** Direct link and size for one build, falling back to the releases page. */
    build: (b: Build) => {
      const a = find(b)
      return { url: a?.browser_download_url ?? RELEASES_URL, size: formatSize(a?.size) }
    },
  }
}
