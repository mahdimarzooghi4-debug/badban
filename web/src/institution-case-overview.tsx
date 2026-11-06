import { type Beneficiary } from "./api";
import { amount } from "./api";
import { type InstitutionFinancialCase } from "./operational-data";
import "./institution-case-overview.css";

export type InstitutionCaseScope = {
  programId: string;
  programName: string;
  participant: Beneficiary;
};

function money(value: string, currency: string): string {
  return amount(value, currency);
}

function ownershipLabel(value: string): string {
  if (value === "PROGRAM_ATTRIBUTED") return "اصل سرمایه سازمانی (منتسب به فرد)";
  if (value === "PARTICIPANT_OWNED") return "دارایی متعلق به فرد";
  return "مالکیت نیازمند بررسی مرجع";
}

export function InstitutionCaseOverview({ data, scope }: {
  data: InstitutionFinancialCase;
  scope: InstitutionCaseScope;
}) {
  // Defense in depth: the rendered participant and returned case must be the same
  // authorized program, participant and participation episode, not just matching a name.
  if (data.program_id.toLowerCase() !== scope.programId.toLowerCase() ||
      data.participant_id.toLowerCase() !== scope.participant.participant_id.toLowerCase() ||
      data.episode_id.toLowerCase() !== scope.participant.episode_id.toLowerCase()) {
    throw new Error("محدوده پرونده مالی با برنامه یا فرد انتخاب‌شده تطابق ندارد.");
  }
  // An asset quantity is not cash, and there is no program-capital total or payment ledger
  // in this response. Never infer either from Figma sample amounts.
  const programAssets = data.assets.filter(
    asset => asset.ownership_funding_type === "PROGRAM_ATTRIBUTED",
  );
  const personalAssets = data.assets.filter(
    asset => asset.ownership_funding_type === "PARTICIPANT_OWNED",
  );
  return <section className="institution-case-overview" aria-label="پرونده فرد در برنامه مجاز">
    <div className="institution-case-context">
      <div>
        <strong>{scope.programName}</strong>
        <span>برنامه انتخاب‌شده · محدوده دسترسی سازمان</span>
      </div>
      <span className="institution-case-tag">داده ثبت‌شدهٔ بادبان</span>
    </div>
    <div className="institution-case-two-cards">
      <article className="institution-case-identity">
        <div className="institution-case-identity-header">
          <img src="/assets/figma/institution-person.svg" width="30" height="30" alt="" />
          <h3>پرونده فرد</h3>
        </div>
        <div className="institution-case-labels">
          <span className="institution-case-chip">{scope.participant.participation_status}</span>
          <small>رضایت ثبت‌شده: {scope.participant.consent_state}</small>
        </div>
        <p>شناسه داخلی فرد: <b dir="ltr">{data.participant_id}</b></p>
        <p>شناسه دوره مشارکت: <b dir="ltr">{data.episode_id}</b></p>
        <small>در API این نما، نام و شناسه ملی فرد ارائه نمی‌شود.</small>
      </article>
      <article className="institution-case-capital">
        <h3>دارایی‌های منتسب از طرف سازمان</h3>
        {programAssets.length ? <>
          <strong>{programAssets.length.toLocaleString("fa-IR")} مورد با انتساب سازمانی</strong>
          <div className="institution-case-labels">
            <span className="institution-case-chip institution-case-chip--blue">مالک اصل: سازمان</span>
            <span className="institution-case-chip">منتفع: مطابق قرارداد</span>
          </div>
        </> : <p className="institution-case-missing">
          دارایی با مالکیت سازمانی در این پرونده گزارش نشده است.
        </p>}
        <small>دارایی شخصی ثبت‌شده در این پاسخ: {personalAssets.length.toLocaleString("fa-IR")} مورد</small>
        <small>این تعداد، مبلغ سرمایه یا مجموع دارایی‌ها نیست.</small>
      </article>
    </div>
    <h3 className="institution-case-read-title">اطلاعات مالی مجاز این پرونده</h3>
    <div className="institution-case-read-rows">
      <div className="institution-case-read-row">
        <span>سرمایه سازمانی منتسب</span>
        <strong>مبلغ تجمیعی در این API ارائه نشده است.</strong>
      </div>
      <div className="institution-case-read-row">
        <span>حق برداشت اصل سرمایه سازمانی</span>
        <strong>از انتساب دارایی، حق برداشت یا انتقال مالکیت ایجاد نمی‌شود.</strong>
      </div>
      <div className="institution-case-read-row">
        <span>وضعیت تأمین وجه یا پرداخت</span>
        <strong>در قرارداد فعلی این API گزارش نشده است.</strong>
      </div>
    </div>
    {programAssets.length > 0 && <section className="institution-case-assets">
      <h4>تفکیک اقلام دارای انتساب سازمانی</h4>
      {programAssets.map(asset => <div key={asset.id} className="institution-case-asset">
        <strong>{asset.asset_name} ({asset.asset_code})</strong>
        <span>مقدار ثبت‌شده: {money(asset.quantity, asset.unit_code)}</span>
        <small>{ownershipLabel(asset.ownership_funding_type)} · وضعیت: {asset.lifecycle_status}</small>
        <small>مقدار ثبت‌شده به معنی وجه نقد قابل برداشت یا ارزش قطعی نیست.</small>
      </div>)}
    </section>}
    <p className="institution-case-rights">
      <img src="/assets/figma/institution-lock.svg" width="26" height="26" alt="" />
      <span>حقوق و منافع فرد تابع قرارداد معتبر است. انتساب وجه یا دارایی سازمانی، مالکیت اصل سرمایه را منتقل نمی‌کند. این صفحه هیچ پرداخت یا تغییر در مالکیت انجام نمی‌دهد.</span>
    </p>
  </section>;
}
