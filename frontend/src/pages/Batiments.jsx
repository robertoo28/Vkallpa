import { useEffect, useState } from 'react'
import Plot from 'react-plotly.js'
import { apiFetch } from '../api/client.js'

const Batiments = () => {
  const [buildings, setBuildings] = useState([])
  const [selected, setSelected] = useState([])
  const [range, setRange] = useState(null)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [metric, setMetric] = useState('Energie')
  const [aggregation, setAggregation] = useState('Jour')
  const [normalize, setNormalize] = useState(false)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    apiFetch('/buildings')
      .then((res) => {
        setBuildings(res.items)
        const initial = res.items.slice(0, 2).map((b) => b.id)
        setSelected(initial)
        if (res.items.length) {
          return apiFetch(`/buildings/${encodeURIComponent(res.items[0].id)}/range`)
        }
        return null
      })
      .then((res) => {
        if (!res) return
        setRange(res)
        setStartDate(res.min_date)
        setEndDate(res.max_date)
      })
      .catch(() => setError('Impossible de charger les bâtiments.'))
  }, [])

  const handleCompare = async () => {
    if (!selected.length || !startDate || !endDate) return
    const params = new URLSearchParams()
    selected.forEach((b) => params.append('buildings', b))
    params.append('start_date', startDate)
    params.append('end_date', endDate)
    params.append('metric', metric)
    params.append('aggregation', aggregation)
    params.append('normalize', normalize)
    try {
      const res = await apiFetch(`/traitement/batiments?${params.toString()}`)
      setData(res)
    } catch {
      setError('Impossible de charger la comparaison.')
    }
  }

  return (
    <div className="page">
      {error && <div className="panel error">{error}</div>}

      <section className="panel filters">
        <div>
          <label>Bâtiments (multi)</label>
          <select
            multiple
            value={selected}
            onChange={(e) =>
              setSelected(Array.from(e.target.selectedOptions, (opt) => opt.value))
            }
          >
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
        <div>
          <label>Métrique</label>
          <select value={metric} onChange={(e) => setMetric(e.target.value)}>
            <option value="Energie">Energie</option>
            <option value="Puissance">Puissance</option>
          </select>
        </div>
        <div>
          <label>Agrégation</label>
          <select value={aggregation} onChange={(e) => setAggregation(e.target.value)}>
            <option value="Heure">Heure</option>
            <option value="Jour">Jour</option>
            <option value="Semaine">Semaine</option>
            <option value="Mois">Mois</option>
          </select>
        </div>
        <div className="toggle">
          <label>Normaliser</label>
          <input
            type="checkbox"
            checked={normalize}
            onChange={(e) => setNormalize(e.target.checked)}
          />
        </div>
        <button className="btn-primary" onClick={handleCompare}>
          Comparer
        </button>
      </section>

      {data && (
        <>
          {data.missing_superficies.length > 0 && (
            <section className="panel warning">
              Superficies manquantes: {data.missing_superficies.join(', ')}
            </section>
          )}
          <section className="panel">
            <h3>Analyse temporelle comparative</h3>
            <Plot
              data={data.series.map((serie) => ({
                type: 'scatter',
                mode: 'lines+markers',
                name: serie.label,
                x: serie.points.map((p) => p.timestamp),
                y: serie.points.map((p) => p.value),
              }))}
              layout={{
                height: 420,
                margin: { l: 50, r: 20, t: 10, b: 40 },
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                font: { color: '#0c323c' },
              }}
              config={{ displayModeBar: false }}
              style={{ width: '100%' }}
            />
          </section>
          <section className="panel">
            <h3>Insights</h3>
            <div className="table">
              <div className="table-row table-header">
                <span>Bâtiment</span>
                <span>Total</span>
                <span>Moyenne</span>
                <span>Puissance moy</span>
                <span>Superficie</span>
              </div>
              {data.insights.ranked.map((row) => (
                <div key={row.label} className="table-row">
                  <span>{row.label}</span>
                  <span>{row.total_energy.toFixed(2)}</span>
                  <span>{row.mean_energy.toFixed(2)}</span>
                  <span>{row.mean_power.toFixed(2)} kW</span>
                  <span>{row.superficie ?? 'N/A'}</span>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  )
}

export default Batiments
