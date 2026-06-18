export interface User {
  id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface GoogleLoginResponse {
  authorization_url: string;
  state: string;
}

export interface AuthStatus {
  authenticated: boolean;
  user: User | null;
}
