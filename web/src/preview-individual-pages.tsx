import { useState } from "react";
import "./preview-individual-pages.css";

type MainPageId = "services" | "requests" | "finance" | "profile";
type SampleService = {
  id: "guarantee" | "pension" | "future";
  title: string;
  description: string;
  badge: string;
  icon: string;
  tone: "gold" | "blue";
};

const services: readonly SampleService[] = [
  { id: "guarantee", title: "ضمانت وام", description: "ضمانت تسهیلات بانکی و صندوق‌های مجاز", badge: "۱ درخواست", icon: "finance-shield.svg", tone: "gold" },
  { id: "pension", title: "مستمری ماهانه", description: "حمایت دوره‌ای از محل بازده محقق‌شده", badge: "۲ دوره", icon: "finance-calendar.svg", tone: "blue" },
  { id: "future", title: "آینده مالی", description: "حمایت مالی پس از خروج طبق سیاست مصوب", badge: "۳ دوره", icon: "finance-wallet-gold.svg", tone: "gold" },
] as const;

const requests = [
  { id: "BD-RQ-۱۰۴۲", category: "guarantee", title: "ضمانت وام", date: "۱۴۰۵/۰۸/۱۲", tone: "gold" as const, icon: "finance-shield.svg" },
  { id: "BD-RQ-۱۰۲۸", category: "pension", title: "مستمری ماهانه", date: "۱۴۰۵/۰۸/۰۵", tone: "blue" as const, icon: "finance-calendar.svg" },
  { id: "BD-RQ-۱۰۳۱", category: "future", title: "آینده مالی", date: "۱۴۰۵/۰۷/۲۷", tone: "gold" as const, icon: "finance-wallet-gold.svg" },
] as const;

const filters = [
  { id: "all", label: "همه" },
  { id: "guarantee", label: "ضمانت وام" },
  { id: "pension", label: "مستمری" },
  { id: "future", label: "آینده مالی" },
] as const;
type Filter = (typeof filters)[number]["id"];

const asset = (name: string) => "/assets/figma/" + name;

function PreviewTitle({ title, subtitle, frame }: {
  title: string; subtitle: string; frame: string;
}) {
  return <header className="mobile-reference-heading" data-figma-frame={frame}>
    <h1>{title}</h1><p>{subtitle}</p>
  </header>;
}

function SampleIcon({ icon, tone = "gold", size = "normal" }: {
  icon: string; tone?: "gold" | "blue" | "neutral"; size?: "normal" | "small";
}) {
  return <span className={"mobile-reference-icon mobile-reference-icon--" + tone + " mobile-reference-icon--" + size}>
    <img src={asset(icon)} alt="" />
  </span>;
}

function Chevron() {
  return <svg aria-hidden="true" className="mobile-reference-chevron"
    viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor"
    strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="m12.5 4.5-5.5 5.5 5.5 5.5" />
  </svg>;
}

function ServicesPage() {
  return <div className="mobile-reference-page mobile-reference-services" data-figma-frame="163:2">
    <PreviewTitle title="خدمات بادبان" subtitle="خدمت مناسب را بشناسید و درخواست اولیه ثبت کنید" frame="163:2" />
    <section className="mobile-reference-message">
      <strong>سه مسیر، یک پرونده مالی</strong><span>هر خدمت شرایط و سوابق مستقل خود را دارد</span>
    </section>
    <div className="mobile-reference-service-list">
      {services.map(service => <article className="mobile-reference-service" key={service.id}>
        <SampleIcon icon={service.icon} tone={service.tone} />
        <h2>{service.title}</h2><p>{service.description}</p>
        <div className="mobile-reference-service-footer">
          <span className="mobile-reference-detail">جزئیات خدمت <Chevron /></span>
          <span className="mobile-reference-pill">{service.badge}</span>
        </div>
      </article>)}
    </div>
    <p className="mobile-reference-disclaimer">ثبت درخواست، تأیید شرایط یا پرداخت مالی نیست.</p>
    <p className="mobile-reference-sample-label">صفحه نمایشی؛ هیچ فرم یا درخواست واقعی ارسال نمی‌شود.</p>
  </div>;
}

function RequestsPage() {
  const [filter, setFilter] = useState<Filter>("all");
  const visible = requests.filter(request => filter === "all" || filter === request.category);
  return <div className="mobile-reference-page mobile-reference-requests" data-figma-frame="163:81">
    <PreviewTitle title="درخواست‌های من" subtitle="وضعیت درخواست‌های ثبت‌شده" frame="163:81" />
    <div className="mobile-reference-filters" role="group" aria-label="فیلتر نمایشی درخواست‌ها">
      {filters.map(item => <button type="button" key={item.id}
        aria-pressed={filter === item.id}
        className={filter === item.id ? "mobile-reference-filter is-selected" : "mobile-reference-filter"}
        onClick={() => setFilter(item.id)}>{item.label}</button>)}
    </div>
    <div className="mobile-reference-request-list">
      {visible.map(request => <article className="mobile-reference-request" key={request.id}>
        <SampleIcon icon={request.icon} tone={request.tone} size="small" />
        <h2>{request.title}</h2>
        <span className="mobile-reference-request-id">{request.id}</span>
        <span className="mobile-reference-status">دریافت‌شده</span>
        <span className="mobile-reference-request-date">تاریخ ثبت: {request.date}</span>
      </article>)}
      {visible.length === 0 && <p>در این دسته درخواست نمونه‌ای وجود ندارد.</p>}
    </div>
    <section className="mobile-reference-message mobile-reference-request-note">
      <strong>وضعیت «دریافت‌شده» یعنی چه؟</strong>
      <span>RECEIVED فقط ثبت اولیه درخواست را نشان می‌دهد؛ نه تأیید خدمت، تخصیص سرمایه یا پرداخت.</span>
    </section>
    <p className="mobile-reference-sample-label">همه شناسه‌ها، نام‌ها و تاریخ‌ها ساختگی و مخصوص پیش‌نمایش هستند.</p>
  </div>;
}

const financeMetrics = [
  { label: "مانده اصل تسهیلات", amount: "۱۱۲ میلیون", icon: "applicant-wallet.svg", tone: "blue" as const },
  { label: "تعهد ضمانتی", amount: "۱۸۰ میلیون", icon: "finance-shield.svg", tone: "gold" as const },
  { label: "حمایت تخصیص‌یافته", amount: "۳ میلیون", icon: "finance-wallet-white.svg", tone: "blue" as const },
  { label: "بازده تخصیص‌یافته", amount: "۴/۵ میلیون", icon: "finance-calendar.svg", tone: "gold" as const },
] as const;

function FinancePage() {
  return <div className="mobile-reference-page mobile-reference-finance" data-figma-frame="163:160">
    <PreviewTitle title="پرونده مالی من" subtitle="وضعیت ضمانت، تسهیلات و حمایت‌ها" frame="163:160" />
    <section className="mobile-reference-finance-hero">
      <div><h2>مرور مالی من</h2><p>مبالغ و وضعیت‌ها در سناریوی نمایشی</p>
        <span>مدیریت سرمایه و برداشت <Chevron /></span></div>
      <SampleIcon icon="finance-wallet-gold.svg" tone="blue" />
    </section>
    <section className="mobile-reference-finance-grid" aria-label="مقادیر فرضی پرونده مالی">
      {financeMetrics.map(metric => <article className="mobile-reference-finance-card" key={metric.label}>
        <div className="mobile-reference-finance-card-title">
          <SampleIcon icon={metric.icon} tone={metric.tone} size="small" />
          <span>{metric.label}</span>
        </div>
        <strong>{metric.amount}</strong><small>ریال • نمونه</small>
      </article>)}
    </section>
    <h2 className="mobile-reference-section-heading">جزئیات مالی</h2>
    <div className="mobile-reference-finance-links">
      <article><SampleIcon icon="finance-shield.svg" size="small" tone="neutral" />
        <div><strong>ضمانت‌ها و تسهیلات</strong><span>وضعیت پرونده و مانده اعلامی</span></div></article>
      <article><SampleIcon icon="finance-calendar.svg" size="small" tone="neutral" />
        <div><strong>مستمری و حمایت پس از خروج</strong><span>سابقه‌ها و دوره‌های ثبت‌شده</span></div></article>
    </div>
    <p className="mobile-reference-sample-label">هیچ مانده بانکی یا حق برداشت واقعی در این پیش‌نمایش وجود ندارد.</p>
  </div>;
}

const accountItems = [
  { title: "اطلاعات هویتی", subtitle: "نگار احمدی • BD-۱۰۴۳", icon: "applicant-account.svg", tone: "neutral" as const },
  { title: "سرمایه من", subtitle: "واریز، برداشت و گردش سرمایه", icon: "finance-shield.svg", tone: "neutral" as const },
  { title: "امنیت و دسترسی", subtitle: "۱ دستگاه فعال • نمونه", icon: "finance-shield.svg", tone: "gold" as const },
  { title: "تنظیمات برنامه", subtitle: "زبان فارسی • حالت روشن", icon: "applicant-wallet.svg", tone: "neutral" as const },
  { title: "راهنما و قوانین", subtitle: "راهنمای رسمی خدمات بادبان", icon: "applicant-requests.svg", tone: "neutral" as const },
] as const;

function AccountPage({ onNavigate }: { onNavigate: (page: string) => void }) {
  return <div className="mobile-reference-page mobile-reference-account" data-figma-frame="163:239">
    <PreviewTitle title="حساب من" subtitle="هویت، امنیت و تنظیمات بادبان" frame="163:239" />
    <section className="mobile-reference-profile">
      <span className="mobile-reference-avatar">
        <img src={asset("applicant-account.svg")} alt="" />
      </span><div><strong>نگار احمدی</strong><span>شناسه نمونه: BD-۱۰۴۳</span></div>
    </section>
    <h2 className="mobile-reference-section-heading">تنظیمات و اطلاعات حساب</h2>
    <div className="mobile-reference-account-list">
      {accountItems.map(item => {
        const row = <><SampleIcon icon={item.icon} tone={item.tone} size="small" />
          <span><strong>{item.title}</strong><small>{item.subtitle}</small></span><Chevron /></>;
        return item.title === "سرمایه من"
          ? <button type="button" className="mobile-reference-account-item" key={item.title}
            onClick={() => onNavigate("finance")}>{row}</button>
          : <div className="mobile-reference-account-item" key={item.title}>{row}</div>;
      })}
    </div>
    <span className="mobile-reference-logout">خروج از حساب</span>
    <p className="mobile-reference-sample-label">حساب و هویت در این نما ساختگی‌اند؛ ورود و خروج واقعی فعال نیست.</p>
  </div>;
}

export function IndividualPreviewPage({ pageId, onNavigate }: {
  pageId: MainPageId; onNavigate: (page: string) => void;
}) {
  if (pageId === "services") return <ServicesPage />;
  if (pageId === "requests") return <RequestsPage />;
  if (pageId === "finance") return <FinancePage />;
  return <AccountPage onNavigate={onNavigate} />;
}
