function getColor(score) {
  if (score >= 70) return 'var(--green)'
  if (score >= 50) return 'var(--amber)'
  return 'var(--red)'
}

function Label({ k }) {
  const m = { satisfaction: 'Review score + trend', engagement: 'Playtime depth + hook + loop', reach: 'Volume + velocity + CCU' }
  return <>{m[k]}</>
}

export default function ScoreBreakdown({ lenses }) {
  const keys = ['satisfaction', 'engagement', 'reach']
  return (
    <div className="card">
      <h3 style={{ fontSize: '1rem', marginBottom: 16 }}>Score Breakdown</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {keys.map(k => {
          const l = lenses?.[k]
          const val = l?.score ?? null
          const color = val !== null ? getColor(val) : 'var(--muted)'
          return (
            <div key={k}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontWeight: 600, fontSize: '.85rem', textTransform: 'capitalize' }}>{k.replace('_',' ')}</span>
                <span style={{ color: val !== null ? color : 'var(--muted)', fontWeight: 700, fontSize: '.85rem' }}>
                  {val !== null ? val : '—'}
                </span>
              </div>
              <div style={{ height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${val ?? 0}%`, background: val !== null ? color : 'var(--muted)', borderRadius: 3, transition: 'width 1s ease' }} />
              </div>
              <p style={{ color: 'var(--muted)', fontSize: '.7rem', marginTop: 3 }}><Label k={k} /></p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
