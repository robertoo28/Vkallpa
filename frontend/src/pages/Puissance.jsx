import { useEffect, useState } from 'react'
import Plot from 'react-plotly.js'
import { apiFetch } from '../api/client.js'

const Puissance = () => {
  const [buildings, setBuildings] = useState([])
  const [building, setBuilding] = useState('')
  const [range, setRange] = useState(null)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
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
        setStartDate(res.min_date)
        setEndDate(res.max_date)
      })
      .catch(() => setError('Impossible de charger la période.'))
  }, [building])

  useEffect(() => {
    if (!building || !startDate || !endDate) return
    apiFetch(
      `/puissance?building=${encodeURIComponent(building)}&start_date=${startDate}&end_date=${endDate}`,
    )
      .then(setData)
      .catch(() => setError('Impossible de charger la puissance.'))
  }, [building, startDate, endDate])

  if (error) {
    return <div className="panel error">{error}</div>
  }

  if (!data) {
    return <div className="panel">Chargement...</div>
  }

  const dates = data.daily.map((d) => d.date)
  const values = data.daily.map((d) => d.puissance_max_kw)
  const threshold = data.threshold_kw

  return (
    <div className="page">
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
          <label>Début</label>
          <input
            type="date"
            value={startDate}
            min={range?.min_date || ''}
            max={range?.max_date || ''}
            onChange={(e) => setStartDate(e.target.value)}
          />
        </div>
        <div>
          <label>Fin</label>
          <input
            type="date"
            value={endDate}
            min={range?.min_date || ''}
            max={range?.max_date || ''}
            onChange={(e) => setEndDate(e.target.value)}
          />
        </div>
      </section>

      {data.alerts.count > 0 && (
        <section className="alert-banner">
          ⚠️ Dépassements de seuil détectés : {data.alerts.count} jours
        </section>
      )}

      <section className="panel">
        <h3>Puissance maximale journalière</h3>
        <Plot
          data={[
            {
              type: 'bar',
              x: dates,
              y: values,
              marker: {
                color: values.map((v) =>
                  threshold && v > threshold ? '#ff4444' : '#1f77b4',
                ),
              },
            },
          ]}
          layout={{
            height: 420,
            margin: { l: 50, r: 20, t: 10, b: 40 },
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            font: { color: '#0c323c' },
            shapes: threshold
              ? [
                  {
                    type: 'line',
                    x0: 0,
                    x1: 1,
                    xref: 'paper',
                    y0: threshold,
                    y1: threshold,
                    line: { color: 'red', dash: 'dash' },
                  },
                ]
              : [],
          }}
          config={{ displayModeBar: false }}
          style={{ width: '100%' }}
        />
      </section>

      <section className="kpi-grid">
        <div className="kpi">
          <p>Puissance moyenne</p>
          <strong>{data.stats.avg_power_kw.toFixed(2)} kW</strong>
        </div>
        <div className="kpi">
          <p>Puissance maximale</p>
          <strong>{data.stats.max_power_kw.toFixed(2)} kW</strong>
        </div>
        <div className="kpi">
          <p>Heure de pic fréquente</p>
          <strong>{data.stats.most_common_peak_hour ?? 'N/A'}</strong>
        </div>
        <div className="kpi">
          <p>Taux de conformité</p>
          <strong>{data.stats.conformity_rate_pct.toFixed(1)}%</strong>
        </div>
      </section>
    </div>
  )
}

export default Puissance
