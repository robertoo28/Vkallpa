import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { useAuth } from './auth/useAuth.js'
import Layout from './components/Layout.jsx'
import Accueil from './pages/Accueil.jsx'
import Batiments from './pages/Batiments.jsx'
import CompaniesAdmin from './pages/CompaniesAdmin.jsx'
import ComparaisonPeriode from './pages/ComparaisonPeriode.jsx'
import ComparaisonPuissance from './pages/ComparaisonPuissance.jsx'
import DashboardMulti from './pages/DashboardMulti.jsx'
import Login from './pages/Login.jsx'
import Monitoring from './pages/Monitoring.jsx'
import Nilm from './pages/Nilm.jsx'
import Profils from './pages/Profils.jsx'
import Puissance from './pages/Puissance.jsx'
import Stub from './pages/Stub.jsx'
import TenantConfigAdmin from './pages/TenantConfigAdmin.jsx'
import UsersAdmin from './pages/UsersAdmin.jsx'
import { getDefaultPath, hasModuleAccess, hasRoleAccess } from './navigation.js'

const LoadingScreen = () => (
  <div className="loading-page">
    <div className="panel">Chargement de la session...</div>
  </div>
)

const PrivateRoute = ({ allowedRoles = [], moduleKey = null, children }) => {
  const { user, loading } = useAuth()

  if (loading) {
    return <LoadingScreen />
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  if (!hasRoleAccess(user, allowedRoles)) {
    return <Navigate to={getDefaultPath(user)} replace />
  }

  if (moduleKey && !hasModuleAccess(user, moduleKey)) {
    return <Navigate to={getDefaultPath(user)} replace />
  }

  return children
}

const AppRoutes = () => {
  const { user } = useAuth()
  const defaultPath = getDefaultPath(user)

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to={defaultPath} replace /> : <Login />} />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <Layout />
          </PrivateRoute>
        }
      >
        <Route index element={<Navigate to={defaultPath} replace />} />
        <Route
          path="accueil"
          element={
            <PrivateRoute moduleKey="accueil">
              <Accueil />
            </PrivateRoute>
          }
        />
        <Route
          path="parc-immobilier"
          element={
            <PrivateRoute moduleKey="parc-immobilier">
              <DashboardMulti />
            </PrivateRoute>
          }
        />
        <Route
          path="monitoring"
          element={
            <PrivateRoute moduleKey="monitoring">
              <Monitoring />
            </PrivateRoute>
          }
        />
        <Route
          path="profils"
          element={
            <PrivateRoute moduleKey="profils">
              <Profils />
            </PrivateRoute>
          }
        />
        <Route
          path="puissance-max"
          element={
            <PrivateRoute moduleKey="puissance-max">
              <Puissance />
            </PrivateRoute>
          }
        />
        <Route
          path="comparaison-puissance"
          element={
            <PrivateRoute moduleKey="comparaison-puissance">
              <ComparaisonPuissance />
            </PrivateRoute>
          }
        />
        <Route
          path="comparaison-periode"
          element={
            <PrivateRoute moduleKey="comparaison-periode">
              <ComparaisonPeriode />
            </PrivateRoute>
          }
        />
        <Route
          path="comparatif-batiments"
          element={
            <PrivateRoute moduleKey="comparatif-batiments">
              <Batiments />
            </PrivateRoute>
          }
        />
        <Route
          path="nilm"
          element={
            <PrivateRoute moduleKey="nilm">
              <Nilm />
            </PrivateRoute>
          }
        />
        <Route
          path="meteo"
          element={
            <PrivateRoute moduleKey="meteo">
              <Stub title="Meteo" />
            </PrivateRoute>
          }
        />
        <Route
          path="carbone"
          element={
            <PrivateRoute moduleKey="carbone">
              <Stub title="Carbone" />
            </PrivateRoute>
          }
        />
        <Route
          path="autoconsommation"
          element={
            <PrivateRoute moduleKey="autoconsommation">
              <Stub title="Autoconsommation" />
            </PrivateRoute>
          }
        />
        <Route
          path="changepoints"
          element={
            <PrivateRoute moduleKey="changepoints">
              <Stub title="Changepoints" />
            </PrivateRoute>
          }
        />
        <Route
          path="anomalies"
          element={
            <PrivateRoute moduleKey="anomalies">
              <Stub title="Anomalies" />
            </PrivateRoute>
          }
        />
        <Route
          path="prediction"
          element={
            <PrivateRoute moduleKey="prediction">
              <Stub title="Prediction" />
            </PrivateRoute>
          }
        />
        <Route
          path="admin/users"
          element={
            <PrivateRoute
              allowedRoles={['vkallpa_admin', 'company_admin']}
              moduleKey="admin-users"
            >
              <UsersAdmin />
            </PrivateRoute>
          }
        />
        <Route
          path="admin/companies"
          element={
            <PrivateRoute
              allowedRoles={['vkallpa_admin']}
              moduleKey="admin-companies"
            >
              <CompaniesAdmin />
            </PrivateRoute>
          }
        />
        <Route
          path="admin/tenant-config"
          element={
            <PrivateRoute
              allowedRoles={['vkallpa_admin', 'company_admin']}
              moduleKey="tenant-settings"
            >
              <TenantConfigAdmin />
            </PrivateRoute>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to={user ? defaultPath : '/login'} replace />} />
    </Routes>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}

export default App
