export interface PublicOidcConfig {
  authority: string;
  clientId: string;
}

/** Runtime metadata comes from same-origin backend; VITE values support local development. */
export function resolvePublicOidcConfig(
  runtime: unknown, buildAuthority: unknown, buildClientId: unknown,
): PublicOidcConfig | null {
  let authority: unknown = buildAuthority;
  let clientId: unknown = buildClientId;
  if (runtime !== undefined && runtime !== null) {
    if (typeof runtime !== "object" || Array.isArray(runtime)) return null;
    const values = runtime as Record<string, unknown>;
    authority = values.authority;
    clientId = values.clientId;
  }
  if (typeof authority !== "string" || typeof clientId !== "string") return null;
  const issuerText = authority.trim();
  const publicClientId = clientId.trim();
  if (!publicClientId || publicClientId.length > 128) return null;
  try {
    const issuer = new URL(issuerText);
    const local = issuer.protocol === "http:" &&
      ["localhost", "127.0.0.1"].includes(issuer.hostname);
    if ((!local && issuer.protocol !== "https:") || issuer.username || issuer.password ||
        issuer.hash || issuer.search || !issuer.hostname) return null;
    return { authority: issuerText.replace(/\/$/, ""), clientId: publicClientId };
  } catch {
    return null;
  }
}
