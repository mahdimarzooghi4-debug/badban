import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { FinancialCase } from "./api";
import { ApplicantFinancialCase, financialAmount } from "./applicant-financial";

const pid = "123e4567-e89b-42d3-a456-426614174000";
const guaranteeId = "123e4567-e89b-42d3-a456-426614174001";
const monthId = "123e4567-e89b-42d3-a456-426614174002";

function fixture(): FinancialCase {
  return {
    participant_id: pid,
    guarantee_cases: [{
      id: guaranteeId, status: "ACTIVE", currency: "IRR",
      requested_principal: "10000000.00", guarantee_exposure: "10000000.00",
      lender_record_status: "NOT_RECORDED", loan_state: null,
      outstanding_principal: null,
    }],
    monthly_entitlements: [{
      id: monthId, period_reference: "1405-08", amount: "1000.00",
      currency: "IRR", status: "APPROVED", payment_status: "NOT_CONFIGURED",
    }],
    post_exit_cases: [],
    balances: [
      {
        currency: "IRR", outstanding_principal: "987654321.123456789012345678",
        guarantee_exposure: "10000000.00",
        realized_return_allocated_to_support: "-200.50",
        allocated_support: "900.00", paid_amount: null, payment_status: "NOT_CONFIGURED",
      },
      {
        currency: "USD", outstanding_principal: null, guarantee_exposure: null,
        realized_return_allocated_to_support: null, allocated_support: null,
        paid_amount: null, payment_status: "NOT_CONFIGURED",
      },
    ],
    external_price_source_status: "NOT_CONFIGURED",
    external_payment_status: "NOT_CONFIGURED",
  };
}

describe("Figma applicant finance 163:160", () => {
  it("localizes arbitrary precision exact amounts without rounding, float or currency mixing", () => {
    expect(financialAmount("987654321.123456789012345678", "IRR"))
      .toBe("۹۸۷٬۶۵۴٬۳۲۱٫۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸ IRR");
    expect(financialAmount(null, "IRR")).toBe("اطلاعات موجود نیست");
    expect(financialAmount("-200.50", "IRR")).toBe("-۲۰۰٫۵ IRR");
  });

  it("renders each currency as its own four-metric Figma panel with no invented total", () => {
    const html = renderToStaticMarkup(createElement(ApplicantFinancialCase, { data: fixture() }));
    expect(html).toContain("پرونده مالی من");
    expect(html).toContain("IRR");
    expect(html).toContain("USD");
    expect(html).toContain("۹۸۷٬۶۵۴٬۳۲۱٫۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸");
    expect(html).toContain("اطلاعات موجود نیست");
    expect(html.match(/applicant-financial-metric"/g)).toHaveLength(8);
    expect(html).not.toContain("مجموع ارزها");
    expect(html).not.toContain("۱۸۰ میلیون");
    expect(html).not.toContain("۱۱۲ میلیون");
  });

  it("binds details to recorded backend rows and does not claim paid or verified", () => {
    const html = renderToStaticMarkup(createElement(ApplicantFinancialCase, { data: fixture() }));
    expect(html).toContain(guaranteeId);
    expect(html).toContain(monthId);
    expect(html).toContain("آینه تسهیلات این پرونده هنوز ثبت نشده است");
    expect(html).toContain("اتصال تسویه انجام نشده است");
    expect(html).toContain("تأیید استحقاق به معنی پرداخت وجه نیست");
    expect(html).not.toContain("پرداخت‌شده");
    expect(html).not.toContain("راستی‌آزمایی شد");
  });

  it("references original versioned Figma icons and no temporary remote assets", () => {
    const html = renderToStaticMarkup(createElement(ApplicantFinancialCase, { data: fixture() }));
    for (const name of [
      "finance-wallet-gold.svg", "finance-shield.svg", "finance-wallet-white.svg",
      "finance-calendar.svg", "finance-chevron.svg",
    ]) expect(html).toContain("/assets/figma/" + name);
    expect(html).not.toContain("figma.com/api/mcp/asset");
  });

  it("shows no fictitious cash balance, requests or records when API returns empty arrays", () => {
    const data = fixture();
    data.guarantee_cases = []; data.monthly_entitlements = [];
    data.post_exit_cases = []; data.balances = [];
    const html = renderToStaticMarkup(createElement(ApplicantFinancialCase, { data }));
    expect(html).toContain("هنوز سبد مانده‌ای");
    expect(html).toContain("پرونده ضمانتی در پاسخ موجود نیست");
    expect(html).not.toContain("0 IRR");
    expect(html).not.toContain("قابل برداشت: ۰");
  });
});
