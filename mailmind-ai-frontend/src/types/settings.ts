export type ThemePreference = "light" | "dark" | "system";

export interface AccountSummary {
  id: string;
  email: string;
  display_name: string | null;
  is_primary: boolean;
  is_active: boolean;
  last_synced_at: string | null;
}

export interface SettingsResponse {
  user_id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  display_name: string | null;
  timezone: string;
  ai_provider: string;
  ai_model: string;
  theme: ThemePreference;
  google_connected: boolean;
  accounts: AccountSummary[];
}

export interface UpdateSettingsPayload {
  full_name?: string | null;
  display_name?: string | null;
  timezone?: string;
  ai_provider?: string;
  ai_model?: string;
  theme?: ThemePreference;
}

export interface AIModelOption {
  id: string;
  name: string;
  provider: string;
  description: string;
  is_default: boolean;
}

export const TIMEZONE_OPTIONS = [
  { value: "UTC", label: "UTC" },
  { value: "America/New_York", label: "Eastern Time (US)" },
  { value: "America/Chicago", label: "Central Time (US)" },
  { value: "America/Denver", label: "Mountain Time (US)" },
  { value: "America/Los_Angeles", label: "Pacific Time (US)" },
  { value: "Europe/London", label: "London" },
  { value: "Europe/Paris", label: "Paris / Berlin" },
  { value: "Asia/Kolkata", label: "India (IST)" },
  { value: "Asia/Tokyo", label: "Tokyo" },
  { value: "Australia/Sydney", label: "Sydney" },
] as const;

export const THEME_OPTIONS: { value: ThemePreference; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
];
