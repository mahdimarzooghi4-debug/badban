import { useState } from "react";
import { amount, type FinancialCase, type EntitlementSummary, type GuaranteeCaseSummary } from "./api";
import "./applicant-financial.css";

const asset = "/assets/figma/";
const financialMetrics = [
  { key: "outstanding_principal", label: "مانده اصل تسهیلات", icon: "finance-wallet-white.svg", tone: "blue" },
  { key: "guarantee_exposure", label: "تعهد ضمانتی", icon: "finance-shield.svg", tone: "gold" },
  { key: "allocated_support", label: "حمایت تخصیص‌یافته", icon: "finance-wallet-white.svg", tone: "blue" },
  { key: "realized_return_allocated_to_support", label: "بازده تخصیص‌یافته", icon: "finance-calendar.svg", tone: "gold" },
] as const;

const statuses: Record<string, string> = {
  REQUESTED: "درخواست‌شده", RESERVED: "رزروشده", ISSUED: "صادرشده",
  ACTIVE: "فعال", DELINQUENT: "دارای تأخیر", CLAIM_PENDING: "در انتظار بررسی مطالبه",
  CLAIM_APPROVED: "مطالبه تأییدشده", CLAIM_REJECTED: "مطالبه ردشده",
  ENFORCEMENT: "در حال پیگیری", SETTLEMENT: "در حال تسویه",
  RELEASED: "آزادشده", CLOSED: "بسته‌شده", CANCELLED: "لغوشده",
  EXPIRED: "منقضی‌شده", PENDING: "در انتظار", SETTLED: "تسویه‌شده",
  REPLACED: "جایگزین‌شده", DRAFT: "پیش‌نویس",
  APPROVED: "تأییدشده", SUSPENDED: "تعلیق‌شده", COMPLETED: "تکمیل‌شده",
};

export function financialAmount(value: string | null, currency?: string): string {
  // amount() groups an arbitrary-length exact string, without converting it to Number.
  return amount(value, currency).replace(/[0-9]/g, digit => "۰۱۲۳۴۵۶۷۸۹"[Number(digit)]);
}

function statusLabel(status: string) {
  return (statuses[status] ?? "وضعیت ثبت‌شده") + " (" + status + ")";
}

function dateLabel(raw: string) {
  return new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium" }).format(new Date(raw));
}

function Entitlement({ item }: { item: EntitlementSummary }) {
  return <div className="applicant-finance-record">
    <strong>دوره: {item.period_reference}</strong>
    <span>{financialAmount(item.amount, item.currency)}</span>
    <small>وضعیت استحقاق: {statusLabel(item.status)}</small>
    <small>پرداخت: اتصال تسویه انجام نشده است؛ مبلغ پرداختی اعلام نمی‌شود.</small>
    <span className="applicant-finance-id" dir="ltr">شناسه: {item.id}</span>
  </div>;
}

function Guarantee({ item }: { item: GuaranteeCaseSummary }) {
  return <div className="applicant-finance-record">
    <strong>ضمانت: {statusLabel(item.status)}</strong>
    <span>اصل درخواست‌شده: {financialAmount(item.requested_principal, item.currency)}</span>
    <span>تعهد ضمانتی ثبت‌شده: {financialAmount(item.guarantee_exposure, item.currency)}</span>
    {item.lender_record_status === "RECORDED" ? <>
      <small>اطلاعات وام نزد تأمین‌کننده ثبت شده؛ این به معنی راستی‌آزمایی مستقل نیست.</small>
      <span>وضعیت آینه وام: {statusLabel(item.loan_state!)}</span>
      <span>مانده اعلامی آینه: {financialAmount(item.outstanding_principal)}</span>
      <small>ارز آینهٔ این ردیف در قرارداد جزئیات ذکر نشده؛ مبالغ معتبر به تفکیک ارز در شاخص‌های بالا هستند.</small>
    </> : <small>آینه تسهیلات این پرونده هنوز ثبت نشده است.</small>}
    <span className="applicant-finance-id" dir="ltr">شناسه: {item.id}</span>
  </div>;
}

export function ApplicantFinancialCase({ data }: { data: FinancialCase }) {
  const [showCapitalNotice, setShowCapitalNotice] = useState(false);
  return <div className="applicant-financial" aria-label="پرونده مالی من">
    <header className="applicant-financial-heading">
      <h2>پرونده مالی من</h2>
      <p>وضعیت ضمانت، تسهیلات و حمایت‌ها</p>
    </header>

    <div className="applicant-financial-hero">
      <div className="applicant-financial-hero-copy">
        <h3>مرور مالی من</h3>
        <p>مبالغ و وضعیت‌ها از داده‌های ثبت‌شده در بادبان</p>
        <button type="button" aria-expanded={showCapitalNotice}
          aria-controls="applicant-financial-capital-notice"
          onClick={() => setShowCapitalNotice(previous => !previous)}>
          مدیریت سرمایه و برداشت
          <img src={asset + "finance-chevron.svg"} width="14" height="14" alt="" />
        </button>
      </div>
      <span className="applicant-financial-hero-icon" aria-hidden="true">
        <img src={asset + "finance-wallet-gold.svg"} width="22" height="22" alt="" />
      </span>
    </div>

    {showCapitalNotice && <div id="applicant-financial-capital-notice"
      className="notice" role="status">
      واریز، برداشت، مانده نقد قابل برداشت و گردش سرمایه در API عملیاتی این مرحله تعریف نشده‌اند.
      دارایی متعلق به فرد و سرمایهٔ متعلق به سازمان مستقل‌اند؛ این صفحه هیچ مبلغ قابل برداشت یا عملیات پرداختی ایجاد نمی‌کند.
    </div>}

    {data.balances.length === 0 && <div className="empty" role="status">
      هنوز سبد مانده‌ای برای این حساب در API موجود نیست. مقدار ناموجود، صفر در نظر گرفته نمی‌شود.
    </div>}
    {data.balances.map(balance => <section key={balance.currency}
      className="applicant-financial-currency" aria-label={"خلاصه مالی به ارز " + balance.currency}>
      <h3 className="applicant-financial-currency-heading">
        اطلاعات ثبت‌شده به ارز <b dir="ltr">{balance.currency}</b>
      </h3>
      <div className="applicant-financial-metrics">
        {financialMetrics.map(metric => <article className="applicant-financial-metric" key={metric.key}>
          <span className={"applicant-financial-metric-icon applicant-financial-metric-icon--" + metric.tone}>
            <img src={asset + metric.icon}
              width={metric.key === "guarantee_exposure" ||
                metric.key === "realized_return_allocated_to_support" ? 24 : 22}
              height={metric.key === "guarantee_exposure" ||
                metric.key === "realized_return_allocated_to_support" ? 24 : 22} alt="" />
          </span>
          <span className="applicant-financial-metric-label">{metric.label}</span>
          <strong className="applicant-financial-metric-amount" dir="auto">
            {financialAmount(balance[metric.key])}
          </strong>
          <small dir="ltr">{balance.currency}</small>
        </article>)}
      </div>
    </section>)}

    <section className="applicant-financial-details" aria-label="جزئیات مالی">
      <h3>جزئیات مالی</h3>
      <details className="applicant-finance-accordion">
        <summary>
          <span className="applicant-finance-detail-icon">
            <img src={asset + "finance-shield.svg"} width="24" height="24" alt="" />
          </span>
          <span><strong>ضمانت‌ها و تسهیلات</strong><small>وضعیت پرونده و مانده اعلامی</small></span>
        </summary>
        <div className="applicant-finance-accordion-content">
          {data.guarantee_cases.length === 0 ? <div className="empty">پرونده ضمانتی در پاسخ موجود نیست.</div> :
            data.guarantee_cases.map(item => <Guarantee key={item.id} item={item} />)}
          <p className="applicant-finance-note">
            این فهرست در API فعلی حداکثر ۱۰۰ ردیف دارد و شمار کل سوابق را نشان نمی‌دهد.
          </p>
        </div>
      </details>

      <details className="applicant-finance-accordion">
        <summary>
          <span className="applicant-finance-detail-icon">
            <img src={asset + "finance-calendar.svg"} width="24" height="24" alt="" />
          </span>
          <span><strong>مستمری و حمایت پس از خروج</strong><small>استحقاق‌ها و دوره‌های ثبت‌شده</small></span>
        </summary>
        <div className="applicant-finance-accordion-content">
          <h4>استحقاق‌های مستمری</h4>
          {data.monthly_entitlements.length === 0
            ? <div className="empty">مستمری ثبت‌شده‌ای در پاسخ موجود نیست.</div>
            : data.monthly_entitlements.map(item => <Entitlement key={item.id} item={item} />)}
          <h4>پرونده‌های حمایت پس از خروج</h4>
          {data.post_exit_cases.length === 0
            ? <div className="empty">پرونده‌ای در پاسخ موجود نیست.</div>
            : data.post_exit_cases.map(item => <div className="applicant-finance-record" key={item.id}>
                <strong>وضعیت پرونده: {statusLabel(item.status)}</strong>
                <small>زمان خروج: {dateLabel(item.exit_at)}</small>
                <small>آغاز حمایت: {dateLabel(item.support_start_at)}</small>
                <small>مدت ثبت‌شده: {item.duration_months.toLocaleString("fa-IR")} ماه</small>
                <span className="applicant-finance-id" dir="ltr">شناسه: {item.id}</span>
                {item.entitlements.length === 0
                  ? <small>استحقاق دوره‌ای در پاسخ وجود ندارد.</small>
                  : item.entitlements.map(period => <Entitlement key={period.id} item={period} />)}
              </div>)}
          <p className="applicant-finance-note">
            فهرست‌ها محدود به پاسخ API هستند. تأیید استحقاق به معنی پرداخت وجه نیست.
          </p>
        </div>
      </details>
    </section>
    <p className="applicant-finance-disclosure">
      اتصال تسویه و منبع قیمت خارجی هنوز پیکربندی نشده است. مبالغ پرداختی، موجودی نقد
      قابل برداشت یا نرخ تبدیل ارز از این اطلاعات قابل استنتاج نیست.
    </p>
  </div>;
}
