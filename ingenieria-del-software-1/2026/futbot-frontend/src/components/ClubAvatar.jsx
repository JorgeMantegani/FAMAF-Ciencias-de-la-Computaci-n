import { useState } from 'react'

export default function ClubAvatar({ avatar, clubName }) {
  const [failedSource, setFailedSource] = useState(null)
  const source = avatar && (/^\d+$/.test(avatar) ? `/avatars/${avatar}.jpg` : avatar)
  if (!source || failedSource === source) {
    return <span className="club-avatar club-avatar-fallback" aria-hidden="true">{clubName.slice(0, 1).toUpperCase()}</span>
  }
  return <img className="club-avatar" src={source} alt={`Escudo de ${clubName}`} onError={() => setFailedSource(source)} />
}
