import { renderToStaticMarkup } from "react-dom/server";
import { describe,expect,it } from "vitest";
import { DesktopInnerPreview } from "./preview-desktop-pages";

describe("Figma-mapped desktop inner screens",()=>{
  it.each([
    {surface:"institution" as const,pageId:"people",frame:"244:113",title:"افراد سازمان"},
    {surface:"lender" as const,pageId:"guarantees",frame:"259:103",title:"ضمانت‌های تأمین‌کننده"},
    {surface:"admin" as const,pageId:"people",frame:"271:122",title:"مدیریت افراد"},
  ])("$surface / $pageId uses Figma frame $frame",({surface,pageId,frame,title})=>{
    const html=renderToStaticMarkup(<DesktopInnerPreview surface={surface} pageId={pageId}/>);
    expect(html).toContain('data-figma-frame="'+frame+'"');
    expect(html).toContain(title);
    expect(html).toMatch(/داده نمایشی|نمایش طراحی/);
  });
  it("offers only sample filters, not fake finance or permission mutation controls",()=>{
    for(const [surface,pageId] of [["institution","people"],["lender","guarantees"],["admin","people"]] as const){
      const html=renderToStaticMarkup(<DesktopInnerPreview surface={surface} pageId={pageId}/>);
      expect(html).not.toContain('type="submit"');
      expect(html).not.toContain("onClick=");
      expect(html).toContain('aria-pressed="true"');
    }
  });
  it("keeps lender's missing balance unknown instead of manufacturing a value",()=>{
    const html=renderToStaticMarkup(<DesktopInnerPreview surface="lender" pageId="guarantees"/>);
    expect(html).toContain("GU-۲۰۵");
    expect(html).toContain("در انتظار اطلاعات");
    expect(html).toContain("—");
  });
  it("labels missing authoritative program data and restricts display to synthetic names",()=>{
    const html=renderToStaticMarkup(<DesktopInnerPreview surface="admin" pageId="people"/>);
    expect(html).toContain("بدون مرجع قطعی");
    expect(html).toContain("نامشخص");
    expect(html).toContain("نام‌ها و ارقام این صفحه نمایشی");
  });
  it("does not display controls from unimplemented Figma pages",()=>{
    expect(DesktopInnerPreview({surface:"lender",pageId:"finance"})).toBeNull();
  });
});
