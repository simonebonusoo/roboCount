import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const authRevisionRef = useRef(0);

  useEffect(() => {
    let isMounted = true;
    const requestRevision = authRevisionRef.current;

    async function bootstrap() {
      try {
        const response = await api.get("/api/auth/me");
        if (!isMounted || requestRevision !== authRevisionRef.current) {
          return;
        }
        setUser(response.user);
        setIsAuthenticated(true);
      } catch (error) {
        if (!isMounted || requestRevision !== authRevisionRef.current) {
          return;
        }
        setUser(null);
        setIsAuthenticated(false);
      } finally {
        if (isMounted && requestRevision === authRevisionRef.current) {
          setIsLoading(false);
        }
      }
    }

    bootstrap();

    return () => {
      isMounted = false;
    };
  }, []);

  async function login(credentials) {
    authRevisionRef.current += 1;
    const requestRevision = authRevisionRef.current;
    setIsLoading(true);

    try {
      await api.post("/api/auth/login", credentials);
      const response = await api.get("/api/auth/me");
      if (requestRevision !== authRevisionRef.current) {
        return response.user;
      }
      setUser(response.user);
      setIsAuthenticated(true);
      return response.user;
    } catch (error) {
      if (requestRevision === authRevisionRef.current) {
        setUser(null);
        setIsAuthenticated(false);
      }
      throw error;
    } finally {
      if (requestRevision === authRevisionRef.current) {
        setIsLoading(false);
      }
    }
  }

  async function logout() {
    authRevisionRef.current += 1;
    const requestRevision = authRevisionRef.current;
    setIsLoading(true);

    try {
      await api.post("/api/auth/logout", {});
    } finally {
      if (requestRevision === authRevisionRef.current) {
        setUser(null);
        setIsAuthenticated(false);
        setIsLoading(false);
      }
    }
  }

  async function refreshUser() {
    authRevisionRef.current += 1;
    const requestRevision = authRevisionRef.current;
    const response = await api.get("/api/auth/me");
    if (requestRevision === authRevisionRef.current) {
      setUser(response.user);
      setIsAuthenticated(true);
      setIsLoading(false);
    }
    return response.user;
  }

  const value = useMemo(
    () => ({
      user,
      isLoading,
      isAuthenticated,
      login,
      logout,
      refreshUser,
      setUser,
    }),
    [user, isLoading, isAuthenticated],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
