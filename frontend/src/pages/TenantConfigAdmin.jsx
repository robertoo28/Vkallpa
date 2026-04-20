import { useEffect, useMemo, useState } from 'react'

import { apiFetch } from '../api/client.js'
import { useAuth } from '../auth/AuthContext.jsx'

const defaultConfig = {
  general: {
    timezone: 'America/Guayaquil',
    language: 'es',
    currency: 'USD',
  },
  energy: {
    tariff_per_kwh: 0.12,
    carbon_factor_kg_per_kwh: 0.25,
    energy_unit: 'kWh',
  },
  alerts: {
    enabled: true,
    consumption_threshold_kwh: 5000,
    anomaly_notifications: true,
  },
  reports: {
    default_period: 'monthly',
    default_format: 'pdf',
    include_carbon: true,
  },
}

const configCategories = [
  {
    key: 'general',
    label: 'General',
    fields: [
      {
        key: 'timezone',
        label: 'Zona horaria',
        type: 'select',
        options: [
          { value: 'America/Guayaquil', label: 'America/Guayaquil' },
          { value: 'America/Lima', label: 'America/Lima' },
          { value: 'America/Bogota', label: 'America/Bogota' },
          { value: 'UTC', label: 'UTC' },
        ],
      },
      {
        key: 'language',
        label: 'Idioma',
        type: 'select',
        options: [
          { value: 'es', label: 'Espanol' },
          { value: 'en', label: 'English' },
          { value: 'fr', label: 'Francais' },
        ],
      },
      {
        key: 'currency',
        label: 'Moneda',
        type: 'select',
        options: [
          { value: 'USD', label: 'USD' },
          { value: 'EUR', label: 'EUR' },
          { value: 'COP', label: 'COP' },
          { value: 'PEN', label: 'PEN' },
          { value: 'CLP', label: 'CLP' },
        ],
      },
    ],
  },
  {
    key: 'energy',
    label: 'Energia',
    fields: [
      {
        key: 'tariff_per_kwh',
        label: 'Tarifa por kWh',
        type: 'number',
        step: '0.01',
      },
      {
        key: 'carbon_factor_kg_per_kwh',
        label: 'Factor carbono kg/kWh',
        type: 'number',
        step: '0.01',
      },
      {
        key: 'energy_unit',
        label: 'Unidad energetica',
        type: 'select',
        options: [
          { value: 'kWh', label: 'kWh' },
          { value: 'MWh', label: 'MWh' },
        ],
      },
    ],
  },
  {
    key: 'alerts',
    label: 'Alertas',
    fields: [
      { key: 'enabled', label: 'Alertas activas', type: 'checkbox' },
      {
        key: 'consumption_threshold_kwh',
        label: 'Umbral consumo kWh',
        type: 'number',
        step: '1',
      },
      {
        key: 'anomaly_notifications',
        label: 'Notificar anomalias',
        type: 'checkbox',
      },
    ],
  },
  {
    key: 'reports',
    label: 'Reportes',
    fields: [
      {
        key: 'default_period',
        label: 'Periodo predeterminado',
        type: 'select',
        options: [
          { value: 'daily', label: 'Diario' },
          { value: 'weekly', label: 'Semanal' },
          { value: 'monthly', label: 'Mensual' },
        ],
      },
      {
        key: 'default_format',
        label: 'Formato predeterminado',
        type: 'select',
        options: [
          { value: 'pdf', label: 'PDF' },
          { value: 'excel', label: 'Excel' },
        ],
      },
      { key: 'include_carbon', label: 'Incluir carbono', type: 'checkbox' },
    ],
  },
]

const mergeConfig = (config) =>
  Object.fromEntries(
    Object.entries(defaultConfig).map(([category, values]) => [
      category,
      { ...values, ...(config?.[category] || {}) },
    ]),
  )

const getTenantIdentifier = (tenant) => tenant?.tenant_id || tenant?.id || ''

const TenantConfigAdmin = () => {
  const { refreshUser, user } = useAuth()
  const [tenants, setTenants] = useState([])
  const [selectedTenant, setSelectedTenant] = useState('')
  const [activeCategory, setActiveCategory] = useState(configCategories[0].key)
  const [config, setConfig] = useState(defaultConfig)
  const [loading, setLoading] = useState(true)
  const [configLoading, setConfigLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const category = useMemo(
    () => configCategories.find((item) => item.key === activeCategory),
    [activeCategory],
  )

  const selectedTenantName = useMemo(() => {
    const tenant = tenants.find((item) => getTenantIdentifier(item) === selectedTenant)
    return tenant?.name || user?.company?.name || 'Tenant'
  }, [selectedTenant, tenants, user])

  useEffect(() => {
    const loadTenants = async () => {
      setLoading(true)
      setError(null)

      try {
        if (user?.role === 'vkallpa_admin') {
          const response = await apiFetch('/tenants')
          const tenantItems = response.items || []
          setTenants(tenantItems)
          setSelectedTenant(getTenantIdentifier(tenantItems[0]))
          return
        }

        const tenant = user?.company
        if (tenant) {
          setTenants([tenant])
          setSelectedTenant(getTenantIdentifier(tenant))
        }
      } catch {
        setError('No se pudieron cargar los tenants.')
      } finally {
        setLoading(false)
      }
    }

    loadTenants()
  }, [user])

  useEffect(() => {
    if (!selectedTenant) {
      return
    }

    const loadConfig = async () => {
      setConfigLoading(true)
      setError(null)

      try {
        const response = await apiFetch(`/tenants/${selectedTenant}/config`)
        setConfig(mergeConfig(response))
      } catch {
        setError('No se pudo cargar la configuracion.')
      } finally {
        setConfigLoading(false)
      }
    }

    loadConfig()
  }, [selectedTenant])

  const handleFieldChange = (field, value) => {
    setConfig((current) => ({
      ...current,
      [activeCategory]: {
        ...current[activeCategory],
        [field.key]: field.type === 'checkbox' ? Boolean(value) : value,
      },
    }))
  }

  const buildCategoryPayload = () => {
    const values = config[activeCategory]

    return Object.fromEntries(
      category.fields.map((field) => {
        const value = values[field.key]

        if (field.type === 'number') {
          if (value === '') {
            throw new Error('Numeric value required')
          }
          return [field.key, Number(value)]
        }

        return [field.key, value]
      }),
    )
  }

  const handleSave = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    setNotice(null)

    try {
      const response = await apiFetch(`/tenants/${selectedTenant}/config`, {
        method: 'PATCH',
        body: JSON.stringify({ [activeCategory]: buildCategoryPayload() }),
      })
      setConfig(mergeConfig(response))
      setNotice(`Configuracion guardada para ${selectedTenantName}.`)

      if (user?.role !== 'vkallpa_admin') {
        await refreshUser()
      }
    } catch {
      setError('No se pudo guardar la configuracion.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="panel">Cargando...</div>
  }

  return (
    <div className="page">
      {error && <div className="panel error">{error}</div>}
      {notice && <div className="panel success">{notice}</div>}

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Configuracion operativa</h3>
            <p className="panel-subtitle">{selectedTenantName}</p>
          </div>

          {user?.role === 'vkallpa_admin' && (
            <div className="tenant-selector">
              <label>Tenant</label>
              <select
                value={selectedTenant}
                onChange={(event) => setSelectedTenant(event.target.value)}
              >
                {tenants.map((tenant) => (
                  <option key={tenant.id} value={getTenantIdentifier(tenant)}>
                    {tenant.name}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        <div className="tabs" role="tablist" aria-label="Configuracion tenant">
          {configCategories.map((item) => (
            <button
              key={item.key}
              className={item.key === activeCategory ? 'active' : ''}
              onClick={() => setActiveCategory(item.key)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </div>
      </section>

      <section className="panel">
        {configLoading ? (
          <div>Cargando...</div>
        ) : (
          <form className="config-form" onSubmit={handleSave}>
            {category.fields.map((field) => (
              <div
                key={field.key}
                className={field.type === 'checkbox' ? 'config-toggle' : ''}
              >
                <label>{field.label}</label>

                {field.type === 'select' && (
                  <select
                    value={config[activeCategory][field.key]}
                    onChange={(event) => handleFieldChange(field, event.target.value)}
                  >
                    {field.options.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                )}

                {field.type === 'number' && (
                  <input
                    min="0"
                    step={field.step}
                    type="number"
                    value={config[activeCategory][field.key]}
                    onChange={(event) => handleFieldChange(field, event.target.value)}
                  />
                )}

                {field.type === 'checkbox' && (
                  <input
                    checked={Boolean(config[activeCategory][field.key])}
                    type="checkbox"
                    onChange={(event) => handleFieldChange(field, event.target.checked)}
                  />
                )}
              </div>
            ))}

            <div className="form-actions admin-form-full">
              <button
                className="btn-primary"
                disabled={saving || !selectedTenant}
                type="submit"
              >
                {saving ? 'Guardando...' : 'Guardar'}
              </button>
            </div>
          </form>
        )}
      </section>
    </div>
  )
}

export default TenantConfigAdmin
