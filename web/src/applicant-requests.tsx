import { useEffect, useState } from "react";
import type { ServiceCode } from "./api";
import {
  loadApplicantRequestPage, REQUEST_PAGE_LIMIT,
  type ApplicantRequestPage, type RequestFilter,
} from "./applicant-requests-data";
import "./applicant-requests.css";

type Loading = { kind: "loading" };
type Loaded = { kind: "ready"; page: ApplicantRequestPage };
type Failed = { kind: "error"; message: string };
type RequestState = Loading | Loaded | Failed;

const options: Array<{ code: RequestFilter; label: string }> = [
  { code: "ALL", label: "همه" },
  { code: "LOAN_GUARANTEE", label: "ضمانت وام" },
  { code: "MONTHLY_PENSION", label: "مستمری" },
  { code: "POST_EXIT_SUPPORT", label: "آینده مالی" },
];

function serviceLabel(code: ServiceCode): string {
  return options.find(option => option.code === code)?.label ?? "خدمت نامشخص";
}

function dateLabel(value: string): string {
  return new Date(value).toLocaleDateString("fa-IR");
}

export function ApplicantRequests({ token, refreshKey, compact = false }: {
  token: string; refreshKey: number; compact?: boolean;
}) {
  const [filter, setFilter] = useState<RequestFilter>("ALL");
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  // The key includes the authenticated owner. Never show another owner/filter/page's data
  // even for one render while React is waiting to run the next effect.
  const key = JSON.stringify([token, compact ? "ALL" : filter, compact ? 0 : offset, refreshKey, refresh]);
  const [saved, setSaved] = useState<{ key: string; state: RequestState }>({
    key: "", state: { kind: "loading" },
  });

  useEffect(() => {
    let active = true;
    setSaved({ key, state: { kind: "loading" } });
    loadApplicantRequestPage(token, compact ? "ALL" : filter, compact ? 0 : offset)
      .then(page => {
        if (active) setSaved({ key, state: { kind: "ready", page } });
      }).catch((error: unknown) => {
        if (active) setSaved({
          key, state: { kind: "error", message: error instanceof Error ? error.message : "خطا در دریافت درخواست‌ها" },
        });
      });
    return () => { active = false; };
  }, [token, filter, offset, refreshKey, refresh, compact, key]);

  const state: RequestState = saved.key === key ? saved.state : { kind: "loading" };
  const selected = state.kind === "ready"
    ? state.page.items.find(item => item.id === selectedId) : undefined;

  function changeFilter(next: RequestFilter) {
    setFilter(next); setOffset(0); setSelectedId(null);
  }
  function movePage(next: number) {
    setOffset(next); setSelectedId(null);
  }

  if (selected) return <section className="applicant-request-detail" aria-label="جزئیات درخواست">
    <button type="button" className="applicant-request-back" onClick={() => setSelectedId(null)}>
      بازگشت به درخواست‌ها
    </button>
    <h3>جزئیات درخواست</h3>
    <p className="muted">بررسی اطلاعات ثبت اولیه درخواست</p>
    <div className="applicant-request-hero">
      <strong>پرونده مالی بادبان</strong>
      <span>{serviceLabel(selected.service_code)} · درخواست ثبت‌شده</span>
    </div>
    <h4>جزئیات و وضعیت</h4>
    <div className="applicant-request-evidence">
      <strong>وضعیت درخواست</strong>
      <p>دریافت‌شده · {dateLabel(selected.submitted_at)}</p>
    </div>
    <div className="applicant-request-evidence">
      <strong>شناسه پیگیری</strong>
      <p dir="ltr" className="applicant-request-id">{selected.id}</p>
    </div>
    <div className="applicant-request-guidance">
      <strong>نتیجه بررسی</strong>
      <p>در API فعلی، نتیجه بررسی این درخواست ثبت نشده است. دریافت درخواست به معنی تأیید خدمت یا پرداخت نیست.</p>
    </div>
  </section>;

  return <section className="applicant-requests" aria-label={compact ? "آخرین درخواست‌ها" : "درخواست‌های من"}>
    {!compact && <>
      <p className="muted">وضعیت درخواست‌های ثبت‌شده</p>
      <div className="applicant-request-filters" role="group" aria-label="فیلتر نوع درخواست">
        {options.map(option => <button type="button" key={option.code}
          aria-pressed={filter === option.code}
          className={filter === option.code ? "active" : ""}
          onClick={() => changeFilter(option.code)}>{option.label}</button>)}
      </div>
    </>}
    {state.kind === "loading" && <p className="notice" role="status">در حال دریافت درخواست‌های شما…</p>}
    {state.kind === "error" && <div className="notice notice--error" role="alert">
      {state.message}
      <button type="button" className="applicant-request-retry"
        onClick={() => { setSelectedId(null); setRefresh(n => n + 1); }}>تلاش دوباره</button>
    </div>}
    {state.kind === "ready" && <>
      {!state.page.items.length && <div className="empty">در این صفحه درخواست ثبت‌شده‌ای وجود ندارد.</div>}
      <div className="applicant-request-cards">
        {(compact ? state.page.items.slice(0, 3) : state.page.items).map(item =>
          <button type="button" className="applicant-request-card" key={item.id}
            onClick={() => setSelectedId(item.id)}
            aria-label={"مشاهده جزئیات " + serviceLabel(item.service_code)}>
            <span className="applicant-request-type">{serviceLabel(item.service_code)}</span>
            <span className="applicant-request-reference" dir="ltr">{item.id}</span>
            <span className="applicant-request-state">دریافت‌شده</span>
            <span className="applicant-request-date">تاریخ ثبت: {dateLabel(item.submitted_at)}</span>
          </button>)}
      </div>
      {!compact && <div className="applicant-request-pagination">
        <button type="button" disabled={offset === 0}
          onClick={() => movePage(Math.max(0, offset - REQUEST_PAGE_LIMIT))}>صفحه قبل</button>
        <span>شروع از ردیف {(offset + 1).toLocaleString("fa-IR")}</span>
        <button type="button" disabled={state.page.items.length < REQUEST_PAGE_LIMIT}
          onClick={() => movePage(offset + REQUEST_PAGE_LIMIT)}>صفحه بعد</button>
      </div>}
    </>}
    {!compact && <div className="applicant-request-guidance">
      <strong>وضعیت «دریافت‌شده» یعنی چه؟</strong>
      <p>فقط ثبت اولیه درخواست را نشان می‌دهد؛ نه تأیید خدمت، تخصیص سرمایه یا پرداخت.</p>
    </div>}
  </section>;
}
