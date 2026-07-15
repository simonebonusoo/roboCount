import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { StatusView } from "./StatusView";

export function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <StatusView title="Caricamento sessione" message="Sto verificando il tuo accesso." />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return children;
}
