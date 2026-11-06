import type { Surface } from "./workspace-access";

const previewSurfaces: readonly Surface[] = ["individual", "institution", "lender", "admin"];

export function previewSurfaceFromLocation(pathname: string, search: string): Surface | null {
  // Never re-interpret an OIDC callback or an authenticated /app route as a public preview.
  if (pathname !== "/") return null;
  const query = new URLSearchParams(search);
  const selected = query.get("preview");
  if (!selected || !previewSurfaces.some(surface => surface === selected)) return null;
  return selected as Surface;
}

export function previewSurfaceUrl(surface: Surface): string {
  return "/?preview=" + encodeURIComponent(surface);
}
