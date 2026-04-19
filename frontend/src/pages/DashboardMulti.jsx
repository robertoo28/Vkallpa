import { useEffect, useState } from 'react'
import Plot from 'react-plotly.js'
import { apiFetch } from '../api/client.js'

const DashboardMulti = () => {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    apiFetch('/dashboard-multi/summary')
      .then(setData)
      .catch(() => setError('Impossible de charger les données.'))
  }, [])

  if (error) {
    return <div className="panel error">{error}</div>
  }

  if (!data) {
    return <div className="panel">Chargement...</div>
  }

  const formatNumber = (value) => {
    return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 }).format(value)
  }

  const buildings = data.charts.consumption_by_building || []
  const usage = data.charts.usage_distribution || []
  const hours = data.charts.hours_distribution || []
  const fluids = data.charts.fluid_distribution || []

  return (
    <div className="page">
      <section className="kpi-grid">
        <div className="kpi">
          <p>Total</p>
          <strong>{formatNumber(data.kpis.total_kwh)} kWh</strong>
        </div>
        <div className="kpi">
          <p>Electricité</p>
          <strong>{formatNumber(data.kpis.total_electric_kwh)} kWh</strong>
        </div>
        <div className="kpi">
          <p>Thermique</p>
          <strong>{formatNumber(data.kpis.total_thermique_kwh)} kWh</strong>
        </div>
        <div className="kpi">
          <p>Compteurs</p>
          <strong>{data.kpis.nb_compteurs}</strong>
        </div>
      </section>

      <section className="grid-3">
        <div className="panel">
          <h3>Consommation par bâtiment</h3>
          <Plot
            data={[
              {
                type: 'bar',
                orientation: 'h',
                x: buildings.map((b) => b.kwh),
                y: buildings.map((b) => b.batiment),
                marker: { color: '#b9ce0e' },
              },
            ]}
            layout={{
              margin: { l: 80, r: 20, t: 10, b: 40 },
              height: 260,
              paper_bgcolor: 'transparent',
              plot_bgcolor: 'transparent',
              font: { color: '#0c323c' },
            }}
            config={{ displayModeBar: false }}
            style={{ width: '100%' }}
          />
        </div>
        <div className="panel">
          <h3>Consommation par usage</h3>
          <Plot
            data={[
              {
                type: 'bar',
                orientation: 'h',
                x: usage.map((u) => u.kwh),
                y: usage.map((u) => u.usage),
                marker: { color: '#e18222' },
              },
            ]}
            layout={{
              margin: { l: 80, r: 20, t: 10, b: 40 },
              height: 260,
              paper_bgcolor: 'transparent',
              plot_bgcolor: 'transparent',
              font: { color: '#0c323c' },
            }}
            config={{ displayModeBar: false }}
            style={{ width: '100%' }}
          />
        </div>
        <div className="panel">
          <h3>Heures ouvrées vs hors heures</h3>
          <Plot
            data={[
              {
                type: 'pie',
                values: hours.map((h) => h.kwh),
                labels: hours.map((h) => h.label),
                hole: 0.55,
                marker: { colors: ['#b9ce0e', '#e18222'] },
              },
            ]}
            layout={{
              margin: { l: 10, r: 10, t: 10, b: 10 },
              height: 260,
              paper_bgcolor: 'transparent',
              font: { color: '#0c323c' },
              showlegend: true,
            }}
            config={{ displayModeBar: false }}
            style={{ width: '100%' }}
          />
        </div>
      </section>

      <section className="panel">
        <h3>Répartition par fluide</h3>
        <Plot
          data={[
            {
              type: 'pie',
              values: fluids.map((f) => f.kwh),
              labels: fluids.map((f) => f.fluide),
              hole: 0.5,
              marker: {
                colors: ['#b9ce0e', '#e18222', '#0c323c', '#ffcc00', '#ff6b6b'],
              },
            },
          ]}
          layout={{
            margin: { l: 10, r: 10, t: 10, b: 10 },
            height: 320,
            paper_bgcolor: 'transparent',
            font: { color: '#0c323c' },
            showlegend: true,
          }}
          config={{ displayModeBar: false }}
          style={{ width: '100%' }}
        />
      </section>

      <section className="panel">
        <h3>Synthèse des compteurs principaux</h3>
        <div className="table">
          <div className="table-row table-header">
            <span>Compteur principal</span>
            <span>Bâtiment</span>
            <span>Fluide</span>
            <span>Usage</span>
            <span>Consommation</span>
          </div>
          {data.table.map((row, idx) => (
            <div key={`${row.compteur}-${idx}`} className="table-row">
              <span>{row.compteur}</span>
              <span>{row.batiment}</span>
              <span>{row.fluide}</span>
              <span>{row.usage}</span>
              <span>{formatNumber(row.consommation_kwh)} kWh</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

export default DashboardMulti
