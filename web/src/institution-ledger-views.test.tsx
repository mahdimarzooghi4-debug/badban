import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { InstitutionHistoryView, InstitutionReportsView } from "./institution-ledger-views";

describe("supporting institution ledger pages", () => {
  it("labels financial history as internal Badban journal evidence", () => {
    const html = renderToStaticMarkup(createElement(InstitutionHistoryView, { token: "test-token" }));
    expect(html).toContain("ثبت داخلی؛ نه تأیید انتقال بانکی");
    expect(html).toContain("برنامه مجاز سازمان");
    expect(html).toContain("انتخاب برنامه");
    expect(html).not.toContain("شناسه تراکنش بانکی");
    expect(html).not.toContain("در انتظار پرداخت");
  });

  it("keeps the report page free of undefined KPIs and fake totals", () => {
    const html = renderToStaticMarkup(createElement(InstitutionReportsView, { token: "test-token" }));
    expect(html).toContain("ثبت داخلی؛ نه تأیید انتقال بانکی");
    expect(html).toContain("برنامه مجاز سازمان");
    expect(html).not.toContain("۱٫۸ میلیارد");
    expect(html).not.toContain("درصد بازده");
    expect(html).not.toContain("جمع کل همه ارزها");
  });
});
