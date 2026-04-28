export const MENU = [
  {
    name: 'Accueil',
    icon: 'HQ',
    items: [
      { label: 'Accueil', path: '/accueil', moduleKey: 'accueil' },
      { label: 'Parc immobilier', path: '/parc-immobilier', moduleKey: 'parc-immobilier' },
    ],
  },
  {
    name: 'Monitoring',
    icon: 'MON',
    items: [
      { label: 'Monitoring', path: '/monitoring', moduleKey: 'monitoring' },
      { label: 'Profils', path: '/profils', moduleKey: 'profils' },
      { label: 'Puissance Max', path: '/puissance-max', moduleKey: 'puissance-max' },
      {
        label: 'Comparaison Puissance',
        path: '/comparaison-puissance',
        moduleKey: 'comparaison-puissance',
      },
      { label: 'Meteo', path: '/meteo', moduleKey: 'meteo' },
      { label: 'Carbone', path: '/carbone', moduleKey: 'carbone' },
    ],
  },
  {
    name: 'Traitement',
    icon: 'OPS',
    items: [
      {
        label: 'Comparaison Periode',
        path: '/comparaison-periode',
        moduleKey: 'comparaison-periode',
      },
      {
        label: 'Comparatif Batiments',
        path: '/comparatif-batiments',
        moduleKey: 'comparatif-batiments',
      },
      {
        label: 'Autoconsommation',
        path: '/autoconsommation',
        moduleKey: 'autoconsommation',
      },
      { label: 'Changepoints', path: '/changepoints', moduleKey: 'changepoints' },
    ],
  },
  {
    name: 'IA',
    icon: 'AI',
    items: [
      { label: 'Anomalies', path: '/anomalies', moduleKey: 'anomalies' },
      { label: 'Prediction', path: '/prediction', moduleKey: 'prediction' },
      { label: 'NILM', path: '/nilm', moduleKey: 'nilm' },
    ],
  },
  {
    name: 'Administration',
    icon: 'ADM',
    items: [
      { label: 'Utilisateurs', path: '/admin/users', moduleKey: 'admin-users' },
      { label: 'Tenants', path: '/admin/companies', moduleKey: 'admin-companies' },
      {
        label: 'Configuracion tenant',
        path: '/admin/tenant-config',
        moduleKey: 'tenant-settings',
      },
    ],
  },
]

export const ROUTE_ITEMS = MENU.flatMap((section) => section.items)

export const ROLE_DEFAULT_PATHS = {
  vkallpa_admin: '/admin/companies',
  company_admin: '/admin/users',
  company_user: '/accueil',
}

export const BUSINESS_MODULE_OPTIONS = ROUTE_ITEMS.filter(
  (item) => !item.moduleKey.startsWith('admin-'),
)

export const hasModuleAccess = (user, moduleKey) => {
  if (!user) return false
  if (user.role === 'vkallpa_admin') return true
  return user.module_permissions.includes(moduleKey)
}

export const hasRoleAccess = (user, allowedRoles = []) => {
  if (!user) return false
  if (!allowedRoles.length) return true
  return allowedRoles.includes(user.role)
}

export const getAccessibleMenu = (user) =>
  MENU.map((section) => ({
    ...section,
    items: section.items.filter((item) => hasModuleAccess(user, item.moduleKey)),
  })).filter((section) => section.items.length > 0)

export const getDefaultPath = (user) => {
  const rolePath = ROLE_DEFAULT_PATHS[user?.role]
  const roleRoute = ROUTE_ITEMS.find((item) => item.path === rolePath)
  if (roleRoute && hasModuleAccess(user, roleRoute.moduleKey)) {
    return rolePath
  }

  const firstRoute = ROUTE_ITEMS.find((item) => hasModuleAccess(user, item.moduleKey))
  return firstRoute?.path || '/login'
}

export const getRoleLabel = (role) => {
  switch (role) {
    case 'vkallpa_admin':
      return 'Admin Vkallpa'
    case 'company_admin':
      return 'Admin Empresa'
    case 'company_user':
      return 'Usuario Empresa'
    default:
      return role
  }
}
