import { useState } from "react";
import { previewWorkspaces } from "./preview-data";
import type { Surface } from "./workspace-access";
import "./preview-workspaces.css";
import { IndividualPreviewPage } from "./preview-individual-pages";

type WorkspacePage = {
  title: string;
  description: string;
  metrics?: Array<{ label: string; value: string; detail: string }>;
  sections: Array<{
    title: string;
    description?: string;
    columns?: string[];
    rows?: string[][];
    items?: Array<{ title: string; description: string; meta?: string }>;
    emptyText?: string;
  }>;
  note?: string;
};

type Workspace = (typeof previewWorkspaces)[Surface];

function Icon({ name, size = 22 }: { name: string; size?: number }) {
  const common = {
    width: size, height: size, viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const, "aria-hidden": true as const,
    focusable: false as const,
  };
  switch (name) {
    case "grid": return <svg {...common}><rect x="3" y="3" width="7" height="7" rx="1.3"/><rect x="14" y="3" width="7" height="7" rx="1.3"/><rect x="3" y="14" width="7" height="7" rx="1.3"/><rect x="14" y="14" width="7" height="7" rx="1.3"/></svg>;
    case "users": return <svg {...common}><circle cx="9" cy="8" r="3.2"/><path d="M3 20v-1.2a5.8 5.8 0 0 1 11.6 0V20M16 5.2a3.1 3.1 0 0 1 0 5.9M18 14.4a4.7 4.7 0 0 1 3 4.4V20"/></svg>;
    case "wallet": return <svg {...common}><rect x="3" y="5" width="18" height="15" rx="2.2"/><path d="M3 9h18M16 14h2"/></svg>;
    case "history": return <svg {...common}><path d="M3.2 11a8.8 8.8 0 1 1 .7 4.8M3 4v6h6M12 7v5l3.2 2"/></svg>;
    case "chart": return <svg {...common}><path d="M3 3v18h18M7 15l4-4 3 2 6-7"/></svg>;
    case "shield": return <svg {...common}><path d="M12 2.8 20 6v5.3c0 5.1-3.4 8.3-8 10.1-4.6-1.8-8-5-8-10.1V6l8-3.2Z"/><path d="m8.5 12 2.2 2.2 4.8-5"/></svg>;
    case "bank": return <svg {...common}><path d="m2.5 8 9.5-5 9.5 5M4 9h16M5 9v10M9.5 9v10M14.5 9v10M19 9v10M3 21h18"/></svg>;
    case "building": return <svg {...common}><path d="M4 21V4.5L13 2v19M13 8h7v13M2 21h20M7 7h2M7 11h2M7 15h2M16 12h1M16 16h1"/></svg>;
    case "scale": return <svg {...common}><path d="M12 3v18M5 6h14M7 6l-4 7h8L7 6Zm10 0-4 7h8l-4-7ZM7 21h10"/></svg>;
    case "sliders": return <svg {...common}><path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2" fill="currentColor"/><circle cx="15" cy="12" r="2" fill="currentColor"/><circle cx="8" cy="18" r="2" fill="currentColor"/></svg>;
    case "key": return <svg {...common}><circle cx="8" cy="15" r="5"/><path d="m11.5 11.5 8-8M16 7l2 2M18.5 4.5l2 2"/></svg>;
    case "bell": return <svg {...common}><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></svg>;
    case "chevron": return <svg {...common}><path d="m15 18-6-6 6-6"/></svg>;
    case "account": return <svg {...common}><circle cx="12" cy="7.5" r="4"/><path d="M4.5 21v-1.8a7.5 7.5 0 0 1 15 0V21"/></svg>;
    case "file": return <svg {...common}><path d="M6 3h8l5 5v13H6zM14 3v5h5M9 13h7M9 17h7"/></svg>;
    case "heart": return <svg {...common}><path d="M20.5 8.8c0 5-8.5 11-8.5 11s-8.5-6-8.5-11A4.5 4.5 0 0 1 12 6.2a4.5 4.5 0 0 1 8.5 2.6Z"/></svg>;
    case "lock": return <svg {...common}><rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>;
    default: return <svg {...common}><circle cx="12" cy="12" r="8"/></svg>;
  }
}

function sidebarIcon(surface: Surface, id: string): string {
  if (id === "dashboard") return "grid";
  if (id === "people") return "users";
  if (id === "organizations") return "building";
  if (id === "capital" || id === "funding") return "wallet";
  if (id === "guarantees") return "shield";
  if (id === "facilities") return "bank";
  if (id === "finance") return surface === "admin" ? "scale" : "wallet";
  if (id === "risk") return "sliders";
  if (id === "access") return "key";
  if (id === "history") return "history";
  if (id === "reports") return "chart";
  return "file";
}

function PreviewBrand({ onClick, mobile = false }: { onClick: () => void; mobile?: boolean }) {
  return <button type="button" className={mobile ? "mobile-brand-button" : "preview-brand-box"}
    onClick={onClick} aria-label="بازگشت به صفحه اصلی بادبان">
    <img src="/assets/badban-logo.png" alt="بادبان — سرمایه، اعتبار، توانمندسازی" />
  </button>;
}

function PreviewSidebar({ surface, workspace, pageId, onNavigate, onBack }: {
  surface: Surface; workspace: Workspace; pageId: string;
  onNavigate: (id: string) => void; onBack: () => void;
}) {
  const title = surface === "institution" ? "پنل سازمان حمایتگر"
    : surface === "lender" ? "پنل تأمین‌کننده تسهیلات" : "مدیریت مرکزی بادبان";
  const context = surface === "institution"
    ? { name: "سازمان همراهی فردا", detail: "فضای سازمانی نمونه • بدون عملیات بانکی" }
    : surface === "lender"
      ? { name: "صندوق تأمین اعتبار نمونه", detail: "دسترسی محدود به تأمین‌کننده" }
      : { name: "کاربر مدیر • نمونه", detail: "دسترسی مدیریتی نمایشی" };
  return <aside className={"preview-sidebar preview-sidebar--" + surface}>
    <div className="preview-sidebar-brand"><PreviewBrand onClick={onBack} /></div>
    <strong className="preview-sidebar-heading">{title}</strong>
    <nav className="preview-sidebar-nav" aria-label={"منوی " + title}>
      {workspace.menu.map(item => <button key={item.id} type="button"
        className={item.id === pageId ? "preview-nav-item preview-nav-item--active" : "preview-nav-item"}
        aria-current={item.id === pageId ? "page" : undefined}
        onClick={() => onNavigate(item.id)}>
        <span className="preview-nav-icon"><Icon name={sidebarIcon(surface, item.id)} size={23} /></span>
        <span>{item.label}</span>
      </button>)}
    </nav>
    <div className="preview-sidebar-context">
      <strong>{context.name}</strong><span>{context.detail}</span>
    </div>
    <button type="button" className="preview-sidebar-exit" onClick={onBack}>
      <span>بازگشت به صفحه اصلی</span><Icon name="chevron" size={19} />
    </button>
    <span className="preview-sidebar-pill">پیش‌نمایش محصول</span>
  </aside>;
}

function SampleMetric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <article className="preview-metric">
    <span>{label}</span><strong>{value}</strong><small>{detail}</small>
  </article>;
}

function DashboardContext({ children, label = "داده نمایشی" }: { children: string; label?: string }) {
  return <div className="dashboard-context-bar">
    <span className="dashboard-context-label">{label}</span><strong>{children}</strong>
  </div>;
}

function DashboardHeading({ breadcrumb, title, description }: {
  breadcrumb: string; title: string; description: string;
}) {
  return <>
    <div className="preview-breadcrumb">{breadcrumb} / داشبورد</div>
    <header className="preview-page-heading">
      <div><h1>{title}</h1><p>{description}</p></div>
    </header>
  </>;
}

function SampleTable({ columns, rows }: { columns: string[]; rows: string[][] }) {
  return <div className="preview-table-wrap"><table className="preview-table">
    <thead><tr>{columns.map(column => <th key={column}>{column}</th>)}</tr></thead>
    <tbody>{rows.map((row, index) => <tr key={index}>
      {row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}
    </tr>)}</tbody>
  </table></div>;
}

function InstitutionDashboard({ onNavigate }: { onNavigate: (id: string) => void }) {
  return <div className="figma-dashboard figma-dashboard--institution">
    <DashboardHeading breadcrumb="پنل سازمان" title="داشبورد سازمان"
      description="نمای کلی افراد، سرمایه منتسب و فعالیت‌های مالی همین سازمان" />
    <DashboardContext>سازمان همراهی فردا&nbsp; • &nbsp;پنل سازمانی مستقل</DashboardContext>
    <section className="preview-metrics preview-metrics--four" aria-label="شاخص‌های نمایشی سازمان">
      <SampleMetric label="سرمایه سازمانی منتسب" value="۱/۸ میلیارد" detail="ریال • اصل متعلق به سازمان" />
      <SampleMetric label="کارکنان" value="۶ نفر" detail="منسوب به برنامه نمونه" />
      <SampleMetric label="مددجویان" value="۱۲ نفر" detail="ثبت‌شده در فهرست نمایشی" />
      <SampleMetric label="افراد منتسب" value="۱۸ نفر" detail="۱۲ مددجو • ۶ کارمند" />
    </section>
    <h2 className="dashboard-section-title">اقدام‌های اصلی</h2>
    <section className="dashboard-actions">
      <article className="dashboard-action-card">
        <div className="dashboard-action-icon"><Icon name="wallet" size={27} /></div>
        <h3>تأمین سرمایه نقدی</h3>
        <p>تخصیص وجه سرمایه به پرونده فرد، بدون انتقال مالکیت</p>
        <button type="button" onClick={() => onNavigate("funding")}>مشاهده فرم تأمین وجه</button>
      </article>
      <article className="dashboard-action-card">
        <div className="dashboard-action-icon"><Icon name="users" size={27} /></div>
        <h3>مدیریت افراد</h3>
        <p>تعریف مددجو یا کارمند در فضای سازمانی</p>
        <button type="button" onClick={() => onNavigate("people")}>افزودن فرد</button>
      </article>
    </section>
    <h2 className="dashboard-section-title dashboard-section-title--spaced">آخرین فعالیت‌های نمونه</h2>
    <section className="dashboard-table-card">
      <SampleTable columns={["فرد", "نوع انتساب", "شناسه نمونه", "مبلغ نمایشی", "وضعیت نمونه"]} rows={[
        ["مریم احمدی", "مددجو", "BD-P-101", "۱۸۵ میلیون ریال", "پیش‌نویس"],
        ["علی مرادی", "کارمند", "BD-P-107", "۱۲۰ میلیون ریال", "در انتظار تطبیق"],
        ["سارا محمدی", "مددجو", "BD-P-103", "۸۵ میلیون ریال", "پیش‌نویس"],
      ]} />
    </section>
    <p className="dashboard-footnote">اصل سرمایه سازمانی متعلق به سازمان می‌ماند؛ این مقادیر صرفاً برای نمایش طراحی هستند.</p>
  </div>;
}

function LenderDashboard() {
  return <div className="figma-dashboard figma-dashboard--lender">
    <DashboardHeading breadcrumb="پنل تأمین‌کننده" title="داشبورد تأمین‌کننده"
      description="نمای ضمانت‌ها و اطلاعات گزارش‌شده تسهیلات، فقط در محدوده تأمین‌کننده مجاز" />
    <DashboardContext>صندوق تأمین اعتبار نمونه&nbsp; • &nbsp;دسترسی صرفاً به پرونده‌های همین تأمین‌کننده</DashboardContext>
    <section className="preview-metrics preview-metrics--four" aria-label="شاخص‌های نمایشی تأمین‌کننده">
      <SampleMetric label="مانده گزارش‌شده" value="۲/۱ میلیارد" detail="ریال • از منبع وام‌دهنده" />
      <SampleMetric label="مبلغ ضمانت‌ها" value="۳/۲ میلیارد" detail="ریال • نمونه" />
      <SampleMetric label="ضمانت فعال • نمونه" value="۱۶ مورد" detail="بدون صدور خودکار ضمانت" />
      <SampleMetric label="ضمانت‌های مرتبط" value="۲۴ پرونده" detail="فقط شناسه‌های مجاز تأمین‌کننده" />
    </section>
    <h2 className="dashboard-section-title dashboard-section-title--lender">مرور ضمانت‌های نمونه</h2>
    <section className="dashboard-record-list">
      <article className="dashboard-record">
        <div className="record-title"><Icon name="shield" /><strong>ضمانت مرتبط با تسهیلات</strong></div>
        <span>GU-204</span><strong>۳۰۰ میلیون ریال</strong><span>مانده ۱۸۰ میلیون</span><span className="record-status">فعال</span>
      </article>
      <article className="dashboard-record">
        <div className="record-title"><Icon name="shield" /><strong>ضمانت مرتبط با تسهیلات</strong></div>
        <span>GU-205</span><strong>۲۵۰ میلیون ریال</strong><span>اطلاعات موجود نیست</span><span className="record-status record-status--waiting">در انتظار اطلاعات</span>
      </article>
      <article className="dashboard-record">
        <div className="record-title"><Icon name="shield" /><strong>ضمانت مرتبط با تسهیلات</strong></div>
        <span>GU-206</span><strong>۱۵۰ میلیون ریال</strong><span>مانده ۹۰ میلیون</span><span className="record-status">فعال</span>
      </article>
    </section>
    <div className="dashboard-policy-note">
      <Icon name="lock" size={25} />
      <div><strong>تأمین‌کننده، تصمیم اعتباری و پرداخت تسهیلات را در سامانه مجاز خودش انجام می‌دهد.</strong>
        <p>این پنل فقط نمای اطلاعات ضمانت و وضعیت گزارش‌شده وام است؛ هیچ هویت یا اطلاعاتی خارج از محدوده مجاز نمایش داده نمی‌شود.</p></div>
    </div>
  </div>;
}

function AdminDashboard() {
  return <div className="figma-dashboard figma-dashboard--admin">
    <DashboardHeading breadcrumb="مدیریت مرکزی" title="داشبورد مدیریت"
      description="نمای متمرکز وضعیت سامانه‌ها، پرونده‌ها و کنترل‌های مدیریتی بادبان" />
    <DashboardContext label="نمایش طراحی">دسترسی مدیریتی&nbsp; • &nbsp;داده‌های نمایشی&nbsp; • &nbsp;کنترل‌های حساس تنها با مجوز و تأیید مستقل</DashboardContext>
    <section className="preview-metrics preview-metrics--four" aria-label="شاخص‌های نمایشی مدیریت">
      <SampleMetric label="موارد نیازمند رسیدگی" value="۷ مورد" detail="صرفاً شبیه‌سازی کنترل" />
      <SampleMetric label="ضمانت‌های ثبت‌شده" value="۳۶ پرونده" detail="بدون ایجاد ضمانت جدید" />
      <SampleMetric label="برنامه‌ها" value="۱۸ برنامه" detail="فعالیت‌های نمایشی" />
      <SampleMetric label="افراد در نمونه" value="۱,۲۴۰ نفر" detail="از برنامه‌های مجاز فرضی" />
    </section>
    <h2 className="dashboard-section-title dashboard-section-title--admin">نمای کنترل عملیات</h2>
    <section className="dashboard-record-list dashboard-record-list--admin">
      <article className="dashboard-record">
        <strong>تطبیق تأمین وجه</strong><span>FIN-102</span><strong>سرمایه سازمانی</strong><strong>۱۲۰ میلیون ریال</strong><span className="record-status record-status--review">نیازمند بررسی</span>
      </article>
      <article className="dashboard-record">
        <strong>کنترل ضمانت</strong><span>GU-204</span><strong>ضمانت و وام</strong><strong>۳۰۰ میلیون ریال</strong><span className="record-status record-status--sample">وضعیت نمونه</span>
      </article>
      <article className="dashboard-record">
        <strong>کنترل دسترسی</strong><span>ACC-008</span><strong>مجوز برنامه</strong><strong>بدون مبلغ</strong><span className="record-status record-status--waiting">در انتظار بازبینی</span>
      </article>
    </section>
    <div className="dashboard-policy-note">
      <Icon name="lock" size={25} />
      <div><strong>دسترسی مدیریتی به معنی مجوز اقدام مالی یا انتشار نیست.</strong>
        <p>فعال‌سازی عملیات حساس به قرارداد، مجوزهای ثبت حسابداری و تأیید مستقل وابسته است؛ Stage این پیش‌نمایش غیرفعال است.</p></div>
    </div>
  </div>;
}

function DesktopDashboard({ surface, onNavigate }: {
  surface: Surface; onNavigate: (id: string) => void;
}) {
  if (surface === "institution") return <InstitutionDashboard onNavigate={onNavigate} />;
  if (surface === "lender") return <LenderDashboard />;
  return <AdminDashboard />;
}

function PreviewSections({ page }: { page: WorkspacePage }) {
  return <>
    {page.metrics && <section className="preview-metrics" aria-label="شاخص‌های نمایشی">
      {page.metrics.map(metric => <SampleMetric key={metric.label} {...metric} />)}
    </section>}
    <div className="preview-sections">
      {page.sections.map(section => <section className="preview-panel" key={section.title}>
        <div className="preview-panel-heading"><h2>{section.title}</h2><span>نمونه</span></div>
        {section.description && <p className="preview-panel-description">{section.description}</p>}
        {section.columns && section.rows && <SampleTable columns={section.columns} rows={section.rows} />}
        {section.items && <div className="preview-item-grid">
          {section.items.map(item => <article className="preview-item" key={item.title}>
            <strong>{item.title}</strong><p>{item.description}</p>{item.meta && <small>{item.meta}</small>}
          </article>)}
        </div>}
        {section.emptyText && <p className="preview-empty">{section.emptyText}</p>}
      </section>)}
    </div>
    {page.note && <div className="preview-note" role="note">{page.note}</div>}
    <div className="preview-readonly-banner">
      <strong>نسخه نمایشی — فقط مشاهده</strong>
      <span>تمام اطلاعات این صفحه نمونه و غیرواقعی است. هیچ درخواست، تغییر دسترسی، محاسبه مالی یا تراکنشی انجام نمی‌شود.</span>
    </div>
  </>;
}

function GenericDesktopPage({ page, surface }: { page: WorkspacePage; surface: Surface }) {
  const title = surface === "institution" ? "پنل سازمان"
    : surface === "lender" ? "پنل تأمین‌کننده" : "مدیریت مرکزی";
  return <div className="generic-preview-page">
    <div className="preview-breadcrumb">{title} / {page.title}</div>
    <header className="preview-page-heading">
      <div><h1>{page.title}</h1><p>{page.description}</p></div>
    </header>
    <DashboardContext>محیط نمایشی بادبان&nbsp; • &nbsp;اطلاعات غیرعملیاتی</DashboardContext>
    <PreviewSections page={page} />
  </div>;
}

function IndividualDashboard({ onNavigate }: { onNavigate: (id: string) => void }) {
  return <div className="individual-dashboard">
    <div className="mobile-greeting">
      <strong>سلام، نگارا! خوش اومدی</strong><span>داده نمایشی</span>
    </div>
    <section className="mobile-hero">
      <div className="mobile-hero-art"><div className="mobile-hero-ring"><Icon name="shield" size={62} /></div></div>
      <div className="mobile-hero-copy">
        <small>همه چیز در مسیر توانمندسازی</small>
        <h1>پرونده مالی شما، شفاف و یکپارچه</h1>
        <button type="button" onClick={() => onNavigate("finance")}>مشاهده پرونده مالی</button>
      </div>
    </section>
    <section className="mobile-services">
      <div className="mobile-section-heading"><h2>خدمات بادبان</h2>
        <button type="button" onClick={() => onNavigate("services")}>همه خدمات <Icon name="chevron" size={14} /></button></div>
      <div className="mobile-service-grid">
        <button type="button" className="mobile-service-card" onClick={() => onNavigate("services")}>
          <span className="mobile-service-icon mobile-service-icon--gold"><img src="/assets/figma/finance-shield.svg" alt="" /></span>
          <strong>ضمانت وام</strong><small>تسهیلات</small>
        </button>
        <button type="button" className="mobile-service-card" onClick={() => onNavigate("services")}>
          <span className="mobile-service-icon mobile-service-icon--blue"><img src="/assets/figma/finance-calendar.svg" alt="" /></span>
          <strong>مستمری</strong><small>حمایت ماهانه</small>
        </button>
        <button type="button" className="mobile-service-card" onClick={() => onNavigate("services")}>
          <span className="mobile-service-icon mobile-service-icon--gold"><img src="/assets/figma/finance-wallet-gold.svg" alt="" /></span>
          <strong>آینده مالی</strong><small>پس از خروج</small>
        </button>
      </div>
    </section>
    <button type="button" className="mobile-finance-shortcut" onClick={() => onNavigate("finance")}>
      <span className="mobile-finance-icon"><img src="/assets/figma/finance-wallet-white.svg" alt="" /></span>
      <span className="mobile-finance-copy"><strong>پرونده مالی من</strong><small>۱ ضمانت&nbsp; • &nbsp;۳ دوره حمایت</small></span>
      <Icon name="chevron" size={21} />
    </button>
    <section className="mobile-activity">
      <h2>آخرین فعالیت‌ها</h2>
      <button type="button" className="mobile-activity-card" onClick={() => onNavigate("requests")}>
        <span className="mobile-activity-icon"><Icon name="history" size={20} /></span>
        <span><strong>ضمانت وام&nbsp; • &nbsp;دریافت‌شده</strong><small>درخواست نمونه&nbsp; • &nbsp;زمان نمایشی</small></span>
      </button>
    </section>
  </div>;
}

function IndividualPage({ page }: { page: WorkspacePage }) {
  return <div className="mobile-generic-page">
    <div className="preview-breadcrumb">بادبان / پیش‌نمایش / افراد</div>
    <header className="preview-page-heading"><div><h1>{page.title}</h1><p>{page.description}</p></div></header>
    <PreviewSections page={page} />
  </div>;
}

function MobileBottomNav({ pageId, onNavigate }: { pageId: string; onNavigate: (id: string) => void }) {
  const items = [
    { id: "profile", label: "حساب", icon: "applicant-account.svg" },
    { id: "requests", label: "درخواست‌ها", icon: "applicant-requests.svg" },
    { id: "services", label: "خدمات", icon: "applicant-services.svg" },
    { id: "finance", label: "مالی", icon: "applicant-wallet.svg" },
    { id: "dashboard", label: "خانه", icon: "applicant-home.svg" },
  ];
  return <nav className="mobile-bottom-nav" aria-label="پیمایش اصلی">
    {items.map(item => <button key={item.id} type="button"
      className={item.id === pageId ? "mobile-nav-item mobile-nav-item--active" : "mobile-nav-item"}
      aria-current={item.id === pageId ? "page" : undefined}
      onClick={() => onNavigate(item.id)}>
      <img src={"/assets/figma/" + item.icon} alt="" /><span>{item.label}</span>
    </button>)}
  </nav>;
}

export function PreviewWorkspace({ surface, onBack }: {
  surface: Surface; onBack: () => void;
}) {
  const [pageId, setPageId] = useState("dashboard");
  const workspace = previewWorkspaces[surface];
  const page = (workspace.pages[pageId] ?? workspace.pages.dashboard) as WorkspacePage;

  if (surface === "individual") {
    return <div className="preview-individual-stage" data-figma-frame={
      ({ dashboard: "160:3", services: "163:2", requests: "163:81", finance: "163:160", profile: "163:239" } as Record<string, string>)[pageId] ?? "160:3"
    }>
      <div className="mobile-screen" dir="rtl">
        <header className="mobile-topbar">
          <span className="mobile-notification" aria-hidden="true">
            <img src="/assets/figma/applicant-bell.svg" alt="" />
          </span>
          <PreviewBrand onClick={onBack} mobile />
        </header>
        <main className="mobile-content">
          {pageId === "dashboard" ? <IndividualDashboard onNavigate={setPageId} />
            : ["services", "requests", "finance", "profile"].includes(pageId)
              ? <IndividualPreviewPage pageId={pageId as "services" | "requests" | "finance" | "profile"} onNavigate={setPageId} />
              : <IndividualPage page={page} />}
        </main>
        <MobileBottomNav pageId={pageId} onNavigate={setPageId} />
      </div>
    </div>;
  }

  const frame = surface === "institution" ? "244:3" : surface === "lender" ? "259:3" : "271:3";
  return <div className={"preview-desktop-shell preview-desktop-shell--" + surface}
    dir="ltr" data-figma-frame={frame}>
    <main className="preview-main" dir="rtl">
      {pageId === "dashboard"
        ? <DesktopDashboard surface={surface} onNavigate={setPageId} />
        : <GenericDesktopPage page={page} surface={surface} />}
    </main>
    <PreviewSidebar surface={surface} workspace={workspace} pageId={pageId}
      onNavigate={setPageId} onBack={onBack} />
  </div>;
}
