export default function SentimentPanel({ sentiment }) {
  if (!sentiment) return <div className="card"><p style={{color:'var(--muted)'}}>No sentiment data</p></div>
  const { compound_score, top_keywords, sentiment_distribution } = sentiment
  const color = compound_score > 0.2 ? 'var(--green)' : compound_score > -0.1 ? 'var(--amber)' : 'var(--red)'

  return (
    <div className="card">
      <h3 style={{ fontSize: '1rem', marginBottom: 4 }}>Review Sentiment</h3>
      <p style={{ color: 'var(--muted)', fontSize: '.75rem', marginBottom: 12 }}>Keyword-based analysis</p>
      <div style={{ textAlign: 'center', marginBottom: 16 }}>
        <div style={{ fontSize: '2.5rem', fontWeight: 800, color, lineHeight: 1 }}>{compound_score.toFixed(2)}</div>
        <span style={{ color: 'var(--muted)', fontSize: '.7rem' }}>Compound Score (-1 to +1)</span>
      </div>
      <div style={{ display: 'flex', gap: 6, marginBottom: 16 }}>
        {[
          ['Positive', sentiment_distribution?.positive || 0, 'var(--green)'],
          ['Neutral', sentiment_distribution?.neutral || 0, 'var(--amber)'],
          ['Negative', sentiment_distribution?.negative || 0, 'var(--red)'],
        ].map(([label, val, c]) => (
          <div key={label} style={{ flex: 1, textAlign: 'center', padding: '8px 4px', background: c.replace(')', ',.08)').replace('var(','rgba(').replace('--green','16,185,129').replace('--amber','245,158,11').replace('--red','239,68,68'), borderRadius: 6 }}>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: c }}>{val}%</div>
            <div style={{ fontSize: '.65rem', color: 'var(--muted)' }}>{label}</div>
          </div>
        ))}
      </div>
      {top_keywords?.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {top_keywords.map(kw => {
            const size = Math.min(12 + kw.count * 2, 22)
            return (
              <span key={kw.keyword} style={{ fontSize: `${size}px`, padding: '2px 10px', background: 'var(--bg2)', borderRadius: 20, border: '1px solid var(--border)', color: kw.count > 5 ? 'var(--accent2)' : 'var(--text2)' }}>
                {kw.keyword}
              </span>
            )
          })}
        </div>
      )}
    </div>
  )
}
