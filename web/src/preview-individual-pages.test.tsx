import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { IndividualPreviewPage } from "./preview-individual-pages";

const pages = [
  { pageId: "services", frame: "163:2", title: "خدمات بادبان", marker: "سه مسیر، یک پرونده مالی" },
  { pageId: "requests", frame: "163:81", title: "درخواست‌های من", marker: "RECEIVED" },
  { pageId: "finance", frame: "163:160", title: "پرونده مالی من", marker: "تعهد ضمانتی" },
  { pageId: "profile", frame: "163:239", title: "حساب من", marker: "تنظیمات و اطلاعات حساب" },
] as const;

describe("Figma mobile inner-page previews", () => {
  it.each(pages)("renders $pageId against its canonical Figma frame $frame", ({pageId,frame,title,marker}) => {
    const markup = renderToStaticMarkup(<IndividualPreviewPage pageId={pageId} onNavigate={() => undefined}/>);
    expect(markup).toContain('data-figma-frame="' + frame + '"');
    expect(markup).toContain(title);
    expect(markup).toContain(marker);
  });

  it("keeps service exploration presentation-only rather than exposing a request submission", () => {
    const markup = renderToStaticMarkup(<IndividualPreviewPage pageId="services" onNavigate={() => undefined}/>);
    expect(markup).toContain("جزئیات خدمت");
    expect(markup).not.toContain("type=\"submit\"");
    expect(markup).toContain("هیچ فرم یا درخواست واقعی ارسال نمی‌شود");
  });

  it("renders four nonmutating demo request filter buttons and only synthetic request IDs", () => {
    const markup = renderToStaticMarkup(<IndividualPreviewPage pageId="requests" onNavigate={() => undefined}/>);
    expect(markup.match(/aria-pressed=/g)).toHaveLength(4);
    expect(markup.match(/BD-RQ-/g)).toHaveLength(3);
    expect(markup).not.toContain('type="submit"');
  });

  it("labels financial figures as synthetic and preserves the independent meaning of received", () => {
    const finance = renderToStaticMarkup(<IndividualPreviewPage pageId="finance" onNavigate={() => undefined}/>);
    expect(finance.match(/ریال • نمونه/g)).toHaveLength(4);
    expect(finance).toContain("هیچ مانده بانکی یا حق برداشت واقعی");
    const requests = renderToStaticMarkup(<IndividualPreviewPage pageId="requests" onNavigate={() => undefined}/>);
    expect(requests).toContain("نه تأیید خدمت، تخصیص سرمایه یا پرداخت");
  });

  it("never offers a fake logout or identity verification action in the public preview", () => {
    const markup = renderToStaticMarkup(<IndividualPreviewPage pageId="profile" onNavigate={() => undefined}/>);
    expect(markup).toContain("حساب و هویت در این نما ساختگی‌اند");
    expect(markup).not.toContain("خروج محلی");
    expect(markup).not.toContain("auth/callback");
  });
});
