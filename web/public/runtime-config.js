// Render's same-origin backend overrides this placeholder with its public issuer/client ID.
// Local Vite development uses the VITE_OIDC_* public environment settings instead.
window.__BADBAN_PUBLIC_OIDC_CONFIG__ = undefined;
