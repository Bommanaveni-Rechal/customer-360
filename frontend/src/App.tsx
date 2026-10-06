import { Navigate, Route, Routes } from "react-router-dom"
import Layout from "./components/Layout"
import Actions from "./pages/Actions"
import Customer360 from "./pages/Customer360"
import Customers from "./pages/Customers"
import Dashboard from "./pages/Dashboard"

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/customers" element={<Customers />} />
        <Route path="/customers/:id" element={<Customer360 />} />
        <Route path="/actions" element={<Actions />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
