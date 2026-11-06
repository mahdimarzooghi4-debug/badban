import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { InstitutionHistoryView, InstitutionReportsView } from "./institution-empty-views";

describe("supporting institution finance empty-state pages", () => {
  it("activates financial history without presenting sample transactions or payment claims", () => {
    const html = renderToStaticMarkup(createElement(InstitutionHistoryView));
    expect(html).toContain("گردش تأمین سرمایه نقدی");
    expect(html).toContain("منبع داده مالی متصل نیست");
    expect(html).toContain("هنوز سابقه مالی برای نمایش وجود ندارد");
    expect(html).toContain("وضعیت درخواست تأمین وجه و پرداخت واقعی یکسان نیستند");
    expect(html).toContain("هیچ نام، مبلغ، شناسه تراکنش یا وضعیت پرداختی نمایش داده نمی‌شود");
    expect(html).not.toContain("مریم احمدی");
    expect(html).not.toContain("علی مرادی");
    expect(html).not.toContain("BD-F-۱۰۱");
    expect(html).not.toContain("۱۵۰ میلیون ریال");
    expect(html).not.toContain("۱۲۰ میلیون ریال");
    expect(html).not.toContain("در انتظار پرداخت");
    expect(html).not.toContain("داده نمایشی");
    expect(html).not.toContain("<button");
    expect(html).not.toContain("<form");
  });

  it("activates reporting without fake aggregate amounts, headcounts, percentages or charts", () => {
    const html = renderToStaticMarkup(createElement(InstitutionReportsView));
    expect(html).toContain("ترکیب سرمایه سازمانی");
    expect(html).toContain("شاخص‌های گزارش");
    expect(html).toContain("داده تجمیعی در دسترس نیست");
    expect(html).toContain("گزارش تجمیعی هنوز آماده نیست");
    expect(html).toContain("هیچ عدد، درصد یا نمودار فرضی نمایش داده نمی‌شود");
    expect(html).toContain("فقط برنامه‌های دارای مجوز سازمان");
    expect(html).toContain("تفکیک اصل سرمایه از حقوق منتفع");
    expect(html).toContain("گزارش رسمی یا فایل قابل ارائه به حسابرسی تولید نمی‌کند");
    expect(html).not.toContain("۱۸ نفر");
    expect(html).not.toContain("۱٫۸ میلیارد");
    expect(html).not.toContain("۱٫۲ میلیارد");
    expect(html).not.toContain("۶۰۰ میلیون");
    expect(html).not.toContain("مریم احمدی");
    expect(html).not.toContain("<button");
    expect(html).not.toContain("<form");
  });

  it("keeps the pages strictly informational and marks the empty states accessibly", () => {
    const history = renderToStaticMarkup(createElement(InstitutionHistoryView));
    const reports = renderToStaticMarkup(createElement(InstitutionReportsView));
    expect(history).toContain('role="status"');
    expect(reports).toContain('role="status"');
    expect(history).toContain('aria-label="سوابق مالی سازمان"');
    expect(reports).toContain('aria-label="گزارش‌های سازمان"');
  });
});
