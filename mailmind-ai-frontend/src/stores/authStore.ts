import { create } from "zustand";
import { persist } from "zustand/middleware";

import { apiRequest } from "@/lib/api";
import type { AuthTokens, GoogleLoginResponse, User } from "@/types/auth";

interface AuthState {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setSession: (tokens: AuthTokens) => void;
  clearSession: () => void;
  fetchGoogleLoginUrl: () => Promise<GoogleLoginResponse>;
  exchangeSessionCode: (code: string) => Promise<void>;
  devLogin: () => Promise<void>;
  refreshSession: () => Promise<void>;
  logout: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      isLoading: false,

      setSession: (tokens) => {
        localStorage.setItem("mailmind_access_token", tokens.access_token);
        set({
          user: tokens.user,
          accessToken: tokens.access_token,
          isAuthenticated: true,
        });
      },

      clearSession: () => {
        localStorage.removeItem("mailmind_access_token");
        set({
          user: null,
          accessToken: null,
          isAuthenticated: false,
        });
      },

      fetchGoogleLoginUrl: () => apiRequest<GoogleLoginResponse>("/auth/google/login"),

      exchangeSessionCode: async (code) => {
        set({ isLoading: true });
        try {
          const tokens = await apiRequest<AuthTokens>("/auth/session/exchange", {
            method: "POST",
            body: JSON.stringify({ code }),
          });
          get().setSession(tokens);
        } finally {
          set({ isLoading: false });
        }
      },

      devLogin: async () => {
        set({ isLoading: true });
        try {
          const tokens = await apiRequest<AuthTokens>("/auth/dev/login", {
            method: "POST",
            body: JSON.stringify({}),
          });
          get().setSession(tokens);
        } finally {
          set({ isLoading: false });
        }
      },

      refreshSession: async () => {
        const tokens = await apiRequest<AuthTokens>("/auth/refresh", {
          method: "POST",
          body: JSON.stringify({}),
        });
        get().setSession(tokens);
      },

      logout: async () => {
        try {
          await apiRequest<{ message: string }>("/auth/logout", {
            method: "POST",
            body: JSON.stringify({}),
          });
        } finally {
          get().clearSession();
        }
      },
    }),
    {
      name: "mailmind-auth",
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        isAuthenticated: state.isAuthenticated,
      }),
    },
  ),
);
