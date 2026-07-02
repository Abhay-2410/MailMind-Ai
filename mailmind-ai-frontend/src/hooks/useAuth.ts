import { API_BASE_URL } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";

export function useAuth() {
  const store = useAuthStore();

  const loginWithGoogle = () => {
    const origin = encodeURIComponent(window.location.origin);
    window.location.assign(`${API_BASE_URL}/auth/google/login/redirect?origin=${origin}`);
  };

  const loginDev = async () => {
    await store.devLogin();
  };

  return {
    user: store.user,
    isAuthenticated: store.isAuthenticated,
    isLoading: store.isLoading,
    loginWithGoogle,
    loginDev,
    logout: store.logout,
    exchangeSessionCode: store.exchangeSessionCode,
    refreshSession: store.refreshSession,
  };
}
