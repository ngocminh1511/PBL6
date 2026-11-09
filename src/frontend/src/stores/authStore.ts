import { create } from 'zustand';
import { User } from '../lib/types';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  setUser: (user: User | null, token?: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: typeof window !== 'undefined' ? localStorage.getItem('lexgraph_token') : null,
  isAuthenticated: false,
  setUser: (user, token) => {
    if (token && typeof window !== 'undefined') {
      localStorage.setItem('lexgraph_token', token);
    }
    set({ user, token: token || null, isAuthenticated: !!user });
  },
  logout: () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('lexgraph_token');
    }
    set({ user: null, token: null, isAuthenticated: false });
  },
}));

