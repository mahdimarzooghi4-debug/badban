import type { ServiceCode } from "./api";

/** Only an active, unique backend catalogue entry may be offered for request intake. */
export type ActiveCatalogueService = {
  service_code: ServiceCode;
  display_name: string;
  description: string;
};

const serviceOrder: readonly ServiceCode[] = [
  "LOAN_GUARANTEE",
  "MONTHLY_PENSION",
  "POST_EXIT_SUPPORT",
];

function isServiceCode(value: unknown): value is ServiceCode {
  return value === "LOAN_GUARANTEE" || value === "MONTHLY_PENSION" || value === "POST_EXIT_SUPPORT";
}

export function activeCatalogueServices(items: unknown): ActiveCatalogueService[] {
  if (!Array.isArray(items)) return [];
  const byCode = new Map<ServiceCode, ActiveCatalogueService | null>();
  for (const item of items) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    if (!isServiceCode(row.service_code)) continue;
    const code = row.service_code;
    // Duplicate versions for a code are ambiguous: fail closed rather than guess.
    if (byCode.has(code)) {
      byCode.set(code, null);
      continue;
    }
    const name = row.display_name;
    const description = row.description;
    if (
      row.lifecycle_status !== "ACTIVE" ||
      typeof name !== "string" || !name.trim() ||
      typeof description !== "string"
    ) {
      byCode.set(code, null);
      continue;
    }
    byCode.set(code, { service_code: code, display_name: name.trim(), description });
  }
  return serviceOrder.flatMap(code => {
    const service = byCode.get(code);
    return service ? [service] : [];
  });
}
