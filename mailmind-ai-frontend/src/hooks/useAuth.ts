import { useAuthStore } from "@/stores/authStore";

export function useAuth() {
  const store = useAuthStore();

  const loginWithGoogle = async () => {
    const { authorization_url } = await store.fetchGoogleLoginUrl();
    window.location.assign(authorization_url);
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
