export type InstitutionView = "home" | "history" | "reports";

/** Only these already-defined institution sections are navigable in this release. */
export function institutionViewForNavigationIndex(index: number): InstitutionView | null {
  if (index === 0) return "home";
  if (index === 3) return "history";
  if (index === 4) return "reports";
  return null;
}
