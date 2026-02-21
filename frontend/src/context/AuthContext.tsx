import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { User, StudentProfile, CompanyProfile } from '../types';
import { authService } from '../services/authService';
import { facultyService } from '../services/facultyService';
import { TOKEN_KEY, USER_KEY, PROFILE_KEY, clearStoredAuth, isTokenExpired } from '../utils/authToken';

interface AuthResponse {
  token?: string;
  user: User;
  profile: StudentProfile | CompanyProfile | null;
  needs_skills_setup?: boolean;
}

interface AuthContextType {
  user: User | null;
  profile: StudentProfile | CompanyProfile | null;
  loading: boolean;
  login: (email: string, password: string, options?: { audience?: 'faculty' | 'default' }) => Promise<AuthResponse>;
  register: (email: string, password: string, role: string, profile: any) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const readStoredJSON = <T,>(key: string): T | null => {
  const raw = localStorage.getItem(key);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as T;
  } catch {
    localStorage.removeItem(key);
    return null;
  }
};

const persistAuthState = (data: { token?: string; user: User; profile: StudentProfile | CompanyProfile | null }) => {
  if (data.token) {
    localStorage.setItem(TOKEN_KEY, data.token);
  }
  localStorage.setItem(USER_KEY, JSON.stringify(data.user));
  if (data.profile) {
    localStorage.setItem(PROFILE_KEY, JSON.stringify(data.profile));
  } else {
    localStorage.removeItem(PROFILE_KEY);
  }
};

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => readStoredJSON<User>(USER_KEY));
  const [profile, setProfile] = useState<StudentProfile | CompanyProfile | null>(() =>
    readStoredJSON<StudentProfile | CompanyProfile>(PROFILE_KEY)
  );
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void checkAuth();
  }, []);

  const checkAuth = async () => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token || isTokenExpired(token)) {
      setUser(null);
      setProfile(null);
      clearStoredAuth();
      setLoading(false);
      return;
    }

    try {
      const data = await authService.getCurrentUser();
      setUser(data.user);
      setProfile(data.profile);
      persistAuthState(data);
    } catch (error: any) {
      if ([401, 403].includes(error?.response?.status)) {
        setUser(null);
        setProfile(null);
        clearStoredAuth();
      }
    }
    setLoading(false);
  };

  const login = async (email: string, password: string, options?: { audience?: 'faculty' | 'default' }) => {
    const data = options?.audience === 'faculty'
      ? await facultyService.login(email, password)
      : await authService.login(email, password);
    setUser(data.user);
    setProfile(data.profile);
    persistAuthState(data);
    return data;
  };

  const register = async (email: string, password: string, role: string, profileData: any) => {
    const data = await authService.register(email, password, role, profileData);
    if (data.token) {
      setUser(data.user);
      setProfile(data.profile);
      persistAuthState(data);
    }
  };

  const logout = () => {
    authService.logout();
    setUser(null);
    setProfile(null);
    clearStoredAuth();
  };

  const refreshUser = async () => {
    const data = await authService.getCurrentUser();
    setUser(data.user);
    setProfile(data.profile);
    persistAuthState(data);
  };

  return (
    <AuthContext.Provider value={{ user, profile, loading, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

