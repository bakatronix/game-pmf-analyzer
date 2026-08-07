export default function BenchmarkBars({ benchmarks, lenses, medianMinutes, ccuCurrent }) {
  if (!benchmarks) return <div className="card"><p style={{color:'var(--muted)'}}>No benchmark data</p></div>

  const items = [
    { label: 'Review Score', value: lenses?.satisfaction?.positive_pct || 0, max: 100, bm: benchmarks.avg_review_score || 0, unit: '%' },
    { label: 'Median Playtime', value: (medianMinutes || 0) / 60, max: 60, bm: benchmarks.median_playtime_hours || 0, unit: 'h', format: v => v.toFixed(1) + 'h' },
    { label: 'Peak CCU', value: Math.min(ccuCurrent || 0, 5000), max: 5000, bm: Math.min(benchmarks.avg_ccu || 0, 5000), unit: '', format: v => v >= 1000 ? (v/1000).toFixed(1)+'k' : v },
    { label: 'Total Reviews', value: Math.min(lenses?.reach?.total_reviews || 0, 15000), max: 15000, bm: Math.min(benchmarks.avg_total_reviews || 0, 15000), unit: '', format: v => v >= 1000 ? (v/1000).toFixed(1)+'k' : v },
    { label: 'Achievements', value: lenses?.engagement?.deepest_ach_pct ? (100 - lenses.engagement.deepest_ach_pct) * 0.5 : 0, max: 100, bm: benchmarks.avg_achievement_completion || 0, unit: '', format: v => Math.round(v) + '' },
  ]

  return (
    <div className="card">
      <h3 style={{ fontSize: '1rem', marginBottom: 4 }}>Genre Benchmark Comparison</h3>
      <p style={{ color: 'var(--muted)', fontSize: '.75rem', marginBottom: 14 }}>vs. {benchmarks.genre} benchmark</p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {items.map(m => {
          const pct = m.max > 0 ? (m.value / m.max * 100) : 0
          const bmPct = m.max > 0 ? (m.bm / m.max * 100) : 0
          const fmt = m.format || (v => Math.round(v) + m.unit)
          return (
            <div key={m.label}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3, fontSize: '.78rem' }}>
                <span>{m.label}</span>
                <span style={{ color: 'var(--text2)' }}>{fmt(m.value)} / benchmark {fmt(m.bm)}</span>
              </div>
              <div style={{ height: 6, background: 'var(--border)', borderRadius: 3, position: 'relative', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${pct}%`, background: 'var(--accent)', borderRadius: 3, transition: 'width 1s ease' }} />
                <div style={{ position: 'absolute', top: -1, left: `${bmPct}%`, width: 3, height: 8, background: 'var(--amber)', borderRadius: 2 }} />
              </div>
            </div>
          )
        })}
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 10, fontSize: '.65rem', color: 'var(--muted)' }}>
        <span>■ Your game</span><span>■ Benchmark</span>
      </div>
    </div>
  )
}
