import { InMemoryWebStorage, UserManager, WebStorageStateStore } from "oidc-client-ts";
import { resolvePublicOidcConfig } from "./auth-config";

const runtime = (window as Window & { __BADBAN_PUBLIC_OIDC_CONFIG__?: unknown })
  .__BADBAN_PUBLIC_OIDC_CONFIG__;
const publicOidc = resolvePublicOidcConfig(
  runtime, import.meta.env.VITE_OIDC_AUTHORITY, import.meta.env.VITE_OIDC_CLIENT_ID,
);

/**
 * An access token exists only in memory, never localStorage, a URL, or a mock
 * session. The transient PKCE state must survive the OIDC redirect.
 * This baseline deliberately requires a new sign-in after a page reload.
 * A production BFF/session boundary is future work, not silently simulated.
 */
export const oidc = publicOidc
  ? new UserManager({
      authority: publicOidc.authority,
      client_id: publicOidc.clientId,
      response_type: "code",
      scope: "openid profile",
      redirect_uri: window.location.origin + "/auth/callback",
      userStore: new WebStorageStateStore({ store: new InMemoryWebStorage() }),
      stateStore: new WebStorageStateStore({ store: window.sessionStorage }),
      automaticSilentRenew: false,
      monitorSession: false,
    })
  : null;

export const isOidcConfigured = oidc !== null;

export async function beginSignIn(): Promise<void> {
  if (!oidc) throw new Error("اتصال احراز هویت هنوز پیکربندی نشده است.");
  await oidc.signinRedirect();
}

export async function completeSignIn(): Promise<string> {
  if (!oidc) throw new Error("احراز هویت پیکربندی نشده است.");
  const user = await oidc.signinRedirectCallback();
  if (!user.access_token || user.expired) throw new Error("نشست معتبر دریافت نشد.");
  window.history.replaceState(null, "", "/app");
  return user.access_token;
}

export async function localSignOut(): Promise<void> {
  // Local sign-out only. Do not claim IdP logout or backend token revocation.
  await oidc?.removeUser();
}
