import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Beneficiary } from "./api";
import type { InstitutionFinancialCase } from "./operational-data";
import { InstitutionCaseOverview } from "./institution-case-overview";

const programId = "11111111-1111-4111-8111-111111111111";
const participantId = "22222222-2222-4222-8222-222222222222";
const episodeId = "33333333-3333-4333-8333-333333333333";
const assetId = "44444444-4444-4444-8444-444444444444";
const personalAssetId = "55555555-5555-4555-8555-555555555555";

const participant: Beneficiary = {
  participant_id: participantId, episode_id: episodeId,
  participation_status: "ACTIVE", consent_state: "RECORDED",
  started_at: "2026-01-01T00:00:00Z",
};
const base: InstitutionFinancialCase = {
  program_id: programId, participant_id: participantId, episode_id: episodeId,
  assets: [], guarantees: [], monthly_pension_entitlements: [],
  post_exit_support_cases: [], program_return_allocations: [],
};
const scope = { programId, programName: "برنامهٔ واقعی سازمان", participant };
function render(data: InstitutionFinancialCase, selected = scope): string {
  return renderToStaticMarkup(createElement(InstitutionCaseOverview, { data, scope: selected }));
}

describe("Figma institution / 04 person finance case", () => {
  it("renders only backend-grounded program and person identifiers, not Figma sample names", () => {
    const html = render(base);
    expect(html).toContain("برنامهٔ واقعی سازمان");
    expect(html).toContain(participantId);
    expect(html).toContain(episodeId);
    expect(html).toContain("رضایت ثبت‌شده");
    expect(html).toContain("مبلغ تجمیعی در این API ارائه نشده است");
    expect(html).toContain("وضعیت تأمین وجه یا پرداخت");
    expect(html).not.toContain("مریم احمدی");
    expect(html).not.toContain("۱۵۰٬۰۰۰٬۰۰۰");
    expect(html).not.toContain("BD-P-۱۰۱");
  });

  it("distinguishes organizational attribution from actual personal ownership without multiplying quantities", () => {
    const asset = {
      id: assetId, asset_code: "GOLD", asset_name: "دارایی مرجع",
      ownership_funding_type: "PROGRAM_ATTRIBUTED", quantity: "12.500000000000000000",
      unit_code: "GRAM", lifecycle_status: "RECORDED", valuation_observations: [],
    };
    const html = render({ ...base, assets: [
      asset, { ...asset, id: personalAssetId, ownership_funding_type: "PARTICIPANT_OWNED" },
    ] });
    expect(html).toContain("۱ مورد با انتساب سازمانی");
    expect(html).toContain("دارایی شخصی ثبت‌شده در این پاسخ: ۱ مورد");
    expect(html).toContain("مالک اصل: سازمان");
    expect(html).toContain("مقدار ثبت‌شده");
    expect(html).toContain("GRAM");
    expect(html).not.toContain("مجموع ارزش دارایی");
    expect(html).not.toContain("میلیون ریال");
  });

  it("does not fabricate entitlement, settlement, payment, cash withdrawal or personal names", () => {
    const html = render(base);
    expect(html).toContain("دارایی با مالکیت سازمانی در این پرونده گزارش نشده است.");
    expect(html).toContain("در قرارداد فعلی این API گزارش نشده است.");
    expect(html).toContain("انتساب وجه یا دارایی سازمانی، مالکیت اصل سرمایه را منتقل نمی‌کند");
    expect(html).not.toContain("پرداخت‌شده");
    expect(html).not.toContain("وجه واریزشده");
    expect(html).not.toContain("قابل برداشت: ");
  });

  it("refuses to render a case from a different authorized program, individual or episode", () => {
    expect(() => render({ ...base, program_id: personalAssetId })).toThrow("تطابق ندارد");
    expect(() => render({ ...base, participant_id: personalAssetId })).toThrow("تطابق ندارد");
    expect(() => render({ ...base, episode_id: personalAssetId })).toThrow("تطابق ندارد");
    expect(() => render(base, {
      ...scope, participant: { ...participant, episode_id: personalAssetId },
    })).toThrow("تطابق ندارد");
  });

  it("uses original native Figma icons, not temporary links or icon substitutes", () => {
    const html = render(base);
    expect(html).toContain("/assets/figma/institution-person.svg");
    expect(html).toContain("/assets/figma/institution-lock.svg");
    expect(html).not.toContain("figma.com/api/mcp/asset/");
  });
});
