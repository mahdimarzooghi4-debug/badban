export type ServiceCode = "LOAN_GUARANTEE" | "MONTHLY_PENSION" | "POST_EXIT_SUPPORT";
export type ServiceRequest = { id: string; service_code: ServiceCode; status: "RECEIVED"; submitted_at: string };
export type Page<T> = { items: T[]; limit: number; offset: number };
export type Service = { service_code: ServiceCode; display_name: string; description: string; lifecycle_status: string };
export type Balance = {
  currency: string;
  outstanding_principal: string | null;
  guarantee_exposure: string | null;
  realized_return_allocated_to_support: string | null;
  allocated_support: string | null;
  paid_amount: string | null;
  payment_status: "NOT_CONFIGURED";
};
export type FinancialCase = {
  participant_id: string;
  guarantee_cases: Array<{ id: string; status: string; guarantee_exposure: string; currency: string }>;
  monthly_entitlements: Array<{ id: string; amount: string; currency: string; status: string }>;
  post_exit_cases: Array<{ id: string; status: string }>;
  balances: Balance[];
  external_payment_status: "NOT_CONFIGURED";
};
export type Program = { program_id: string; code: string; name: string; status: string };
export type Beneficiary = {
  participant_id: string; episode_id: string; participation_status: string;
  consent_state: string; started_at: string;
};
export type Provider = { provider_id: string; provider_code: string; display_name: string };
export type Guarantee = {
  guarantee_case_id: string; case_state: string; currency: string;
  current_guarantee_exposure: string; outstanding_principal: string | null;
  loan_currency: string | null; loan_state: string | null;
};
export type AdminWorkspace = {
  workspace_code: string; scope_type: string; scope_id: string | null;
  service_code: string | null; role_codes: string[]; capabilities: string[];
};

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) { super(message); }
}

export function amount(value: string | number | null | undefined, currency?: string | null): string {
  if (value === null || value === undefined || value === "") return "اطلاعات موجود نیست";
  const parts = String(value).split(".");
  const integer = parts[0];
  if (!/^-?\d+$/.test(integer) || (parts[1] !== undefined && !/^\d+$/.test(parts[1]))) return "اطلاعات نامعتبر";
  const digits = integer.replace(/\B(?=(\d{3})+(?!\d))/g, "٬");
  const fraction = parts[1]?.replace(/0+$/, "");
  const shown = fraction ? digits + "٫" + fraction : digits;
  return shown + (currency ? " " + currency : "");
}

export async function api<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  if (!path.startsWith("/api/v1/") || path.includes("://") || path.includes("..")) {
    throw new Error("مسیر API نامعتبر است.");
  }
  if (!token) throw new ApiError(401, "برای مشاهده اطلاعات وارد حساب شوید.");
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: {
        Authorization: "Bearer " + token,
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
      credentials: "omit",
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "ارتباط با سرویس برقرار نشد.");
  }
  if (!response.ok) {
    const fallback = response.status === 403
      ? "دسترسی به این بخش برای حساب شما مجاز نیست."
      : response.status === 401
        ? "نشست شما معتبر نیست؛ دوباره وارد شوید."
        : "درخواست انجام نشد. " + response.status;
    throw new ApiError(response.status, fallback);
  }
  return response.json() as Promise<T>;
}

export const client = {
  catalogue: (token: string) => api<{ items: Service[] }>("/api/v1/service-catalogue", token),
  financial: (token: string) => api<FinancialCase>("/api/v1/applicant/financial-case", token),
  requests: (token: string) => api<Page<ServiceRequest>>("/api/v1/applicant/service-requests", token),
  submitRequest: (token: string, code: ServiceCode, idempotencyKey: string) =>
    api<ServiceRequest>("/api/v1/applicant/service-requests", token, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ service_code: code }),
    }),
  programs: (token: string) => api<Page<Program>>("/api/v1/support-institution/programs", token),
  beneficiaries: (token: string, programId: string) =>
    api<Page<Beneficiary>>("/api/v1/support-institution/programs/" + encodeURIComponent(programId) + "/beneficiaries", token),
  providers: (token: string) => api<Page<Provider>>("/api/v1/lender/providers", token),
  guarantees: (token: string, providerId: string) =>
    api<Page<Guarantee>>("/api/v1/lender/providers/" + encodeURIComponent(providerId) + "/guarantees", token),
  workspaces: (token: string) => api<{ items: AdminWorkspace[] }>("/api/v1/admin/workspace", token),
};
