import { useEffect, useMemo, useState } from 'react'
import Plot from 'react-plotly.js'
import { apiFetch } from '../api/client.js'

const Monitoring = () => {
  const [buildings, setBuildings] = useState([])
  const [building, setBuilding] = useState('')
  const [range, setRange] = useState(null)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [metric, setMetric] = useState('Energie')
  const [aggregation, setAggregation] = useState('Jour')
  const [showVacances, setShowVacances] = useState(true)
  const [tab, setTab] = useState('graphs')

  const [graphs, setGraphs] = useState(null)
  const [heatmap, setHeatmap] = useState(null)
  const [calendar, setCalendar] = useState(null)
  const [boxplots, setBoxplots] = useState(null)
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

  const query = useMemo(() => {
    if (!building || !startDate || !endDate) return null
    return `building=${encodeURIComponent(building)}&start_date=${startDate}&end_date=${endDate}`
  }, [building, startDate, endDate])

  useEffect(() => {
    if (!query || tab !== 'graphs') return
    const controller = new AbortController()
    apiFetch(
      `/monitoring/graphs?${query}&metric=${metric}&aggregation=${aggregation}&show_vacances=${showVacances}`,
      { signal: controller.signal },
    )
      .then(setGraphs)
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setError('Impossible de charger les graphiques.')
        }
      })
    return () => controller.abort()
  }, [query, metric, aggregation, showVacances, tab])

  useEffect(() => {
    if (!query || tab !== 'heatmap') return
    const controller = new AbortController()
    apiFetch(`/monitoring/heatmap?${query}`, { signal: controller.signal })
      .then(setHeatmap)
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setError('Impossible de charger la heatmap.')
        }
      })
    return () => controller.abort()
  }, [query, tab])

  useEffect(() => {
    if (!query || tab !== 'calendar') return
    const controller = new AbortController()
    apiFetch(`/monitoring/calendar?${query}`, { signal: controller.signal })
      .then(setCalendar)
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setError('Impossible de charger le calendar.')
        }
      })
    return () => controller.abort()
  }, [query, tab])

  useEffect(() => {
    if (!query || tab !== 'boxplots') return
    const controller = new AbortController()
    apiFetch(`/monitoring/boxplots?${query}`, { signal: controller.signal })
      .then(setBoxplots)
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setError('Impossible de charger les boxplots.')
        }
      })
    return () => controller.abort()
  }, [query, tab])

  if (error) {
    return <div className="panel error">{error}</div>
  }

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
        <div>
          <label>Mesure</label>
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
            <option value="Annee">Année</option>
          </select>
        </div>
        <div className="toggle">
          <label>Afficher vacances</label>
          <input
            type="checkbox"
            checked={showVacances}
            onChange={(e) => setShowVacances(e.target.checked)}
          />
        </div>
      </section>

      <section className="tabs">
        <button className={tab === 'graphs' ? 'active' : ''} onClick={() => setTab('graphs')}>
          Graphiques
        </button>
        <button className={tab === 'heatmap' ? 'active' : ''} onClick={() => setTab('heatmap')}>
          Heatmap
        </button>
        <button className={tab === 'calendar' ? 'active' : ''} onClick={() => setTab('calendar')}>
          Calendar
        </button>
        <button className={tab === 'boxplots' ? 'active' : ''} onClick={() => setTab('boxplots')}>
          Boxplots
        </button>
      </section>

      {tab === 'graphs' && graphs && (
        <section className="panel">
          <h3>Analyse temporelle</h3>
          <Plot
            data={[
              {
                type: 'scatter',
                mode: 'lines',
                x: graphs.series.map((p) => p.timestamp),
                y: graphs.series.map((p) => p.value),
                line: { color: '#1f77b4', width: 3 },
              },
            ]}
            layout={{
              height: 420,
              margin: { l: 50, r: 20, t: 10, b: 40 },
              paper_bgcolor: 'transparent',
              plot_bgcolor: 'transparent',
              font: { color: '#0c323c' },
              shapes: (graphs.vacances || []).map((v) => ({
                type: 'rect',
                x0: v.start,
                x1: v.end,
                y0: 0,
                y1: 1,
                yref: 'paper',
                fillcolor: 'rgba(255,0,0,0.1)',
                line: { width: 0 },
              })),
            }}
            config={{ displayModeBar: false }}
            style={{ width: '100%' }}
          />
        </section>
      )}

      {tab === 'heatmap' && heatmap && (
        <section className="panel">
          <h3>Heatmap temporelle</h3>
          <Plot
            data={[
              {
                type: 'heatmap',
                z: heatmap.values,
                x: heatmap.hours,
                y: heatmap.days,
                colorscale: 'Viridis',
              },
            ]}
            layout={{
              height: 420,
              margin: { l: 80, r: 20, t: 10, b: 40 },
              paper_bgcolor: 'transparent',
              plot_bgcolor: 'transparent',
              font: { color: '#0c323c' },
            }}
            config={{ displayModeBar: false }}
            style={{ width: '100%' }}
          />
        </section>
      )}

      {tab === 'calendar' && calendar && (
        <section className="panel">
          <h3>Distribution journalière</h3>
          <Plot
            data={[
              {
                type: 'scatter',
                mode: 'markers',
                x: calendar.daily.map((d) => d.date),
                y: calendar.daily.map((d) => d.value),
                marker: {
                  color: calendar.daily.map((d) => d.value),
                  colorscale: 'Viridis',
                  size: 10,
                },
              },
            ]}
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
          <div className="stats-row">
            <div>Jours analysés: {calendar.stats.days}</div>
            <div>Moyenne: {calendar.stats.mean.toFixed(1)} kWh</div>
            <div>Max: {calendar.stats.max.toFixed(1)} kWh</div>
            <div>Min: {calendar.stats.min.toFixed(1)} kWh</div>
          </div>
        </section>
      )}

      {tab === 'boxplots' && boxplots && (
        <section className="panel">
          <h3>Distribution par jour de semaine</h3>
          <Plot
            data={boxplots.days_order.map((day) => ({
              type: 'box',
              y: boxplots.series[day],
              name: day,
              boxpoints: false,
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
      )}
    </div>
  )
}

export default Monitoring
