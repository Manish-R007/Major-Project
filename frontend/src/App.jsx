import { Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Atlas from './pages/Atlas.jsx'
import Claims from './pages/Claims.jsx'
import ClaimDetail from './pages/ClaimDetail.jsx'
import DSS from './pages/DSS.jsx'
import Users from './pages/Users.jsx'
import Navbar from './components/Navbar.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'

function Layout({ children }) {
  return (
    <div className="min-h-screen bg-parchment-200">
      <Navbar />
      {children}
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      <Route path="/dashboard" element={
        <ProtectedRoute><Layout><Dashboard /></Layout></ProtectedRoute>
      } />
      <Route path="/atlas" element={
        <ProtectedRoute><Layout><Atlas /></Layout></ProtectedRoute>
      } />
      <Route path="/claims" element={
        <ProtectedRoute><Layout><Claims /></Layout></ProtectedRoute>
      } />
      <Route path="/claims/:id" element={
        <ProtectedRoute><Layout><ClaimDetail /></Layout></ProtectedRoute>
      } />
      <Route path="/dss" element={
        <ProtectedRoute allowedRoles={['village_official', 'district_officer', 'state_officer', 'admin']}>
          <Layout><DSS /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/users" element={
        <ProtectedRoute allowedRoles={['admin', 'state_officer']}>
          <Layout><Users /></Layout>
        </ProtectedRoute>
      } />

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
