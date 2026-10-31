import React, { createContext, useState, useContext, useEffect, useCallback } from 'react';
import { APIError, getCurrentUser, logoutUser } from '@/api/backendClient';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoadingAuth, setIsLoadingAuth] = useState(true);
  const [isLoadingPublicSettings, setIsLoadingPublicSettings] = useState(false);
  const [authError, setAuthError] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [appPublicSettings, setAppPublicSettings] = useState(null);

  useEffect(() => {
    checkAppState();
  }, []);

  const checkAppState = async () => {
    try {
      setIsLoadingPublicSettings(false);
      setAuthError(null);
      await checkUserAuth();
    } catch (error) {
      console.error('Unexpected error:', error);
      setAuthError({
        type: 'unknown',
        message: error.message || 'An unexpected error occurred'
      });
      setIsLoadingAuth(false);
    }
  };

  const checkUserAuth = useCallback(async () => {
    try {
      setIsLoadingAuth(true);
      const currentUser = await getCurrentUser();
      setUser(currentUser);
      setIsAuthenticated(true);
      setAuthError(null);
      setIsLoadingAuth(false);
      setAuthChecked(true);
      return currentUser;
    } catch (error) {
      if (!(error instanceof APIError && error.status === 401)) {
        console.error('User auth check failed:', error);
      }
      setUser(null);
      setIsAuthenticated(false);
      setIsLoadingAuth(false);
      setAuthChecked(true);

      if (error instanceof APIError && error.status !== 401) {
        setAuthError({
          type: 'backend_error',
          message: error.message
        });
      } else if (!(error instanceof APIError)) {
        setAuthError({
          type: 'backend_error',
          message: error.message || 'Unable to connect to the backend'
        });
      } else {
        setAuthError(null);
      }
      return null;
    }
  }, []);

  const logout = useCallback(async (shouldRedirect = true) => {
    await logoutUser();
    setUser(null);
    setIsAuthenticated(false);
    setAuthError(null);
    setAuthChecked(true);

    if (shouldRedirect) {
      window.location.href = '/login';
    }
  }, []);

  const setAuthenticatedUser = useCallback((authenticatedUser) => {
    setUser(authenticatedUser);
    setIsAuthenticated(Boolean(authenticatedUser));
    setAuthError(null);
    setIsLoadingAuth(false);
    setAuthChecked(true);
  }, []);

  useEffect(() => {
    const handlePageShow = (event) => {
      if (event.persisted) checkUserAuth();
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') checkUserAuth();
    };
    window.addEventListener('pageshow', handlePageShow);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      window.removeEventListener('pageshow', handlePageShow);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [checkUserAuth]);

  return (
    <AuthContext.Provider value={{ 
      user, 
      isAuthenticated, 
      isLoadingAuth,
      isLoadingPublicSettings,
      authError,
      appPublicSettings,
      authChecked,
      logout,
      setAuthenticatedUser,
      checkUserAuth,
      checkAppState
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
