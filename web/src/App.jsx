import { useState, useCallback } from 'react'
import ScoreCard from './components/ScoreCard'
import ScoreBreakdown from './components/ScoreBreakdown'
import PlaytimeHistogram from './components/PlaytimeHistogram'
import CohortTable from './components/CohortTable'
import Recommendations from './components/Recommendations'
import ReviewPanel from './components/ReviewPanel'
import SentimentPanel from './components/SentimentPanel'
import BenchmarkBars from './components/BenchmarkBars'
import SeanEllisSurvey from './components/SeanEllisSurvey'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

export default function App() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [appId, setAppId] = useState('105600')

  const analyze = useCallback(async (e) => {
    e.preventDefault()
    if (!appId.trim()) return
    setLoading(true); setError(null); setData(null)
    try {
      const res = await fetch(`${API}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ app_id: parseInt(appId) }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Analysis failed')
      setData(await res.json())
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }, [appId])

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '40px 20px' }}>
      <header style={{ textAlign: 'center', marginBottom: 36 }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 800, background: 'linear-gradient(135deg, #6366f1, #818cf8, #10b981)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Game PMF Analyzer</h1>
        <p style={{ color: 'var(--text2)', marginTop: 6 }}>Post-launch signal report for indie games on Steam</p>
      </header>

      <form onSubmit={analyze} style={{ display: 'flex', gap: 10, maxWidth: 460, margin: '0 auto 40px' }}>
        <input value={appId} onChange={(e) => setAppId(e.target.value)} placeholder="Steam App ID (e.g. 105600)" style={{ flex: 1 }} />
        <button className="btn-primary" type="submit" disabled={loading}>{loading ? '...' : 'Analyze'}</button>
      </form>

      {error && <div className="card" style={{ borderColor: 'var(--red)', color: 'var(--red)', marginBottom: 24 }}>{error}</div>}
      {loading && <div style={{ textAlign: 'center', padding: 60 }}><div className="spinner" style={{ margin: '0 auto 16px' }} /><p style={{ color: 'var(--text2)' }}>Fetching data...</p></div>}

      {data && (
        <>
          <div style={{ marginBottom: 20 }}>
            <h2 style={{ fontSize: '1.5rem' }}>{data.game_name}</h2>
            <p style={{ color: 'var(--muted)', fontSize: '.85rem' }}>
              App {data.app_id} · {data.genres?.join(', ')} · Released {data.release_date || 'Unknown'}
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16, marginBottom: 16 }}>
            <ScoreCard lenses={data.lenses} label={data.label} />
            <ScoreBreakdown lenses={data.lenses} />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16, marginBottom: 16 }}>
            <PlaytimeHistogram engagement={data.lenses?.engagement} />
            <CohortTable cohort={data.cohort} />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16, marginBottom: 16 }}>
            <ReviewPanel reviews={data.reviews} />
            <SentimentPanel sentiment={data.sentiment} />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16, marginBottom: 16 }}>
            <BenchmarkBars benchmarks={data.benchmarks} lenses={data.lenses}
              medianMinutes={data.median_playtime_minutes} ccuCurrent={data.ccu_current} />
          </div>

          <Recommendations recs={data.recommendations} patchCount={data.patch_count} />
          <SeanEllisSurvey gameName={data.game_name} />
        </>
      )}
    </div>
  )
}
