import { useEffect, useState } from "react";
import { loadApplicantProfile, type ApplicantProfile } from "./applicant-profile-data";
import "./applicant-profile.css";

type ProfileState =
  | { kind: "loading" }
  | { kind: "ready"; data: ApplicantProfile }
  | { kind: "error"; message: string };

export function ApplicantAccount({ token, onFinancialCase, onLogout }: {
  token: string; onFinancialCase: () => void; onLogout: () => void;
}) {
  const [showDetails, setShowDetails] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const key = JSON.stringify([token, refresh]);
  const [saved, setSaved] = useState<{ key: string; state: ProfileState }>({
    key: "", state: { kind: "loading" },
  });

  useEffect(() => {
    let live = true;
    setSaved({ key, state: { kind: "loading" } });
    loadApplicantProfile(token).then(data => {
      if (live) setSaved({ key, state: { kind: "ready", data } });
    }).catch((error: unknown) => {
      if (live) setSaved({
        key, state: {
          kind: "error", message: error instanceof Error ? error.message : "خطا در دریافت پروفایل",
        },
      });
    });
    return () => { live = false; };
  }, [token, key]);

  const state: ProfileState = saved.key === key ? saved.state : { kind: "loading" };

  return <section className="applicant-account" aria-label="حساب من">
    {showDetails ? <>
      <button className="applicant-account-back" type="button" onClick={() => setShowDetails(false)}>
        بازگشت به حساب
      </button>
      <h3>اطلاعات هویتی</h3>
      <p className="muted">نمایش ایمن اطلاعات حساب</p>
    </> : <>
      <h3>حساب من</h3>
      <p className="muted">هویت، امنیت و تنظیمات بادبان</p>
    </>}
    {state.kind === "loading" && <p className="notice" role="status">در حال دریافت اطلاعات حساب…</p>}
    {state.kind === "error" && <div className="notice notice--error" role="alert">
      {state.message}
      <button className="applicant-account-back" type="button"
        onClick={() => setRefresh(value => value + 1)}>تلاش دوباره</button>
    </div>}
    {state.kind === "ready" && <>
      <div className="applicant-account-hero">
        <strong>هویت حساب بادبان</strong>
        <span>حساب احراز هویت‌شده · بدون نمایش اطلاعات حساس</span>
      </div>
      {showDetails ? <>
        <h4>اطلاعات و گزینه‌ها</h4>
        <div className="applicant-account-entry">
          <strong>وضعیت پرونده</strong>
          <span>وضعیت ثبت‌شده در بادبان: {state.data.lifecycle_status}</span>
        </div>
        <div className="applicant-account-entry">
          <strong>شناسه داخلی پرونده</strong>
          <span dir="ltr" className="applicant-account-id">{state.data.participant_id}</span>
        </div>
        <div className="applicant-account-entry">
          <strong>حریم خصوصی</strong>
          <span>نام، کد ملی و اطلاعات حساس هویتی در این نما نمایش داده نمی‌شود.</span>
        </div>
      </> : <>
        <h4>تنظیمات و اطلاعات حساب</h4>
        <button type="button" className="applicant-account-action" onClick={() => setShowDetails(true)}>
          <strong>اطلاعات هویتی</strong><span>مشاهده وضعیت و شناسه داخلی پرونده</span>
        </button>
        <button type="button" className="applicant-account-action" onClick={onFinancialCase}>
          <strong>پرونده مالی</strong><span>سوابق موجود در API بادبان</span>
        </button>
        <div className="applicant-account-entry">
          <strong>امنیت و دسترسی</strong>
          <span>مدیریت دستگاه‌ها و نشست‌های فعال در API فعلی ارائه نشده است.</span>
        </div>
      </>}
    </>}
    {!showDetails && <button type="button" className="applicant-account-logout" onClick={onLogout}>
      خروج از حساب (محلی)
    </button>}
  </section>;
}
