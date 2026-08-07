export default function ReviewPanel({ reviews }) {
  if (!reviews) return <div className="card"><p style={{color:'var(--muted)'}}>No review data</p></div>
  const { total, positive, negative, score, trend_label } = reviews
  const pct = score || 0
  const posWidth = total > 0 ? (positive / total * 100) : 50
  const color = pct >= 80 ? 'var(--green)' : pct >= 60 ? 'var(--amber)' : 'var(--red)'

  return (
    <div className="card">
      <h3 style={{ fontSize: '1rem', marginBottom: 12 }}>Review Scores</h3>
      <div style={{ fontSize: '2rem', fontWeight: 800, color, marginBottom: 4 }}>{pct}%</div>
      <div className="badge" style={{ background: pct>=80?'rgba(16,185,129,.12)':pct>=60?'rgba(245,158,11,.12)':'rgba(239,68,68,.12)', color, marginBottom: 14 }}>{trend_label}</div>
      <div style={{ height: 10, background: 'var(--border)', borderRadius: 5, overflow: 'hidden', display: 'flex', marginBottom: 12 }}>
        <div style={{ width: `${posWidth}%`, background: 'var(--green)', height: '100%', transition: 'width 1s ease' }} />
        <div style={{ width: `${100 - posWidth}%`, background: 'var(--red)', height: '100%', transition: 'width 1s ease' }} />
      </div>
      <div style={{ display: 'flex', gap: 20, justifyContent: 'space-between', fontSize: '.8rem' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ color: 'var(--muted)', fontSize: '.7rem' }}>Total</div>
          <div style={{ fontWeight: 700 }}>{total.toLocaleString()}</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ color: 'var(--muted)', fontSize: '.7rem' }}>Positive</div>
          <div style={{ fontWeight: 700, color: 'var(--green)' }}>{positive.toLocaleString()}</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ color: 'var(--muted)', fontSize: '.7rem' }}>Negative</div>
          <div style={{ fontWeight: 700, color: 'var(--red)' }}>{negative.toLocaleString()}</div>
        </div>
      </div>
    </div>
  )
}
