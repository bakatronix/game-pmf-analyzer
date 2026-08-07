import { useState, useEffect } from 'react'

export default function SeanEllisSurvey({ gameName }) {
  const [results, setResults] = useState(null)
  const [selected, setSelected] = useState(null)
  const [submitted, setSubmitted] = useState(false)

  const KEY = 'pmf_survey_' + (gameName || 'unknown')

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(KEY))
      if (saved) { setResults(saved); setSubmitted(true) }
    } catch {}
  }, [KEY])

  const handleSubmit = () => {
    if (!selected) return
    const existing = { very: 0, somewhat: 0, not: 0 }
    try {
      const saved = JSON.parse(localStorage.getItem(KEY))
      if (saved) { existing.very = saved.very; existing.somewhat = saved.somewhat; existing.not = saved.not }
    } catch {}
    if (selected === 'Very disappointed') existing.very++
    else if (selected === 'Somewhat disappointed') existing.somewhat++
    else existing.not++
    const total = existing.very + existing.somewhat + existing.not
    const pct = total > 0 ? Math.round(existing.very / total * 100) : 0
    const newResults = { ...existing, total, very_pct: pct, pmf: pct >= 40 }
    localStorage.setItem(KEY, JSON.stringify(newResults))
    setResults(newResults)
    setSubmitted(true)
  }

  const total = results?.total || 0
  const veryPct = results?.very_pct || 0

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 style={{ fontSize: '1rem', marginBottom: 4 }}>Sean Ellis Test</h3>
      <p style={{ color: 'var(--muted)', fontSize: '.8rem', marginBottom: 14 }}>
        How would you feel if you could no longer play {gameName}?
      </p>

      {!submitted ? (
        <div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 12 }}>
            {['Very disappointed', 'Somewhat disappointed', 'Not disappointed'].map(o => (
              <label key={o} style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px',
                background: selected === o ? 'rgba(99,102,241,.08)' : 'var(--bg2)',
                border: `1px solid ${selected === o ? 'var(--accent)' : 'var(--border)'}`,
                borderRadius: 8, cursor: 'pointer', fontSize: '.85rem',
              }}>
                <input type="radio" name="se" checked={selected === o} onChange={() => setSelected(o)}
                  style={{ accentColor: 'var(--accent)' }} />
                {o}
              </label>
            ))}
          </div>
          <button className="btn-primary" onClick={handleSubmit} disabled={!selected}
            style={{ width: '100%' }}>Submit</button>
        </div>
      ) : (
        <div>
          {total > 0 && (
            <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
              {[
                ['Very', results.very, 'var(--green)'],
                ['Somewhat', results.somewhat, 'var(--amber)'],
                ['Not', results.not, 'var(--red)'],
              ].map(([l, v, c]) => (
                <div key={l} style={{ flex: 1, textAlign: 'center', background: 'var(--bg2)', borderRadius: 8, padding: '8px 4px' }}>
                  <div style={{ fontWeight: 700, color: c, fontSize: '1.1rem' }}>{v}</div>
                  <div style={{ color: 'var(--muted)', fontSize: '.65rem' }}>{l}</div>
                </div>
              ))}
            </div>
          )}
          <div style={{ height: 8, background: 'var(--border)', borderRadius: 4, overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${veryPct}%`, background: veryPct >= 40 ? 'var(--green)' : 'var(--amber)', borderRadius: 4, transition: 'width .5s ease' }} />
          </div>
          <p style={{ color: 'var(--muted)', fontSize: '.7rem', marginTop: 6, textAlign: 'center' }}>
            {veryPct}% "Very disappointed" — {veryPct >= 40 ? 'Above the 40% PMF threshold' : 'Below the 40% PMF threshold'}
            {total > 0 ? ` (${total} responses)` : ''}
          </p>
        </div>
      )}
    </div>
  )
}
