import { createContext, useContext, useEffect, useState, type PropsWithChildren } from "react";

import { getCurrentUserRequest, loginRequest } from "@/api/auth";
import { clearAccessToken, clearRole, getStoredAccessToken, getStoredRole, storeAccessToken, storeRole } from "@/shared/storage";
import type { User, UserRole } from "@/types/domain";

interface AuthContextValue {
  accessToken: string | null;
  currentUser: User | null;
  role: UserRole | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshCurrentUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: PropsWithChildren) {
  const [accessToken, setAccessToken] = useState<string | null>(getStoredAccessToken());
  const [role, setRole] = useState<UserRole | null>(getStoredRole());
  const [currentUser, setCurrentUser] = useState<User | null>(null);

  useEffect(() => {
    if (!accessToken) {
      return;
    }
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
      });
  }, [accessToken]);

  async function login(email: string, password: string) {
    const response = await loginRequest(email, password);
    storeAccessToken(response.data.access_token);
    setAccessToken(response.data.access_token);
    await getCurrentUserRequest().then((me) => {
      setCurrentUser(me.data);
      setRole(me.data.role);
      storeRole(me.data.role);
    });
  }

  function logout() {
    clearAccessToken();
    clearRole();
    setAccessToken(null);
    setRole(null);
    setCurrentUser(null);
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
