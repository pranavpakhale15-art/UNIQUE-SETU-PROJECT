import { Toaster } from "@/components/ui/toaster";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClientInstance } from "@/lib/query-client";
import {
  BrowserRouter as Router,
  Route,
  Routes,
  Navigate,
} from "react-router-dom";

import PageNotFound from "./lib/PageNotFound";
import { AuthProvider, useAuth } from "@/lib/AuthContext";
import UserNotRegisteredError from "@/components/UserNotRegistered";
import ScrollToTop from "./components/ScrollToTop";
import ProtectedRoute from "@/components/ProtectedRoute";
import Layout from "@/components/Layout";
import { LanguageProvider } from "@/lib/i18n/LanguageContext";

import Home from "@/pages/Home";
import ServiceDetail from "@/pages/ServiceDetail";
import CustomerDashboard from "@/pages/CustomerDashboard";
import NewApplication from "@/pages/NewApplication";
import ApplicationDetail from "@/pages/ApplicationDetail";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import ForgotPassword from "@/pages/ForgotPassword";
import ResetPassword from "@/pages/ResetPassword";
import RoleWorkspace from "@/pages/RoleWorkspace";

const AuthenticatedApp = () => {
  const {
    isLoadingAuth,
    isLoadingPublicSettings,
    authError,
    navigateToLogin,
  } = useAuth();

  if (isLoadingPublicSettings || isLoadingAuth) {
    return (
      <div className="fixed inset-0 flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-slate-200 border-t-slate-800 rounded-full animate-spin"></div>
      </div>
    );
  }

  if (authError) {
    if (authError.type === "user_not_registered") {
      return <UserNotRegisteredError />;
    }

    if (authError.type === "auth_required") {
      navigateToLogin();
      return null;
    }
  }

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />

      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/services/:slug" element={<ServiceDetail />} />

        <Route
          element={
            <ProtectedRoute
              unauthenticatedElement={<Navigate to="/login" replace />}
              roles={["customer"]}
            />
          }
        >
          <Route path="/dashboard" element={<CustomerDashboard />} />
          <Route path="/applications/new" element={<NewApplication />} />
        </Route>

        <Route
          element={
            <ProtectedRoute
              unauthenticatedElement={<Navigate to="/login" replace />}
              roles={["owner", "staff", "admin"]}
            />
          }
        >
          <Route path="/workspace" element={<RoleWorkspace />} />
        </Route>

        <Route
          element={
            <ProtectedRoute
              unauthenticatedElement={<Navigate to="/login" replace />}
            />
          }
        >
          <Route
            path="/applications/:id"
            element={<ApplicationDetail />}
          />
        </Route>
      </Route>

      <Route path="*" element={<PageNotFound />} />
    </Routes>
  );
};

function App() {
  return (
    <AuthProvider>
      <LanguageProvider>
        <QueryClientProvider client={queryClientInstance}>
          <Router>
            <ScrollToTop />
            <AuthenticatedApp />
          </Router>
          <Toaster />
        </QueryClientProvider>
      </LanguageProvider>
    </AuthProvider>
  );
}

export default App;