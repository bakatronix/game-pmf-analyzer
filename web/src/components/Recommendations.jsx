const PRIORITY = { HIGH: { bg: 'rgba(239,68,68,.08)', border: 'rgba(239,68,68,.25)', color: '#fca5a5' }, MEDIUM: { bg: 'rgba(245,158,11,.08)', border: 'rgba(245,158,11,.25)', color: '#fcd34d' }, LOW: { bg: 'rgba(99,102,241,.08)', border: 'rgba(99,102,241,.25)', color: '#a5b4fc' } }

export default function Recommendations({ recs, patchCount }) {
  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 style={{ fontSize: '1rem', marginBottom: 4 }}>Recommendations (next 30 days)</h3>
      <p style={{ color: 'var(--muted)', fontSize: '.75rem', marginBottom: 16 }}>
        {patchCount > 0 ? `${patchCount} patches detected in post-launch history` : 'No patches detected'}
      </p>
      {(!recs || recs.length === 0) ? (
        <p style={{ color: 'var(--muted)', fontSize: '.85rem' }}>All signals within normal range — keep monitoring.</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {recs.map((r, i) => {
            const p = PRIORITY[r.priority] || PRIORITY.LOW
            return (
              <div key={i} style={{ background: p.bg, border: `1px solid ${p.border}`, borderRadius: 8, padding: '14px 18px' }}>
                <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                  <span className="badge" style={{ background: p.border, color: p.color, flexShrink: 0, fontSize: '.65rem' }}>{r.priority}</span>
                  <div>
                    <strong style={{ color: p.color, fontSize: '.88rem' }}>{r.title}</strong>
                    <span style={{ color: 'var(--muted)', fontSize: '.7rem', marginLeft: 8 }}>({r.category})</span>
                    <p style={{ color: 'var(--text2)', fontSize: '.8rem', marginTop: 4, lineHeight: 1.5 }}>{r.detail}</p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
