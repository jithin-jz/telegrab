import { useState, useEffect } from 'react'

const FALLBACK = 'https://github.com/jithin-jz/telegrab/releases/latest'

function getOS(): 'windows' | 'mac' | 'unknown' {
  // Prefer modern API, fall back to userAgent
  const uaData = (navigator as unknown as { userAgentData?: { platform?: string } }).userAgentData;
  if (uaData?.platform) {
    const p = uaData.platform.toLowerCase()
    if (p.includes('win')) return 'windows'
    if (p.includes('mac')) return 'mac'
    return 'unknown'
  }
  const ua = navigator.userAgent.toLowerCase()
  if (ua.includes('win')) return 'windows'
  if (ua.includes('mac')) return 'mac'
  return 'unknown'
}

export function useDownloadUrl() {
  const [url, setUrl] = useState(FALLBACK)
  const [downloadCount, setDownloadCount] = useState<number | null>(null)
  const os = getOS()
  const label = os === 'mac' ? 'Download for macOS' : os === 'windows' ? 'Download for Windows' : 'Download'

  useEffect(() => {
    fetch('https://api.github.com/repos/jithin-jz/telegrab/releases?per_page=100')
      .then(r => r.json())
      .then((data: any[]) => {
        if (!Array.isArray(data)) return

        // 1. Calculate total downloads across all releases
        let total = 0
        data.forEach((release: any) => {
          const assets = release.assets ?? []
          assets.forEach((asset: any) => {
            total += asset.download_count ?? 0
          })
        })
        setDownloadCount(total)

        // 2. Find the latest release to extract the download URL for the OS
        const latestRelease = data.find((r: any) => !r.prerelease && !r.draft) || data[0]
        if (latestRelease) {
          const assets: { name: string; browser_download_url: string }[] = latestRelease.assets ?? []
          let match: string | undefined
          if (os === 'windows') {
            match = assets.find(a => a.name.toLowerCase().endsWith('-setup.exe'))?.browser_download_url
          } else if (os === 'mac') {
            match = assets.find(a => a.name.toLowerCase().includes('macos'))?.browser_download_url
          }
          if (match) setUrl(match)
        }
      })
      .catch(() => {})
  }, [os])

  return { url, label, os, downloadCount }
}
