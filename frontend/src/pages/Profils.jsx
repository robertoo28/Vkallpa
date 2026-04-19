import { useEffect, useState } from 'react'
import Plot from 'react-plotly.js'
import { apiFetch } from '../api/client.js'

const Profils = () => {
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
      `/profils?building=${encodeURIComponent(building)}&start_date=${startDate}&end_date=${endDate}`,
    )
      .then(setData)
      .catch(() => setError('Impossible de charger les profils.'))
  }, [building, startDate, endDate])

  if (error) {
    return <div className="panel error">{error}</div>
  }

  if (!data) {
    return <div className="panel">Chargement...</div>
  }

  const daily = data.profiles.daily_profile || []
  const weeklyMonth = data.profiles.weekly_month_profile || []
  const monthlyYear = data.profiles.monthly_year_profile || []

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

      <section className="panel">
        <h3>Profil énergétique 24h</h3>
        <Plot
          data={Array.from(
            new Set(daily.map((d) => d.Jour_Semaine)),
          ).map((day) => ({
            type: 'scatter',
            mode: 'lines+markers',
            name: day,
            x: daily.filter((d) => d.Jour_Semaine === day).map((d) => d.Heure),
            y: daily.filter((d) => d.Jour_Semaine === day).map((d) => d.Energie_periode_kWh),
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

      <section className="grid-2">
        <div className="panel">
          <h3>Profil hebdomadaire par mois</h3>
          <Plot
            data={Array.from(new Set(weeklyMonth.map((d) => d.Mois))).map((month) => ({
              type: 'scatter',
              mode: 'lines+markers',
              name: month,
              x: weeklyMonth.filter((d) => d.Mois === month).map((d) => d.Jour_Semaine),
              y: weeklyMonth.filter((d) => d.Mois === month).map((d) => d.Energie_periode_kWh),
            }))}
            layout={{
              height: 360,
              margin: { l: 50, r: 20, t: 10, b: 40 },
              paper_bgcolor: 'transparent',
              plot_bgcolor: 'transparent',
              font: { color: '#0c323c' },
            }}
            config={{ displayModeBar: false }}
            style={{ width: '100%' }}
          />
        </div>
        <div className="panel">
          <h3>Profil mensuel par année</h3>
          <Plot
            data={Array.from(new Set(monthlyYear.map((d) => d.Annee))).map((year) => ({
              type: 'scatter',
              mode: 'lines+markers',
              name: year,
              x: monthlyYear.filter((d) => d.Annee === year).map((d) => d.Mois),
              y: monthlyYear.filter((d) => d.Annee === year).map((d) => d.Energie_periode_kWh),
            }))}
            layout={{
              height: 360,
              margin: { l: 50, r: 20, t: 10, b: 40 },
              paper_bgcolor: 'transparent',
              plot_bgcolor: 'transparent',
              font: { color: '#0c323c' },
            }}
            config={{ displayModeBar: false }}
            style={{ width: '100%' }}
          />
        </div>
      </section>
    </div>
  )
}

export default Profils
