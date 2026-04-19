import { useEffect, useMemo, useState } from 'react'

import { apiFetch } from '../api/client.js'
import { useAuth } from '../auth/AuthContext.jsx'
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

const UsersAdmin = () => {
  const { user } = useAuth()
  const [users, setUsers] = useState([])
  const [companies, setCompanies] = useState([])
  const [buildings, setBuildings] = useState([])
  const [form, setForm] = useState(() => makeEmptyForm(user))
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const buildingLabels = useMemo(
    () => Object.fromEntries(buildings.map((item) => [item.id, item.label])),
    [buildings],
  )

  const companyMap = useMemo(
    () => Object.fromEntries(companies.map((item) => [item.id, item])),
    [companies],
  )

  const selectedCompany =
    user?.role === 'company_admin' ? user.company : companyMap[form.company_id]

  const availableBuildings =
    selectedCompany?.allowed_building_ids?.map((id) => ({
      id,
      label: buildingLabels[id] || id,
    })) || []

  const loadData = async () => {
    setLoading(true)
    setError(null)

    try {
      const requests = [apiFetch('/admin/users'), apiFetch('/buildings')]
      if (user?.role === 'vkallpa_admin') {
        requests.push(apiFetch('/admin/companies'))
      }

      const [usersResponse, buildingsResponse, companiesResponse] = await Promise.all(requests)
      setUsers(usersResponse.items)
      setBuildings(buildingsResponse.items)
      setCompanies(companiesResponse?.items || (user?.company ? [user.company] : []))
    } catch {
      setError('Impossible de charger les utilisateurs.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (user) {
      setForm(makeEmptyForm(user))
      loadData()
    }
  }, [user])

  useEffect(() => {
    if (form.role === 'company_admin') {
      setForm((current) => ({
        ...current,
        module_permissions: BUSINESS_MODULE_OPTIONS.map((item) => item.moduleKey),
        allowed_building_ids: selectedCompany?.allowed_building_ids || [],
      }))
    }
  }, [form.role, selectedCompany])

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
  }

  const handleDelete = async (userId) => {
    if (!window.confirm('Confirmer la suppression logique de cet utilisateur ?')) {
      return
    }

    try {
      await apiFetch(`/admin/users/${userId}`, { method: 'DELETE' })
      await loadData()
    } catch {
      setError('Impossible de supprimer cet utilisateur.')
    }
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setSubmitting(true)
    setError(null)

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

    try {
      if (form.id) {
        await apiFetch(`/admin/users/${form.id}`, {
          method: 'PATCH',
          body: JSON.stringify(payload),
        })
      } else {
        await apiFetch('/admin/users', {
          method: 'POST',
          body: JSON.stringify({
            ...payload,
            password: form.password,
          }),
        })
      }

      setForm(makeEmptyForm(user))
      await loadData()
    } catch {
      setError('Impossible d enregistrer cet utilisateur.')
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
    return <div className="panel">Chargement...</div>
  }

  return (
    <div className="page">
      {error && <div className="panel error">{error}</div>}

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Utilisateurs</h3>
            <p className="panel-subtitle">
              Administrez les comptes, les roles, les modules visibles et les batiments autorises.
            </p>
          </div>
        </div>

        <form className="admin-form" onSubmit={handleSubmit}>
          <div>
            <label>Nom complet</label>
            <input
              value={form.full_name}
              onChange={(e) => setForm((current) => ({ ...current, full_name: e.target.value }))}
              required
            />
          </div>
          <div>
            <label>Usuario</label>
            <input
              value={form.username}
              onChange={(e) => setForm((current) => ({ ...current, username: e.target.value }))}
              required
            />
          </div>
          <div>
            <label>Mot de passe {form.id ? '(laisser vide pour conserver)' : ''}</label>
            <input
              type="password"
              value={form.password}
              onChange={(e) => setForm((current) => ({ ...current, password: e.target.value }))}
              required={!form.id}
            />
          </div>
          <div>
            <label>Role</label>
            <select
              value={form.role}
              onChange={(e) => setForm((current) => ({ ...current, role: e.target.value }))}
            >
              <option value="company_admin">Admin Empresa</option>
              <option value="company_user">Usuario Empresa</option>
            </select>
          </div>
          <div>
            <label>Statut</label>
            <select
              value={form.status}
              onChange={(e) => setForm((current) => ({ ...current, status: e.target.value }))}
            >
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>

          {user?.role === 'vkallpa_admin' && (
            <div>
              <label>Entreprise</label>
              <select
                value={form.company_id}
                onChange={(e) => setForm((current) => ({ ...current, company_id: e.target.value }))}
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
                El rol Admin Empresa obtiene acceso completo a modulos de negocio y gestion de usuarios.
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
            <label>Batiments permitidos</label>
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
              {submitting ? 'Enregistrement...' : form.id ? 'Mettre a jour' : 'Creer'}
            </button>
            <button
              className="btn-secondary"
              type="button"
              onClick={() => setForm(makeEmptyForm(user))}
              disabled={submitting}
            >
              Reinitialiser
            </button>
          </div>
        </form>
      </section>

      <section className="panel">
        <div className="table">
          <div className="table-row table-header">
            <span>Nom</span>
            <span>Usuario</span>
            <span>Role</span>
            <span>Entreprise</span>
            <span>Statut</span>
            <span>Modules</span>
            <span>Action</span>
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
                <button className="btn-danger small" onClick={() => handleDelete(item.id)}>
                  Eliminar
                </button>
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

export default UsersAdmin
