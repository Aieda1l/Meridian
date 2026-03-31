/**
 * Admin dashboard authentication context — delegates to the shared auth-client module.
 */
import { createAuthProvider, useAuth } from '../../../shared/auth-client/useAuth';
import { apiFetch } from '../api/client';

const STORAGE_KEY_TOKEN = 'admin_access_token';
const STORAGE_KEY_USER = 'meridian_admin_user';

const { AuthProvider } = createAuthProvider({
  storageKeyToken: STORAGE_KEY_TOKEN,
  storageKeyUser: STORAGE_KEY_USER,
  apiFetch,
});

export { AuthProvider, useAuth };
