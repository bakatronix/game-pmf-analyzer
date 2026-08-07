import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const BARS = ['#ef4444', '#f97316', '#f59e0b', '#84cc16', '#10b981']

export default function PlaytimeHistogram({ engagement }) {
  if (!engagement) return <div className="card"><p style={{color:'var(--muted)'}}>No playtime data</p></div>
  const b = engagement.playtime_buckets
  if (!b) return <div className="card"><p style={{color:'var(--muted)'}}>No playtime distribution</p></div>

  const data = [
    { name: '<1h', value: b.sub_1h || 0 },
    { name: '1-2h', value: b["1h_to_2h"] || 0 },
    { name: '2-5h', value: b["2h_to_5h"] || 0 },
    { name: '5-20h', value: b["5h_to_20h"] || 0 },
    { name: '20h+', value: b["20h_plus"] || 0 },
  ]

  return (
    <div className="card">
      <h3 style={{ fontSize: '1rem', marginBottom: 4 }}>Playtime Distribution</h3>
      <p style={{ color: 'var(--muted)', fontSize: '.75rem', marginBottom: 12 }}>
        Refund-window signal: {engagement.sub2h_ratio}% of sampled players under 2h
        &nbsp;·&nbsp; Median {engagement.median_hr}h
      </p>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} barSize={44}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="name" tick={{ fill: 'var(--text2)', fontSize: 11 }} />
          <YAxis tick={{ fill: 'var(--text2)', fontSize: 11 }} unit="%" />
          <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)' }} formatter={v => [`${v}%`]} />
          <Bar dataKey="value" radius={[6,6,0,0]}>
            {data.map((_, i) => <Cell key={i} fill={BARS[i]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p style={{ color: 'var(--muted)', fontSize: '.65rem', marginTop: 8 }}>
        Sampled from review playtimes. True sub-2h ratio likely higher (reviewers skew engaged).
      </p>
    </div>
  )
}
