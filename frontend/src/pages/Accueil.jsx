import { useEffect, useState } from 'react'
import { apiFetch } from '../api/client.js'

const Accueil = () => {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    apiFetch('/accueil/summary')
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

  return (
    <div className="page">
      <section className="hero-card">
        <h2>Tableau de consommation énergétique</h2>
        <div className="hero-metric">
          <div>
            <p>Consommation Annuelle Totale</p>
            <strong>{formatNumber(data.total_annual_kwh)} kWh</strong>
          </div>
          <span className="hero-icon">⚡</span>
        </div>
        <div className="hero-stats">
          <div>
            <p>Mensuelle moyenne</p>
            <strong>{formatNumber(data.monthly_avg_kwh)} kWh</strong>
          </div>
          <div>
            <p>Quotidienne moyenne</p>
            <strong>{formatNumber(data.daily_avg_kwh)} kWh</strong>
          </div>
          <div>
            <p>Coût estimé annuel</p>
            <strong>{formatNumber(data.estimated_cost_eur)} €</strong>
          </div>
        </div>
      </section>

      <section className="panel">
        <h3>Classement détaillé des bâtiments</h3>
        <div className="table">
          <div className="table-row table-header">
            <span>Bâtiment</span>
            <span>Consommation annuelle (kWh)</span>
          </div>
          {data.table.map((row, idx) => (
            <div
              key={`${row.building}-${idx}`}
              className={`table-row level-${row.level}`}
            >
              <span>
                {row.level === 0 ? '🏢 ' : '⚡ '}
                {row.building}
              </span>
              <span>{formatNumber(row.consumption_kwh)}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

export default Accueil
