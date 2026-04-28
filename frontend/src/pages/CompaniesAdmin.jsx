import { useEffect, useMemo, useState } from 'react'

import { apiFetch } from '../api/client.js'

const emptyForm = {
  id: null,
  original_tenant_id: '',
  tenant_id: '',
  name: '',
  slug: '',
  status: 'active',
  user_quota: 25,
  allowed_building_ids: [],
  admin_username: '',
  admin_full_name: '',
  admin_password: '',
}

const CompaniesAdmin = () => {
  const [tenants, setTenants] = useState([])
  const [buildings, setBuildings] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const buildingLabels = useMemo(
    () => Object.fromEntries(buildings.map((item) => [item.id, item.label])),
    [buildings],
  )

  const isEditing = Boolean(form.id)

  const loadData = async () => {
    setLoading(true)
    setError(null)

    try {
      const [tenantsResponse, buildingsResponse] = await Promise.all([
        apiFetch('/tenants'),
        apiFetch('/buildings'),
      ])
      setTenants(tenantsResponse.items)
      setBuildings(buildingsResponse.items)
    } catch {
      setError('No se pudieron cargar los tenants.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const buildPayload = () => {
    const payload = {
      tenant_id: form.tenant_id,
      name: form.name,
      slug: form.slug || null,
      status: form.status,
      user_quota: Number(form.user_quota),
      allowed_building_ids: form.allowed_building_ids,
    }

    if (!isEditing) {
      payload.admin_username = form.admin_username || null
      payload.admin_full_name = form.admin_full_name || null
      payload.admin_password = form.admin_password || null
    }

    return payload
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    setNotice(null)

    try {
      const payload = buildPayload()
      const response = isEditing
        ? await apiFetch(`/tenants/${form.original_tenant_id || form.tenant_id}`, {
            method: 'PUT',
            body: JSON.stringify(payload),
          })
        : await apiFetch('/tenants', {
            method: 'POST',
            body: JSON.stringify(payload),
          })

      const admin = response.initial_admin
      setNotice(
        admin?.temporary_password
          ? `Tenant guardado. Admin inicial: ${admin.username}. Clave temporal: ${admin.temporary_password}.`
          : admin
          ? `Tenant guardado. Admin inicial: ${admin.username}.`
          : 'Tenant actualizado correctamente.',
      )
      setForm(emptyForm)
      await loadData()
    } catch {
      setError('No se pudo guardar el tenant.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleEdit = (tenant) => {
    setForm({
      id: tenant.id,
      original_tenant_id: tenant.tenant_id,
      tenant_id: tenant.tenant_id,
      name: tenant.name,
      slug: tenant.slug,
      status: tenant.status,
      user_quota: tenant.user_quota,
      allowed_building_ids: tenant.allowed_building_ids,
      admin_username: '',
      admin_full_name: '',
      admin_password: '',
    })
    setNotice(null)
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
            <h3>Tenants</h3>
            <p className="panel-subtitle">
              Registre organizaciones cliente, edificios autorizados y su Admin inicial.
            </p>
          </div>
        </div>

        <form className="admin-form" onSubmit={handleSubmit}>
          <div>
            <label>Tenant ID</label>
            <input
              value={form.tenant_id}
              onChange={(e) => setForm((current) => ({ ...current, tenant_id: e.target.value }))}
              placeholder="acme-energy"
              required
            />
          </div>
          <div>
            <label>Nombre</label>
            <input
              value={form.name}
              onChange={(e) => setForm((current) => ({ ...current, name: e.target.value }))}
              required
            />
          </div>
          <div>
            <label>Slug</label>
            <input
              value={form.slug}
              onChange={(e) => setForm((current) => ({ ...current, slug: e.target.value }))}
              placeholder="opcional"
            />
          </div>
          <div>
            <label>Estado</label>
            <select
              value={form.status}
              onChange={(e) => setForm((current) => ({ ...current, status: e.target.value }))}
            >
              <option value="active">Activo</option>
              <option value="inactive">Inactivo</option>
            </select>
          </div>
          <div>
            <label>Cupo usuarios</label>
            <input
              type="number"
              min="1"
              value={form.user_quota}
              onChange={(e) =>
                setForm((current) => ({ ...current, user_quota: e.target.value }))
              }
              required
            />
          </div>

          {!isEditing && (
            <>
              <div>
                <label>Usuario Admin</label>
                <input
                  value={form.admin_username}
                  onChange={(e) =>
                    setForm((current) => ({ ...current, admin_username: e.target.value }))
                  }
                  placeholder="admin@tenant"
                />
              </div>
              <div>
                <label>Nombre Admin</label>
                <input
                  value={form.admin_full_name}
                  onChange={(e) =>
                    setForm((current) => ({ ...current, admin_full_name: e.target.value }))
                  }
                  placeholder="Admin Tenant"
                />
              </div>
              <div>
                <label>Clave Admin</label>
                <input
                  type="password"
                  value={form.admin_password}
                  onChange={(e) =>
                    setForm((current) => ({ ...current, admin_password: e.target.value }))
                  }
                  placeholder="se genera si queda vacia"
                />
              </div>
            </>
          )}

          <div className="admin-form-full">
            <label>Edificios autorizados</label>
            <select
              multiple
              value={form.allowed_building_ids}
              onChange={(e) =>
                setForm((current) => ({
                  ...current,
                  allowed_building_ids: Array.from(
                    e.target.selectedOptions,
                    (option) => option.value,
                  ),
                }))
              }
            >
              {buildings.map((building) => (
                <option key={building.id} value={building.id}>
                  {building.label}
                </option>
              ))}
            </select>
          </div>
          <div className="form-actions admin-form-full">
            <button className="btn-primary" disabled={submitting} type="submit">
              {submitting ? 'Guardando...' : isEditing ? 'Actualizar' : 'Crear'}
            </button>
            <button
              className="btn-secondary"
              type="button"
              onClick={() => setForm(emptyForm)}
              disabled={submitting}
            >
              Reiniciar
            </button>
          </div>
        </form>
      </section>

      <section className="panel">
        <div className="table">
          <div className="table-row table-header">
            <span>Tenant</span>
            <span>Tenant ID</span>
            <span>Estado</span>
            <span>Edificios</span>
            <span>Usuarios</span>
            <span>Cupo</span>
            <span>Accion</span>
          </div>
          {tenants.map((tenant) => (
            <div key={tenant.id} className="table-row">
              <span>{tenant.name}</span>
              <span>{tenant.tenant_id}</span>
              <span>
                <span className={`status-pill ${tenant.status}`}>{tenant.status}</span>
              </span>
              <span>
                {tenant.allowed_building_ids.length > 0
                  ? tenant.allowed_building_ids
                      .slice(0, 3)
                      .map((id) => buildingLabels[id] || id)
                      .join(', ')
                  : 'Sin edificios'}
              </span>
              <span>{tenant.user_count}</span>
              <span>{tenant.user_quota}</span>
              <span>
                <button className="btn-secondary small" onClick={() => handleEdit(tenant)}>
                  Editar
                </button>
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

export default CompaniesAdmin
