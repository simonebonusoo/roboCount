import React, { Suspense, lazy } from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { StatusView } from "./components/StatusView";
import { queryClient } from "./lib/queryClient";
import "./styles.css";
import { applyTheme, getStoredTheme } from "./hooks/useThemePreference";

const AppShell = lazy(() => import("./components/AppShell").then((module) => ({ default: module.AppShell })));
const LoginPage = lazy(() => import("./pages/LoginPage").then((module) => ({ default: module.LoginPage })));
const HomePage = lazy(() => import("./pages/HomePage").then((module) => ({ default: module.HomePage })));
const CalendarPage = lazy(() => import("./pages/CalendarPage").then((module) => ({ default: module.CalendarPage })));
const ExpensesPage = lazy(() => import("./pages/ExpensesPage").then((module) => ({ default: module.ExpensesPage })));
const IncomesPage = lazy(() => import("./pages/IncomesPage").then((module) => ({ default: module.IncomesPage })));
const ProfilePage = lazy(() => import("./pages/ProfilePage").then((module) => ({ default: module.ProfilePage })));
const CoupleBalancePage = lazy(() => import("./pages/CoupleBalancePage").then((module) => ({ default: module.CoupleBalancePage })));
const SavingsPage = lazy(() => import("./pages/SavingsPage").then((module) => ({ default: module.SavingsPage })));
const ReportPage = lazy(() => import("./pages/ReportPage").then((module) => ({ default: module.ReportPage })));
const AdminUsersPage = lazy(() => import("./pages/AdminUsersPage").then((module) => ({ default: module.AdminUsersPage })));

if (typeof window !== "undefined") {
  applyTheme(getStoredTheme());
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Suspense fallback={<StatusView title="Caricamento" message="Sto preparando l'interfaccia." />}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <AppShell />
                  </ProtectedRoute>
                }
              >
                <Route index element={<Navigate to="/home" replace />} />
                <Route path="dashboard" element={<Navigate to="/home" replace />} />
                <Route path="home" element={<HomePage />} />
                <Route path="calendar" element={<CalendarPage />} />
                <Route path="couple-balance" element={<CoupleBalancePage />} />
                <Route path="expenses" element={<ExpensesPage />} />
                <Route path="incomes" element={<IncomesPage />} />
                <Route path="risparmi" element={<SavingsPage />} />
                <Route path="report" element={<ReportPage />} />
                <Route path="profile" element={<ProfilePage />} />
                <Route path="admin/users" element={<AdminUsersPage />} />
              </Route>
            </Routes>
          </Suspense>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <App />,
);
