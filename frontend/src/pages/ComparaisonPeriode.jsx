import { useEffect, useState } from 'react'
import { apiFetch } from '../api/client.js'

const ComparaisonPeriode = () => {
  const [buildings, setBuildings] = useState([])
  const [building, setBuilding] = useState('')
  const [range, setRange] = useState(null)
  const [metric, setMetric] = useState('Energie')
  const [startA, setStartA] = useState('')
  const [endA, setEndA] = useState('')
  const [startB, setStartB] = useState('')
  const [endB, setEndB] = useState('')
  const [normalize, setNormalize] = useState(true)
  const [excludeWeekends, setExcludeWeekends] = useState(false)
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
        setStartA(res.min_date)
        setEndA(res.min_date)
        setStartB(res.max_date)
        setEndB(res.max_date)
      })
      .catch(() => setError('Impossible de charger la période.'))
  }, [building])

  const handleCompare = async () => {
    setError(null)
    try {
      const res = await apiFetch(
        `/traitement/comparaison-periode?building=${encodeURIComponent(
          building,
        )}&start_a=${startA}&end_a=${endA}&start_b=${startB}&end_b=${endB}&metric=${metric}&normalize_days=${normalize}&exclude_weekends=${excludeWeekends}`,
      )
      setData(res)
    } catch {
      setError('Impossible de comparer les périodes.')
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
          <label>Métrique</label>
          <select value={metric} onChange={(e) => setMetric(e.target.value)}>
            <option value="Energie">Energie</option>
            <option value="Puissance">Puissance</option>
          </select>
        </div>
        <div className="toggle">
          <label>Normaliser jours</label>
          <input
            type="checkbox"
            checked={normalize}
            onChange={(e) => setNormalize(e.target.checked)}
          />
        </div>
        <div className="toggle">
          <label>Exclure weekends</label>
          <input
            type="checkbox"
            checked={excludeWeekends}
            onChange={(e) => setExcludeWeekends(e.target.checked)}
          />
        </div>
      </section>

      <section className="panel filters">
        <div>
          <label>Début A</label>
          <input
            type="date"
            value={startA}
            min={range?.min_date || ''}
            max={range?.max_date || ''}
            onChange={(e) => setStartA(e.target.value)}
          />
        </div>
        <div>
          <label>Fin A</label>
          <input
            type="date"
            value={endA}
            min={range?.min_date || ''}
            max={range?.max_date || ''}
            onChange={(e) => setEndA(e.target.value)}
          />
        </div>
        <div>
          <label>Début B</label>
          <input
            type="date"
            value={startB}
            min={range?.min_date || ''}
            max={range?.max_date || ''}
            onChange={(e) => setStartB(e.target.value)}
          />
        </div>
        <div>
          <label>Fin B</label>
          <input
            type="date"
            value={endB}
            min={range?.min_date || ''}
            max={range?.max_date || ''}
            onChange={(e) => setEndB(e.target.value)}
          />
        </div>
        <button className="btn-primary" onClick={handleCompare}>
          Comparer
        </button>
      </section>

      {data?.metrics && (
        <section className="panel">
          <h3>Résultats</h3>
          <div className="kpi-grid">
            <div className="kpi">
              <p>Évolution totale</p>
              <strong>{data.metrics.total_evolution_pct.toFixed(1)}%</strong>
            </div>
            <div className="kpi">
              <p>Évolution moy/jour</p>
              <strong>{data.metrics.avg_daily_evolution_pct.toFixed(1)}%</strong>
            </div>
            <div className="kpi">
              <p>Évolution pic max</p>
              <strong>{data.metrics.max_evolution_pct.toFixed(1)}%</strong>
            </div>
          </div>
          <div className="table">
            <div className="table-row table-header">
              <span>Métrique</span>
              <span>{data.metrics.names[0]}</span>
              <span>{data.metrics.names[1]}</span>
            </div>
            <div className="table-row">
              <span>Consommation totale</span>
              <span>{data.metrics.total_consumption[0].toFixed(0)}</span>
              <span>{data.metrics.total_consumption[1].toFixed(0)}</span>
            </div>
            <div className="table-row">
              <span>Moyenne journalière</span>
              <span>{data.metrics.avg_daily_consumption[0].toFixed(0)}</span>
              <span>{data.metrics.avg_daily_consumption[1].toFixed(0)}</span>
            </div>
            <div className="table-row">
              <span>Pic maximum</span>
              <span>{data.metrics.max_consumption[0].toFixed(0)}</span>
              <span>{data.metrics.max_consumption[1].toFixed(0)}</span>
            </div>
          </div>
        </section>
      )}
    </div>
  )
}

export default ComparaisonPeriode
