import { useEffect, useMemo, useState } from 'react'

import { apiFetch } from '../api/client.js'
import { useAuth } from '../auth/useAuth.js'

const defaultMapping = {
  timestamp: 'Date',
  energy_kwh: 'Energie_periode_kWh',
  power_kw: 'Puissance_moyenne_kW',
  site: 'Batiment',
  energy_type: '',
  location: '',
}

const emptyConfig = {
  source_type: 'azure_blob',
  name: 'Azure Blob Storage',
  container_name: '',
  blob_prefix: '',
  default_sheet_name: 'Donnees_Detaillees',
  field_mapping: defaultMapping,
}

const mappingFields = [
  { key: 'timestamp', label: 'Fecha / hora', required: true },
  { key: 'energy_kwh', label: 'Energia kWh', required: true },
  { key: 'power_kw', label: 'Potencia kW' },
  { key: 'site', label: 'Sitio' },
  { key: 'energy_type', label: 'Tipo energia' },
  { key: 'location', label: 'Ubicacion' },
]

const getTenantIdentifier = (tenant) => tenant?.tenant_id || tenant?.id || ''

const tenantQuery = (tenantId) =>
  tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : ''

const normalizeConfig = (config) => ({
  ...emptyConfig,
  ...config,
  field_mapping: {
    ...defaultMapping,
    ...(config?.field_mapping || {}),
  },
})

const cleanMapping = (mapping) =>
  Object.fromEntries(
    Object.entries(mapping).map(([key, value]) => [key, value || null]),
  )

const DataSourcesAdmin = () => {
  const { user } = useAuth()
  const [tenants, setTenants] = useState([])
  const [selectedTenant, setSelectedTenant] = useState('')
  const [config, setConfig] = useState(emptyConfig)
  const [files, setFiles] = useState([])
  const [selectedFile, setSelectedFile] = useState('')
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [configLoading, setConfigLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const selectedTenantName = useMemo(() => {
    const tenant = tenants.find((item) => getTenantIdentifier(item) === selectedTenant)
    return tenant?.name || user?.company?.name || 'Tenant'
  }, [selectedTenant, tenants, user])

  const selectedFileFormat = useMemo(
    () => files.find((item) => item.name === selectedFile)?.format || '',
    [files, selectedFile],
  )

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

        if (user?.company) {
          setTenants([user.company])
          setSelectedTenant(getTenantIdentifier(user.company))
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

    const loadDataSource = async () => {
      setConfigLoading(true)
      setError(null)
      setPreview(null)

      try {
        const [configResponse, filesResponse] = await Promise.all([
          apiFetch(`/data-sources${tenantQuery(selectedTenant)}`),
          apiFetch(`/data-sources/files${tenantQuery(selectedTenant)}`),
        ])
        const fileItems = filesResponse.items || []
        setConfig(normalizeConfig(configResponse))
        setFiles(fileItems)
        setSelectedFile(fileItems[0]?.name || '')
      } catch {
        setError('No se pudo cargar la fuente de datos.')
      } finally {
        setConfigLoading(false)
      }
    }

    loadDataSource()
  }, [selectedTenant])

  const handleConfigChange = (field, value) => {
    setConfig((current) => ({ ...current, [field]: value }))
  }

  const handleMappingChange = (field, value) => {
    setConfig((current) => ({
      ...current,
      field_mapping: {
        ...current.field_mapping,
        [field]: value,
      },
    }))
  }

  const handleSave = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    setNotice(null)

    try {
      const response = await apiFetch('/data-sources', {
        method: 'PUT',
        body: JSON.stringify({
          ...config,
          tenant_id: selectedTenant,
          field_mapping: cleanMapping(config.field_mapping),
        }),
      })
      setConfig(normalizeConfig(response))
      setNotice(`Fuente de datos guardada para ${selectedTenantName}.`)
    } catch {
      setError('No se pudo guardar la fuente de datos.')
    } finally {
      setSaving(false)
    }
  }

  const handlePreview = async () => {
    setPreviewing(true)
    setError(null)
    setNotice(null)

    try {
      const response = await apiFetch('/data-sources/preview', {
        method: 'POST',
        body: JSON.stringify({
          tenant_id: selectedTenant,
          blob_name: selectedFile,
          sheet_name: config.default_sheet_name || null,
          field_mapping: cleanMapping(config.field_mapping),
        }),
      })
      setPreview(response)
      setNotice(
        response.is_valid
          ? 'Vista previa validada correctamente.'
          : 'Vista previa generada con observaciones.',
      )
    } catch {
      setError('No se pudo generar la vista previa.')
    } finally {
      setPreviewing(false)
    }
  }

  if (loading) {
    return <div className="panel">Cargando...</div>
  }

  return (
    <div className="page">
      {error && <div className="panel error">{error}</div>}
      {notice && <div className="panel success">{notice}</div>}

      <div className="data-source-layout">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h3>Fuente Azure Blob Storage</h3>
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

          <form className="admin-form" onSubmit={handleSave}>
            <div>
              <label>Nombre</label>
              <input
                required
                value={config.name}
                onChange={(event) => handleConfigChange('name', event.target.value)}
              />
            </div>
            <div>
              <label>Contenedor</label>
              <input
                required
                value={config.container_name}
                onChange={(event) =>
                  handleConfigChange('container_name', event.target.value)
                }
              />
            </div>
            <div>
              <label>Prefijo blob</label>
              <input
                value={config.blob_prefix || ''}
                onChange={(event) =>
                  handleConfigChange('blob_prefix', event.target.value)
                }
                placeholder="opcional"
              />
            </div>
            <div>
              <label>Hoja Excel</label>
              <input
                value={config.default_sheet_name || ''}
                onChange={(event) =>
                  handleConfigChange('default_sheet_name', event.target.value)
                }
                placeholder="opcional"
              />
            </div>

            <div className="form-actions admin-form-full">
              <button
                className="btn-primary"
                disabled={saving || configLoading || !selectedTenant}
                type="submit"
              >
                {saving ? 'Guardando...' : 'Guardar'}
              </button>
            </div>
          </form>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <h3>Archivos disponibles</h3>
              <p className="panel-subtitle">{files.length} archivos CSV/XLSX</p>
            </div>
            <button
              className="btn-secondary"
              disabled={!selectedFile || previewing}
              onClick={handlePreview}
              type="button"
            >
              {previewing ? 'Validando...' : 'Previsualizar'}
            </button>
          </div>

          <div className="source-file-list">
            {files.map((file) => (
              <button
                key={file.name}
                className={
                  file.name === selectedFile ? 'file-button active' : 'file-button'
                }
                onClick={() => setSelectedFile(file.name)}
                type="button"
              >
                <span>{file.name}</span>
                <strong>{file.format.toUpperCase()}</strong>
              </button>
            ))}
          </div>

          {selectedFile && (
            <div className="preview-meta">
              <span>{selectedFile}</span>
              <span className="status-pill active">
                {selectedFileFormat.toUpperCase()}
              </span>
            </div>
          )}
        </section>
      </div>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Mapeo de campos</h3>
            <p className="panel-subtitle">CSV y Excel</p>
          </div>
        </div>

        <datalist id="preview-columns">
          {(preview?.columns || []).map((column) => (
            <option key={column} value={column} />
          ))}
        </datalist>

        <div className="mapping-grid">
          {mappingFields.map((field) => (
            <div key={field.key}>
              <label>
                {field.label}
                {field.required ? ' *' : ''}
              </label>
              <input
                list="preview-columns"
                required={Boolean(field.required)}
                value={config.field_mapping[field.key] || ''}
                onChange={(event) =>
                  handleMappingChange(field.key, event.target.value)
                }
              />
            </div>
          ))}
        </div>
      </section>

      {preview && (
        <section className="panel">
          <div className="panel-header">
            <div>
              <h3>Vista previa</h3>
              <p className="panel-subtitle">{preview.blob_name}</p>
            </div>
            <span className={`status-pill ${preview.is_valid ? 'active' : 'inactive'}`}>
              {preview.is_valid ? 'Valido' : 'Revisar'}
            </span>
          </div>

          {preview.validation_errors.length > 0 && (
            <div className="validation-list">
              {preview.validation_errors.map((item) => (
                <div
                  key={`${item.field}-${item.column}-${item.message}`}
                  className="validation-item"
                >
                  <strong>{item.field}</strong>
                  <span>{item.column || 'archivo'}</span>
                  <p>{item.message}</p>
                </div>
              ))}
            </div>
          )}

          <div className="preview-table-wrap">
            <table className="preview-table">
              <thead>
                <tr>
                  {preview.columns.map((column) => (
                    <th key={column}>{column}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row, index) => (
                  <tr key={`${preview.blob_name}-${index}`}>
                    {preview.columns.map((column) => (
                      <td key={column}>{row[column] ?? '-'}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}

export default DataSourcesAdmin
