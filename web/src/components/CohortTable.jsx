export default function CohortTable({ cohort }) {
  if (!cohort || cohort.cohort_size === 0) return (
    <div className="card"><h3 style={{fontSize:'1rem',marginBottom:8}}>Cohort Comparison</h3><p style={{color:'var(--muted)',fontSize:'.85rem'}}>No cohort data available — need more games in the database within ±90 days of this release.</p></div>
  )

  const ranks = cohort?.percentile_ranks
  if (!ranks) return <div className="card"><p style={{color:'var(--muted)'}}>No percentile data</p></div>

  const items = [
    ['Review Volume', ranks.review_volume],
    ['Review Score', ranks.review_score],
    ['Median Playtime', ranks.median_playtime],
    ['Sub-2h Ratio', ranks.sub2h_ratio],
    ['Peak CCU', ranks.peak_ccu],
  ]

  return (
    <div className="card">
      <h3 style={{ fontSize: '1rem', marginBottom: 4 }}>Cohort Comparison</h3>
      <p style={{ color: 'var(--muted)', fontSize: '.75rem', marginBottom: 12 }}>
        {cohort.cohort_size} games in ±{cohort.window_days}d window
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {items.map(([label, info]) => {
          if (!info) return null
          const pct = Math.min(100, Math.max(0, info.percentile || 50))
          const isHigh = pct > 50
          return (
            <div key={label}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2, fontSize: '.8rem' }}>
                <span>{label}</span>
                <span style={{ color: 'var(--text2)' }}>
                  <span style={{ fontWeight: 600, color: isHigh ? 'var(--green)' : pct < 50 ? 'var(--red)' : 'var(--amber)' }}>
                    {Math.round(pct)}th
                  </span>
                  &nbsp;· yours {typeof info.value === 'number' ? info.value.toLocaleString() : info.value} &nbsp;|&nbsp; median {info.cohort_median?.toLocaleString?.() || info.cohort_median}
                </span>
              </div>
              <div style={{ height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${pct}%`, background: isHigh ? 'var(--green)' : pct < 40 ? 'var(--red)' : 'var(--amber)', borderRadius: 2, transition: 'width 1s ease' }} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
