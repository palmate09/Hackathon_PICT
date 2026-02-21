export const TOKEN_KEY = 'token';
export const USER_KEY = 'auth_user';
export const PROFILE_KEY = 'auth_profile';

const decodeBase64Url = (value: string): string | null => {
  try {
    const normalized = value.replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized.padEnd(normalized.length + ((4 - (normalized.length % 4)) % 4), '=');
    return atob(padded);
  } catch {
    return null;
  }
};

export const getTokenPayload = (token: string): Record<string, unknown> | null => {
  const parts = token.split('.');
  if (parts.length !== 3) {
    return null;
  }
  const payloadRaw = decodeBase64Url(parts[1]);
  if (!payloadRaw) {
    return null;
  }
  try {
    return JSON.parse(payloadRaw) as Record<string, unknown>;
  } catch {
    return null;
  }
};

export const isTokenExpired = (token: string, clockSkewSeconds: number = 30): boolean => {
  const payload = getTokenPayload(token);
  if (!payload) {
    return true;
  }
  const exp = payload.exp;
  if (typeof exp !== 'number') {
    return true;
  }
  const now = Math.floor(Date.now() / 1000);
  return exp <= now + clockSkewSeconds;
};

export const clearStoredAuth = () => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(PROFILE_KEY);
};
