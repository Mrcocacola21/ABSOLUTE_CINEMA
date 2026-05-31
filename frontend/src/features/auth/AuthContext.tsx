import { createContext, useContext, useEffect, useState, type PropsWithChildren } from "react";

import { getCurrentUserRequest, loginRequest } from "@/api/auth";
import { refreshStoredAccessToken } from "@/api/client";
import {
  AUTH_STORAGE_EVENT,
  clearAuthStorage,
  getStoredAccessToken,
  getStoredRefreshToken,
  getStoredRole,
  storeAuthTokens,
  storeRole,
} from "@/shared/storage";
import type { User, UserRole } from "@/types/domain";

interface AuthContextValue {
  accessToken: string | null;
  refreshToken: string | null;
  currentUser: User | null;
  role: UserRole | null;
  isAuthenticated: boolean;
  isAuthLoading: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
  refreshCurrentUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: PropsWithChildren) {
  const [accessToken, setAccessToken] = useState<string | null>(getStoredAccessToken());
  const [refreshToken, setRefreshToken] = useState<string | null>(getStoredRefreshToken());
  const [role, setRole] = useState<UserRole | null>(getStoredRole());
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [isAuthLoading, setIsAuthLoading] = useState(Boolean(accessToken || refreshToken));

  useEffect(() => {
    function syncAuthStorage() {
      const nextToken = getStoredAccessToken();
      const nextRefreshToken = getStoredRefreshToken();
      const nextRole = getStoredRole();
      setAccessToken(nextToken);
      setRefreshToken(nextRefreshToken);
      setRole(nextRole);
      if (!nextToken && !nextRefreshToken) {
        setCurrentUser(null);
        setIsAuthLoading(false);
      }
    }

    window.addEventListener(AUTH_STORAGE_EVENT, syncAuthStorage);
    return () => {
      window.removeEventListener(AUTH_STORAGE_EVENT, syncAuthStorage);
    };
  }, []);

  useEffect(() => {
    let isCurrent = true;

    async function restoreSession() {
      if (!accessToken && !refreshToken) {
        setCurrentUser(null);
        setIsAuthLoading(false);
        return;
      }

      setIsAuthLoading(true);
      try {
        let activeAccessToken = getStoredAccessToken();
        if (!activeAccessToken && getStoredRefreshToken()) {
          activeAccessToken = await refreshStoredAccessToken();
          if (isCurrent) {
            setAccessToken(activeAccessToken);
          }
        }

        const response = await getCurrentUserRequest();
        if (!isCurrent) {
          return;
        }
        setCurrentUser(response.data);
        setRole(response.data.role);
        storeRole(response.data.role);
      } catch {
        clearAuthStorage();
        if (!isCurrent) {
          return;
        }
        setAccessToken(null);
        setRefreshToken(null);
        setRole(null);
        setCurrentUser(null);
      } finally {
        if (isCurrent) {
          setIsAuthLoading(false);
        }
      }
    }

    void restoreSession();
    return () => {
      isCurrent = false;
    };
  }, [accessToken, refreshToken]);

  async function login(email: string, password: string) {
    setIsAuthLoading(true);
    let storedNewTokens = false;
    try {
      const response = await loginRequest(email, password);
      storeAuthTokens({
        accessToken: response.data.access_token,
        refreshToken: response.data.refresh_token,
      });
      storedNewTokens = true;
      setAccessToken(response.data.access_token);
      setRefreshToken(response.data.refresh_token);
      const me = await getCurrentUserRequest();
      setCurrentUser(me.data);
      setRole(me.data.role);
      storeRole(me.data.role);
      return me.data;
    } catch (error) {
      if (storedNewTokens) {
        clearAuthStorage();
        setAccessToken(null);
        setRefreshToken(null);
        setRole(null);
        setCurrentUser(null);
      }
      throw error;
    } finally {
      setIsAuthLoading(false);
    }
  }

  function logout() {
    clearAuthStorage();
    setAccessToken(null);
    setRefreshToken(null);
    setRole(null);
    setCurrentUser(null);
    setIsAuthLoading(false);
  }

  async function refreshCurrentUser() {
    if (!accessToken && !refreshToken) {
      setCurrentUser(null);
      return;
    }
    const response = await getCurrentUserRequest();
    setCurrentUser(response.data);
    setRole(response.data.role);
    storeRole(response.data.role);
  }

  const value: AuthContextValue = {
    accessToken,
    refreshToken,
    currentUser,
    role,
    isAuthenticated: Boolean(accessToken && currentUser),
    isAuthLoading,
    login,
    logout,
    refreshCurrentUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider.");
  }
  return context;
}
