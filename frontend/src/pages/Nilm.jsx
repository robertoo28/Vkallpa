import { useEffect, useState } from 'react'
import Plot from 'react-plotly.js'
import { apiFetch } from '../api/client.js'

const Nilm = () => {
  const [buildings, setBuildings] = useState([])
  const [building, setBuilding] = useState('')
  const [range, setRange] = useState(null)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [aggregation, setAggregation] = useState('Jour')
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

  const handleRun = async () => {
    try {
      const res = await apiFetch('/ia/nilm', {
        method: 'POST',
        body: JSON.stringify({
          building,
          start_date: startDate,
          end_date: endDate,
          aggregation,
        }),
      })
      setData(res)
    } catch {
      setError('Impossible de lancer la simulation NILM.')
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
          <label>Agrégation</label>
          <select value={aggregation} onChange={(e) => setAggregation(e.target.value)}>
            <option value="Heure">Heure</option>
            <option value="Jour">Jour</option>
            <option value="Semaine">Semaine</option>
            <option value="Mois">Mois</option>
          </select>
        </div>
        <button className="btn-primary" onClick={handleRun}>
          Lancer la simulation
        </button>
      </section>

      {data && (
        <>
          <section className="panel">
            <h3>Consommation totale</h3>
            <Plot
              data={[
                {
                  type: 'scatter',
                  mode: 'lines',
                  name: 'Total',
                  x: data.total_series.map((p) => p.timestamp),
                  y: data.total_series.map((p) => p.value),
                  line: { color: '#000', width: 3 },
                },
                {
                  type: 'scatter',
                  mode: 'lines',
                  name: 'Reconstruction',
                  x: data.reconstruction_series.map((p) => p.timestamp),
                  y: data.reconstruction_series.map((p) => p.value),
                  line: { color: '#ff4444', width: 2, dash: 'dot' },
                },
              ]}
              layout={{
                height: 400,
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
            <h3>Décomposition par composante</h3>
            <Plot
              data={data.components.map((comp) => ({
                type: 'scatter',
                mode: 'lines',
                name: comp.name,
                x: comp.series.map((p) => p.timestamp),
                y: comp.series.map((p) => p.value),
                line: { color: comp.color },
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
            <h3>Répartition par composante</h3>
            <Plot
              data={[
                {
                  type: 'pie',
                  labels: data.stats.components.map((c) => c.name),
                  values: data.stats.components.map((c) => c.total_kwh),
                  hole: 0.4,
                },
              ]}
              layout={{
                height: 360,
                margin: { l: 20, r: 20, t: 10, b: 10 },
                paper_bgcolor: 'transparent',
                font: { color: '#0c323c' },
              }}
              config={{ displayModeBar: false }}
              style={{ width: '100%' }}
            />
          </section>
        </>
      )}
    </div>
  )
}

export default Nilm
