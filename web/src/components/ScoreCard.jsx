function getColor(score) {
  if (score >= 70) return 'var(--green)'
  if (score >= 50) return 'var(--amber)'
  return 'var(--red)'
}

function LENS_INFO() { return {
  satisfaction: { label: 'Satisfaction', desc: 'Are buyers glad they bought it?' },
  engagement: { label: 'Engagement', desc: 'Are players actually playing?' },
  reach: { label: 'Reach', desc: 'Is it finding an audience?' },
}}

export default function ScoreCard({ lenses, label }) {
  const info = LENS_INFO()
  const keys = ['satisfaction', 'engagement', 'reach']
  const hasData = keys.every(k => lenses?.[k])

  return (
    <div className="card">
      <h3 style={{ fontSize: '1rem', marginBottom: 16 }}>PMF Signal</h3>
      <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
        {keys.map(k => {
          const l = lenses?.[k]
          const score = l?.score ?? 0
          const color = getColor(score)
          const r = 38; const circ = 2 * Math.PI * r; const off = circ - (score / 100) * circ
          return (
            <div key={k} style={{ flex: 1, textAlign: 'center' }}>
              <svg width="90" height="90" viewBox="0 0 90 90" style={{ display: 'block', margin: '0 auto 4px' }}>
                <circle cx="45" cy="45" r={r} fill="none" stroke="var(--border)" strokeWidth="6" />
                <circle cx="45" cy="45" r={r} fill="none" stroke={color} strokeWidth="6" strokeLinecap="round"
                  strokeDasharray={circ} strokeDashoffset={off} transform="rotate(-90 45 45)"
                  style={{ transition: 'stroke-dashoffset 1s ease' }} />
              </svg>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color }}>{score}</div>
              <div style={{ fontSize: '.65rem', color: 'var(--muted)', marginTop: 2 }}>
                {info[k].label}
                {l ? ` (±${l.ci || '?'})` : ''}
              </div>
            </div>
          )
        })}
      </div>
      <p style={{ color: 'var(--text2)', fontSize: '.82rem', lineHeight: 1.5, fontStyle: 'italic' }}>
        {label.split('\n').pop()?.replace('→', '').trim() || 'Analyzing...'}
      </p>
    </div>
  )
}
