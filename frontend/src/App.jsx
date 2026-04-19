import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { useAuth } from './auth/AuthContext.jsx'
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
import UsersAdmin from './pages/UsersAdmin.jsx'
import { getDefaultPath, hasModuleAccess } from './navigation.js'

const LoadingScreen = () => (
  <div className="loading-page">
    <div className="panel">Chargement de la session...</div>
  </div>
)

const RequireAuth = ({ children }) => {
  const { user, loading } = useAuth()

  if (loading) {
    return <LoadingScreen />
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return children
}

const RequireModule = ({ moduleKey, children }) => {
  const { user, loading } = useAuth()

  if (loading) {
    return <LoadingScreen />
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  if (!hasModuleAccess(user, moduleKey)) {
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
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to={defaultPath} replace />} />
        <Route
          path="accueil"
          element={
            <RequireModule moduleKey="accueil">
              <Accueil />
            </RequireModule>
          }
        />
        <Route
          path="parc-immobilier"
          element={
            <RequireModule moduleKey="parc-immobilier">
              <DashboardMulti />
            </RequireModule>
          }
        />
        <Route
          path="monitoring"
          element={
            <RequireModule moduleKey="monitoring">
              <Monitoring />
            </RequireModule>
          }
        />
        <Route
          path="profils"
          element={
            <RequireModule moduleKey="profils">
              <Profils />
            </RequireModule>
          }
        />
        <Route
          path="puissance-max"
          element={
            <RequireModule moduleKey="puissance-max">
              <Puissance />
            </RequireModule>
          }
        />
        <Route
          path="comparaison-puissance"
          element={
            <RequireModule moduleKey="comparaison-puissance">
              <ComparaisonPuissance />
            </RequireModule>
          }
        />
        <Route
          path="comparaison-periode"
          element={
            <RequireModule moduleKey="comparaison-periode">
              <ComparaisonPeriode />
            </RequireModule>
          }
        />
        <Route
          path="comparatif-batiments"
          element={
            <RequireModule moduleKey="comparatif-batiments">
              <Batiments />
            </RequireModule>
          }
        />
        <Route
          path="nilm"
          element={
            <RequireModule moduleKey="nilm">
              <Nilm />
            </RequireModule>
          }
        />
        <Route
          path="meteo"
          element={
            <RequireModule moduleKey="meteo">
              <Stub title="Meteo" />
            </RequireModule>
          }
        />
        <Route
          path="carbone"
          element={
            <RequireModule moduleKey="carbone">
              <Stub title="Carbone" />
            </RequireModule>
          }
        />
        <Route
          path="autoconsommation"
          element={
            <RequireModule moduleKey="autoconsommation">
              <Stub title="Autoconsommation" />
            </RequireModule>
          }
        />
        <Route
          path="changepoints"
          element={
            <RequireModule moduleKey="changepoints">
              <Stub title="Changepoints" />
            </RequireModule>
          }
        />
        <Route
          path="anomalies"
          element={
            <RequireModule moduleKey="anomalies">
              <Stub title="Anomalies" />
            </RequireModule>
          }
        />
        <Route
          path="prediction"
          element={
            <RequireModule moduleKey="prediction">
              <Stub title="Prediction" />
            </RequireModule>
          }
        />
        <Route
          path="admin/users"
          element={
            <RequireModule moduleKey="admin-users">
              <UsersAdmin />
            </RequireModule>
          }
        />
        <Route
          path="admin/companies"
          element={
            <RequireModule moduleKey="admin-companies">
              <CompaniesAdmin />
            </RequireModule>
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
