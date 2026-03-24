import { createContext, useContext, useEffect, useState, type PropsWithChildren } from "react";

import { getCurrentUserRequest, loginRequest } from "@/api/auth";
import {
  AUTH_STORAGE_EVENT,
  clearAccessToken,
  clearRole,
  getStoredAccessToken,
  getStoredRole,
  storeAccessToken,
  storeRole,
} from "@/shared/storage";
import type { User, UserRole } from "@/types/domain";

interface AuthContextValue {
  accessToken: string | null;
  currentUser: User | null;
  role: UserRole | null;
  isAuthenticated: boolean;
  isAuthLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshCurrentUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: PropsWithChildren) {
  const [accessToken, setAccessToken] = useState<string | null>(getStoredAccessToken());
  const [role, setRole] = useState<UserRole | null>(getStoredRole());
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [isAuthLoading, setIsAuthLoading] = useState(Boolean(accessToken));

  useEffect(() => {
    function syncAuthStorage() {
      const nextToken = getStoredAccessToken();
      const nextRole = getStoredRole();
      setAccessToken(nextToken);
      setRole(nextRole);
      if (!nextToken) {
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
    if (!accessToken) {
      setCurrentUser(null);
      setIsAuthLoading(false);
      return;
    }
    setIsAuthLoading(true);
    void getCurrentUserRequest()
      .then((response) => {
        setCurrentUser(response.data);
        setRole(response.data.role);
        storeRole(response.data.role);
      })
      .catch(() => {
        clearAccessToken();
        clearRole();
        setAccessToken(null);
        setRole(null);
        setCurrentUser(null);
      })
      .finally(() => {
        setIsAuthLoading(false);
      });
  }, [accessToken]);

  async function login(email: string, password: string) {
    setIsAuthLoading(true);
    let storedNewToken = false;
    try {
      const response = await loginRequest(email, password);
      storeAccessToken(response.data.access_token);
      storedNewToken = true;
      setAccessToken(response.data.access_token);
      const me = await getCurrentUserRequest();
      setCurrentUser(me.data);
      setRole(me.data.role);
      storeRole(me.data.role);
    } catch (error) {
      if (storedNewToken) {
        clearAccessToken();
        clearRole();
        setAccessToken(null);
        setRole(null);
        setCurrentUser(null);
      }
      throw error;
    } finally {
      setIsAuthLoading(false);
    }
  }

  function logout() {
    clearAccessToken();
    clearRole();
    setAccessToken(null);
    setRole(null);
    setCurrentUser(null);
    setIsAuthLoading(false);
  }

  async function refreshCurrentUser() {
    if (!accessToken) {
      return;
    }
    const response = await getCurrentUserRequest();
    setCurrentUser(response.data);
    setRole(response.data.role);
    storeRole(response.data.role);
  }

  const value: AuthContextValue = {
    accessToken,
    currentUser,
    role,
    isAuthenticated: Boolean(accessToken),
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
