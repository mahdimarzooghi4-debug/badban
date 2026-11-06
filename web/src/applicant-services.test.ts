import { describe, expect, it } from "vitest";
import { activeCatalogueServices } from "./applicant-services";

const active = (service_code: string, display_name: string) => ({
  service_code,
  display_name,
  description: "شرح معتبر از API",
  lifecycle_status: "ACTIVE",
});

describe("applicant Figma service cards backed by the live catalogue", () => {
  it("uses only active known backend services, with server names and canonical card order", () => {
    const result = activeCatalogueServices([
      active("POST_EXIT_SUPPORT", "پشتیبانی پس از خروج"),
      { ...active("MONTHLY_PENSION", "مستمری"), lifecycle_status: "DRAFT" },
      active("UNRECOGNIZED_SERVICE", "مجهول"),
      active("LOAN_GUARANTEE", "  ضمانت تسهیلات  "),
    ]);
    expect(result).toEqual([
      { service_code: "LOAN_GUARANTEE", display_name: "ضمانت تسهیلات", description: "شرح معتبر از API" },
      { service_code: "POST_EXIT_SUPPORT", display_name: "پشتیبانی پس از خروج", description: "شرح معتبر از API" },
    ]);
  });

  it("fails closed for empty, malformed, duplicate, or missing catalogue data", () => {
    expect(activeCatalogueServices(null)).toEqual([]);
    expect(activeCatalogueServices({ items: [] })).toEqual([]);
    expect(activeCatalogueServices([
      active("LOAN_GUARANTEE", "ضمانت اول"),
      active("LOAN_GUARANTEE", "ضمانت دوم"),
      { ...active("POST_EXIT_SUPPORT", "خدمت"), description: null },
      { ...active("MONTHLY_PENSION", "  "), description: "شرح" },
    ])).toEqual([]);
  });

  it("never turns a non-active entry or missing status into an offered service", () => {
    expect(activeCatalogueServices([
      { ...active("LOAN_GUARANTEE", "آزمایشی"), lifecycle_status: "INACTIVE" },
      { service_code: "MONTHLY_PENSION", display_name: "مستمری", description: "" },
    ])).toEqual([]);
  });
});
