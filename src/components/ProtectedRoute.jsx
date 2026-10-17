import { useEffect } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/lib/AuthContext';
import UserNotRegisteredError from '@/components/UserNotRegistered';

const DefaultFallback = () => (
  <div className="fixed inset-0 flex items-center justify-center">
    <div className="w-8 h-8 border-4 border-slate-200 border-t-slate-800 rounded-full animate-spin"></div>
  </div>
);

export default function ProtectedRoute({ fallback = <DefaultFallback />, unauthenticatedElement, roles }) {
  const { user, isAuthenticated, isLoadingAuth, authChecked, authError, checkUserAuth } = useAuth();
  const location = useLocation();

  useEffect(() => {
    if (!authChecked && !isLoadingAuth) {
      checkUserAuth();
    }
  }, [authChecked, isLoadingAuth, checkUserAuth]);

  if (isLoadingAuth || !authChecked) {
    return fallback;
  }

  if (authError) {
    if (authError.type === 'user_not_registered') {
      return <UserNotRegisteredError />;
    }
    if (authError.type !== 'auth_required') {
      return (
        <div role="alert" className="max-w-lg mx-auto px-4 py-16 text-center">
          <p className="text-destructive">{authError.message}</p>
          <button
            type="button"
            onClick={checkUserAuth}
            className="mt-4 text-sm font-medium text-primary hover:underline"
          >
            Retry connection
          </button>
        </div>
      );
    }
    return authError.type === 'auth_required' ? loginRedirect(location) : unauthenticatedElement;
  }

  if (!isAuthenticated) {
    return loginRedirect(location);
  }

  if (roles && !roles.includes(user?.role)) {
    return <Navigate to={user?.role === 'customer' ? '/dashboard' : '/workspace'} replace />;
  }

  return <Outlet />;
}

function loginRedirect(location) {
  const returnTo = `${location.pathname}${location.search}${location.hash}`;
  return <Navigate to={`/login?returnTo=${encodeURIComponent(returnTo)}`} replace />;
}
