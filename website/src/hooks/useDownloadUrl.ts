import { useState, useEffect } from 'react'

const FALLBACK = 'https://github.com/jithin-jz/telegrab/releases/latest'

function getOS(): 'windows' | 'mac' | 'unknown' {
  const p = navigator.platform.toLowerCase()
  if (p.includes('win')) return 'windows'
  if (p.includes('mac')) return 'mac'
  return 'unknown'
}

export function useDownloadUrl() {
  const [url, setUrl] = useState(FALLBACK)
  const os = getOS()
  const label = os === 'mac' ? 'Download for macOS' : os === 'windows' ? 'Download for Windows' : 'Download'

  useEffect(() => {
    fetch('https://api.github.com/repos/jithin-jz/telegrab/releases/latest')
      .then(r => r.json())
      .then(data => {
        const assets: { name: string; browser_download_url: string }[] = data.assets ?? []
        let match: string | undefined
        if (os === 'windows') {
          match = assets.find(a => a.name.toLowerCase().endsWith('-setup.exe'))?.browser_download_url
        } else if (os === 'mac') {
          match = assets.find(a => a.name.toLowerCase().includes('macos'))?.browser_download_url
        }
        if (match) setUrl(match)
      })
      .catch(() => {})
  }, [os])

  return { url, label, os }
}
