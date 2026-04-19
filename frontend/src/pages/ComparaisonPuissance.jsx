import { useEffect, useState } from 'react'
import Plot from 'react-plotly.js'
import { apiFetch } from '../api/client.js'

const ComparaisonPuissance = () => {
  const [buildings, setBuildings] = useState([])
  const [building, setBuilding] = useState('')
  const [range, setRange] = useState(null)
  const [referenceDate, setReferenceDate] = useState('')
  const [comparisons, setComparisons] = useState(['', '', '', ''])
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    apiFetch('/buildings')
      .then((res) => {
        setBuildings(res.items)
        if (res.items.length) {
          setBuilding(res.items[0].id)
        }
      })
      .catch(() => setError('Impossible de charger les bâtiments.'))
  }, [])

  useEffect(() => {
    if (!building) return
    apiFetch(`/buildings/${encodeURIComponent(building)}/range`)
      .then((res) => {
        setRange(res)
        setReferenceDate(res.max_date)
      })
      .catch(() => setError('Impossible de charger la période.'))
  }, [building])

  const handleCompare = async () => {
    if (!referenceDate) return
    const params = new URLSearchParams()
    params.append('building', building)
    params.append('reference_date', referenceDate)
    comparisons.filter(Boolean).forEach((d) => params.append('comparison_dates', d))
    try {
      const res = await apiFetch(`/monitoring/comparaison-puissance?${params.toString()}`)
      setData(res)
    } catch (err) {
      setError('Impossible de comparer les jours.')
    }
  }

  return (
    <div className="page">
      {error && <div className="panel error">{error}</div>}

      <section className="panel filters">
        <div>
          <label>Bâtiment</label>
          <select value={building} onChange={(e) => setBuilding(e.target.value)}>
            {buildings.map((b) => (
              <option key={b.id} value={b.id}>
                {b.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label>Jour de référence</label>
          <input
            type="date"
            value={referenceDate}
            min={range?.min_date || ''}
            max={range?.max_date || ''}
            onChange={(e) => setReferenceDate(e.target.value)}
          />
        </div>
        <button className="btn-primary" onClick={handleCompare}>
          Comparer
        </button>
      </section>

      <section className="panel grid-2">
        {comparisons.map((value, idx) => (
          <div key={idx}>
            <label>Jour {idx + 2}</label>
            <input
              type="date"
              value={value}
              min={range?.min_date || ''}
              max={range?.max_date || ''}
              onChange={(e) => {
                const next = [...comparisons]
                next[idx] = e.target.value
                setComparisons(next)
              }}
            />
          </div>
        ))}
      </section>

      {data && (
        <section className="panel">
          <h3>Comparaison Puissance Journalière</h3>
          <Plot
            data={data.series.map((series) => ({
              type: 'scatter',
              mode: 'lines+markers',
              name: series.date,
              x: series.points.map((p) => p.hour_float),
              y: series.points.map((p) => p.power_kw),
            }))}
            layout={{
              height: 420,
              margin: { l: 50, r: 20, t: 10, b: 40 },
              paper_bgcolor: 'transparent',
              plot_bgcolor: 'transparent',
              font: { color: '#0c323c' },
              xaxis: {
                tickmode: 'linear',
                tick0: 0,
                dtick: 2,
              },
            }}
            config={{ displayModeBar: false }}
            style={{ width: '100%' }}
          />
        </section>
      )}
    </div>
  )
}

export default ComparaisonPuissance
