import { useCallback, useEffect, useMemo, useState } from 'react'

import { apiFetch } from '../api/client.js'
import { useAuth } from '../auth/useAuth.js'
import { BUSINESS_MODULE_OPTIONS, getRoleLabel } from '../navigation.js'

const makeEmptyForm = (user) => ({
  id: null,
  username: '',
  full_name: '',
  password: '',
  role: 'company_user',
  status: 'active',
  company_id: user?.company?.id || '',
  module_permissions: ['accueil', 'monitoring'],
  allowed_building_ids: user?.company?.allowed_building_ids || [],
})

const arraysMatch = (left, right) =>
  left.length === right.length && left.every((item, index) => item === right[index])

const UsersAdmin = () => {
  const { user } = useAuth()
  const [users, setUsers] = useState([])
  const [companies, setCompanies] = useState([])
  const [buildings, setBuildings] = useState([])
  const [form, setForm] = useState(() => makeEmptyForm(user))
  const [formOpen, setFormOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const buildingLabels = useMemo(
    () => Object.fromEntries(buildings.map((item) => [item.id, item.label])),
    [buildings],
  )

  const companyMap = useMemo(
    () => Object.fromEntries(companies.map((item) => [item.id, item])),
    [companies],
  )

  const isEditing = Boolean(form.id)
  const selectedCompany =
    user?.role === 'company_admin' ? user.company : companyMap[form.company_id]

  const availableBuildings =
    selectedCompany?.allowed_building_ids?.map((id) => ({
      id,
      label: buildingLabels[id] || id,
    })) || []

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const requests = [apiFetch('/users'), apiFetch('/buildings')]
      if (user?.role === 'vkallpa_admin') {
        requests.push(apiFetch('/admin/companies'))
      }

      const [usersResponse, buildingsResponse, companiesResponse] =
        await Promise.all(requests)
      setUsers(usersResponse.items)
      setBuildings(buildingsResponse.items)
      setCompanies(companiesResponse?.items || (user?.company ? [user.company] : []))
    } catch {
      setError('No se pudieron cargar los usuarios.')
    } finally {
      setLoading(false)
    }
  }, [user])

  useEffect(() => {
    if (user) {
      setForm(makeEmptyForm(user))
      loadData()
    }
  }, [loadData, user])

  useEffect(() => {
    if (form.role !== 'company_admin') {
      return
    }

    const moduleKeys = BUSINESS_MODULE_OPTIONS.map((item) => item.moduleKey)
    const buildingIds = selectedCompany?.allowed_building_ids || []
    setForm((current) => {
      if (
        arraysMatch(current.module_permissions, moduleKeys) &&
        arraysMatch(current.allowed_building_ids, buildingIds)
      ) {
        return current
      }

      return {
        ...current,
        module_permissions: moduleKeys,
        allowed_building_ids: buildingIds,
      }
    })
  }, [form.role, selectedCompany])

  const handleCreate = () => {
    setForm(makeEmptyForm(user))
    setNotice(null)
    setFormOpen(true)
  }

  const handleEdit = (item) => {
    setForm({
      id: item.id,
      username: item.username,
      full_name: item.full_name,
      password: '',
      role: item.role,
      status: item.status,
      company_id: item.company?.id || '',
      module_permissions:
        item.role === 'company_admin'
          ? BUSINESS_MODULE_OPTIONS.map((option) => option.moduleKey)
          : item.effective_module_permissions,
      allowed_building_ids: item.allowed_building_ids.length
        ? item.allowed_building_ids
        : item.effective_building_ids,
    })
    setNotice(null)
    setFormOpen(true)
  }

  const handleCloseForm = () => {
    setForm(makeEmptyForm(user))
    setFormOpen(false)
  }

  const handleToggleStatus = async (item) => {
    if (item.id === user?.id) {
      setError('No puedes desactivar tu propio usuario.')
      return
    }

    const nextStatus = item.status === 'active' ? 'inactive' : 'active'
    setError(null)
    setNotice(null)

    try {
      await apiFetch(`/users/${item.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: nextStatus }),
      })
      setNotice(
        nextStatus === 'active'
          ? 'Usuario activado correctamente.'
          : 'Usuario desactivado correctamente.',
      )
      await loadData()
    } catch {
      setError('No se pudo actualizar el estado del usuario.')
    }
  }

  const buildPayload = () => {
    const payload = {
      username: form.username,
      full_name: form.full_name,
      role: form.role,
      status: form.status,
      company_id: selectedCompany?.id || form.company_id,
      module_permissions: form.role === 'company_user' ? form.module_permissions : [],
      allowed_building_ids:
        form.role === 'company_user'
          ? form.allowed_building_ids
          : selectedCompany?.allowed_building_ids || [],
    }

    if (form.password) {
      payload.password = form.password
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
        ? await apiFetch(`/users/${form.id}`, {
            method: 'PATCH',
            body: JSON.stringify(payload),
          })
        : await apiFetch('/users', {
            method: 'POST',
            body: JSON.stringify(payload),
          })

      setNotice(
        response.temporary_password
          ? `Usuario guardado e invitado. Clave temporal: ${response.temporary_password}.`
          : 'Usuario guardado e invitado correctamente.',
      )
      handleCloseForm()
      await loadData()
    } catch {
      setError('No se pudo guardar el usuario.')
    } finally {
      setSubmitting(false)
    }
  }

  const toggleModule = (moduleKey) => {
    setForm((current) => ({
      ...current,
      module_permissions: current.module_permissions.includes(moduleKey)
        ? current.module_permissions.filter((item) => item !== moduleKey)
        : [...current.module_permissions, moduleKey],
    }))
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
            <h3>Usuarios</h3>
            <p className="panel-subtitle">
              Administre cuentas, roles, modulos visibles y edificios autorizados.
            </p>
          </div>
          <button className="btn-primary" type="button" onClick={handleCreate}>
            Nuevo usuario
          </button>
        </div>

        <div className="table users-table">
          <div className="table-row table-header">
            <span>Nombre</span>
            <span>Email</span>
            <span>Rol</span>
            <span>Tenant</span>
            <span>Estado</span>
            <span>Modulos</span>
            <span>Acciones</span>
          </div>
          {users.map((item) => (
            <div key={item.id} className="table-row">
              <span>{item.full_name}</span>
              <span>{item.username}</span>
              <span>{getRoleLabel(item.role)}</span>
              <span>{item.company?.name || 'Vkallpa'}</span>
              <span>
                <span className={`status-pill ${item.status}`}>{item.status}</span>
              </span>
              <span>{item.effective_module_permissions.join(', ') || 'Sin acceso'}</span>
              <span className="inline-actions">
                <button className="btn-secondary small" onClick={() => handleEdit(item)}>
                  Editar
                </button>
                <button
                  className={item.status === 'active' ? 'btn-danger small' : 'btn-secondary small'}
                  disabled={item.id === user?.id}
                  onClick={() => handleToggleStatus(item)}
                >
                  {item.status === 'active' ? 'Desactivar' : 'Activar'}
                </button>
              </span>
            </div>
          ))}
        </div>
      </section>

      {formOpen && (
        <div className="modal-backdrop">
          <section className="modal-panel" role="dialog" aria-modal="true">
            <div className="panel-header">
              <h3>{isEditing ? 'Editar usuario' : 'Nuevo usuario'}</h3>
              <button className="btn-secondary small" type="button" onClick={handleCloseForm}>
                Cerrar
              </button>
            </div>

            <form className="admin-form" onSubmit={handleSubmit}>
              <div>
                <label>Nombre completo</label>
                <input
                  value={form.full_name}
                  onChange={(e) =>
                    setForm((current) => ({ ...current, full_name: e.target.value }))
                  }
                  required
                />
              </div>
              <div>
                <label>Email</label>
                <input
                  type="email"
                  value={form.username}
                  onChange={(e) =>
                    setForm((current) => ({ ...current, username: e.target.value }))
                  }
                  required
                />
              </div>
              <div>
                <label>Contrasena</label>
                <input
                  type="password"
                  value={form.password}
                  onChange={(e) =>
                    setForm((current) => ({ ...current, password: e.target.value }))
                  }
                  placeholder={isEditing ? 'Mantener actual' : 'Se genera si queda vacia'}
                />
              </div>
              <div>
                <label>Rol</label>
                <select
                  value={form.role}
                  onChange={(e) => setForm((current) => ({ ...current, role: e.target.value }))}
                >
                  <option value="company_admin">Admin Empresa</option>
                  <option value="company_user">Usuario Empresa</option>
                </select>
              </div>
              <div>
                <label>Estado</label>
                <select
                  value={form.status}
                  onChange={(e) =>
                    setForm((current) => ({ ...current, status: e.target.value }))
                  }
                >
                  <option value="active">Activo</option>
                  <option value="inactive">Inactivo</option>
                </select>
              </div>

              {user?.role === 'vkallpa_admin' && (
                <div>
                  <label>Tenant</label>
                  <select
                    value={form.company_id}
                    onChange={(e) =>
                      setForm((current) => ({ ...current, company_id: e.target.value }))
                    }
                    required
                  >
                    <option value="">Seleccionar</option>
                    {companies.map((company) => (
                      <option key={company.id} value={company.id}>
                        {company.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="admin-form-full">
                <label>Permisos por modulo</label>
                {form.role === 'company_admin' ? (
                  <p className="form-hint">
                    Admin Empresa obtiene acceso completo a modulos de negocio.
                  </p>
                ) : (
                  <div className="checkbox-grid">
                    {BUSINESS_MODULE_OPTIONS.map((module) => (
                      <label key={module.moduleKey} className="checkbox-item">
                        <input
                          type="checkbox"
                          checked={form.module_permissions.includes(module.moduleKey)}
                          onChange={() => toggleModule(module.moduleKey)}
                        />
                        <span>{module.label}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>

              <div className="admin-form-full">
                <label>Edificios permitidos</label>
                <select
                  multiple
                  value={
                    form.role === 'company_admin'
                      ? selectedCompany?.allowed_building_ids || []
                      : form.allowed_building_ids
                  }
                  onChange={(e) =>
                    setForm((current) => ({
                      ...current,
                      allowed_building_ids: Array.from(
                        e.target.selectedOptions,
                        (option) => option.value,
                      ),
                    }))
                  }
                  disabled={form.role === 'company_admin'}
                >
                  {availableBuildings.map((building) => (
                    <option key={building.id} value={building.id}>
                      {building.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-actions admin-form-full">
                <button className="btn-primary" type="submit" disabled={submitting}>
                  {submitting ? 'Guardando...' : isEditing ? 'Actualizar' : 'Crear'}
                </button>
                <button
                  className="btn-secondary"
                  type="button"
                  onClick={handleCloseForm}
                  disabled={submitting}
                >
                  Cancelar
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  )
}

export default UsersAdmin
