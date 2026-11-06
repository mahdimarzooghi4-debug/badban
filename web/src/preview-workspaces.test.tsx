import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { PreviewWorkspace } from "./preview-workspaces";
import type { Surface } from "./workspace-access";

const cases: Array<{ surface: Surface; frame: string; heading: string }> = [
  { surface: "individual", frame: "160:3", heading: "سلام، نگارا! خوش اومدی" },
  { surface: "institution", frame: "244:3", heading: "داشبورد سازمان" },
  { surface: "lender", frame: "259:3", heading: "داشبورد تأمین‌کننده" },
  { surface: "admin", frame: "271:3", heading: "داشبورد مدیریت" },
];

describe("Figma-aligned Badban preview shells", () => {
  it.each(cases)("renders the $surface preview against Figma frame $frame", ({ surface, frame, heading }) => {
    const markup = renderToStaticMarkup(
      <PreviewWorkspace surface={surface} onBack={() => undefined} />,
    );
    expect(markup).toContain('data-figma-frame="' + frame + '"');
    expect(markup).toContain(heading);
    expect(markup).toMatch(/داده نمایشی|داده‌های نمایشی|نمایش طراحی/);
  });

  it("renders the individual surface as a mobile app with the five Figma bottom-navigation destinations", () => {
    const markup = renderToStaticMarkup(
      <PreviewWorkspace surface="individual" onBack={() => undefined} />,
    );
    expect(markup).toContain('class="mobile-screen"');
    expect(markup).toContain('aria-label="پیمایش اصلی"');
    for (const label of ["حساب", "درخواست‌ها", "خدمات", "مالی", "خانه"]) {
      expect(markup).toContain(label);
    }
  });

  it("renders organization, lender and admin surfaces with their own right-side navigation", () => {
    for (const surface of ["institution", "lender", "admin"] as const) {
      const markup = renderToStaticMarkup(
        <PreviewWorkspace surface={surface} onBack={() => undefined} />,
      );
      expect(markup).toContain('class="preview-sidebar preview-sidebar--' + surface + '"');
      expect(markup).toContain("پیش‌نمایش محصول");
      expect(markup).not.toContain("preview-role-switcher");
    }
  });

  it("keeps the financial and administrative preview actions explicitly sample-only", () => {
    const organization = renderToStaticMarkup(
      <PreviewWorkspace surface="institution" onBack={() => undefined} />,
    );
    const admin = renderToStaticMarkup(
      <PreviewWorkspace surface="admin" onBack={() => undefined} />,
    );
    expect(organization).toContain("بدون انتقال مالکیت");
    expect(admin).toContain("دسترسی مدیریتی به معنی مجوز اقدام مالی یا انتشار نیست");
  });
});
