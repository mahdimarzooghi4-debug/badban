import { useEffect, useState } from "react";
import { amount, api, type Beneficiary, type Guarantee } from "./api";
import { InstitutionCaseOverview } from "./institution-case-overview";
import {
  adminServiceQueuePath, allowedAdminServices, institutionCasePath, serviceLabel,
  valueOrUnavailable, verifiedInstitutionCase, verifiedIntakePage,
  type AdminWorkspaceAccess, type IntakePage, type InstitutionFinancialCase, type ServiceCode,
} from "./operational-data";
import "./operational-details.css";

type RequestState<T> =
  | { scope: string; owner: string; status: "loading" }
  | { scope: string; owner: string; status: "ready"; data: T }
  | { scope: string; owner: string; status: "error"; message: string };

function useScopedResource<T>(scope: string, token: string, load: () => Promise<T>): RequestState<T> {
  const [state, setState] = useState<RequestState<T>>({ scope, owner: token, status: "loading" });
  useEffect(() => {
    let current = true;
    setState({ scope, owner: token, status: "loading" });
    Promise.resolve().then(load).then(
      data => { if (current) setState({ scope, owner: token, status: "ready", data }); },
      (error: unknown) => { if (current) setState({ scope, owner: token, status: "error",
        message: error instanceof Error ? error.message : "دریافت اطلاعات امکان‌پذیر نشد." }); },
    );
    return () => { current = false; };
    // Scope and authenticated owner define the request identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, token]);
  return state.scope === scope && state.owner === token ? state : { scope, owner: token, status: "loading" };
}
function Result<T>({ state, children }: { state: RequestState<T>; children: (data: T) => React.ReactNode }) {
  if (state.status === "loading") return <p className="detail-feedback" role="status">در حال دریافت اطلاعات مجاز…</p>;
  if (state.status === "error") return <p className="detail-feedback detail-feedback--error" role="alert">{state.message}</p>;
  return <>{children(state.data)}</>;
}
function MiniRow({ title, value }: { title: string; value: React.ReactNode }) {
  return <div className="detail-mini-row"><span>{title}</span><strong>{value}</strong></div>;
}
function money(value: string | number | null | undefined, currencyCode?: string | null): string {
  return amount(value, currencyCode);
}
export function InstitutionFinancialDetail({ token, programId, participantId, episodeId, programName, participant, onClose }: {
  token: string; programId: string; participantId: string; episodeId: string;
  programName: string; participant: Beneficiary; onClose: () => void;
}) {
  const scope = programId + ":" + participantId + ":" + episodeId;
  const state = useScopedResource<InstitutionFinancialCase>(scope, token, () =>
    api<unknown>(institutionCasePath(programId, participantId, episodeId), token)
      .then(raw => verifiedInstitutionCase(raw, programId, participantId, episodeId)));
  return <section className="detail-surface" aria-labelledby="institution-case-title">
    <div className="detail-heading"><div><small>پرونده فرد در برنامه مجاز</small><h2 id="institution-case-title">جزئیات مالی و دارایی‌ها</h2></div>
      <button className="detail-close" type="button" onClick={onClose}>بستن جزئیات</button></div>
    <Result state={state}>{data => <>
      <InstitutionCaseOverview data={data} scope={{ programId, programName, participant }} />
      <h3 className="detail-support-heading">جزئیات تکمیلی پرونده بر اساس اطلاعات ثبت‌شده</h3>
      <p className="detail-note">مالکیت اصل سرمایه با حق بهره‌مندی از آن یکسان نیست. این نما هیچ پرداخت، انتساب یا تغییر تعهدی انجام نمی‌دهد.</p>
      <div className="detail-columns">
        <article className="detail-card"><h3>دارایی‌های ثبت‌شده</h3>
          {data.assets.length ? data.assets.map(asset => <div className="detail-entry" key={asset.id}>
            <MiniRow title="دارایی" value={asset.asset_name + " (" + asset.asset_code + ")"}/>
            <MiniRow title="مقدار" value={valueOrUnavailable(asset.quantity) + " " + asset.unit_code}/>
            <MiniRow title="مالکیت اصل" value={asset.ownership_funding_type === "PROGRAM_ATTRIBUTED" ? "سازمانی؛ اصل متعلق به سازمان است" :
              asset.ownership_funding_type === "PARTICIPANT_OWNED" ? "شخصی؛ متعلق به فرد" : "نوع مالکیت نیازمند بررسی مرجع"}/>
            <MiniRow title="وضعیت ثبت" value={asset.lifecycle_status}/>
            {asset.valuation_observations[0] && <MiniRow title="آخرین مشاهده ارزش (نه قیمت قطعی)"
              value={money(asset.valuation_observations[0].gross_market_value, asset.valuation_observations[0].valuation_currency) +
                " · " + asset.valuation_observations[0].source_name}/>}
          </div>) : <p className="detail-empty">دارایی ثبت‌شده‌ای برای این پرونده وجود ندارد.</p>}
        </article>
        <article className="detail-card"><h3>ضمانت‌ها و تسهیلات مرتبط</h3>
          {data.guarantees.length ? data.guarantees.map(g => <div className="detail-entry" key={g.id}>
            <MiniRow title="وضعیت ضمانت" value={g.state}/>
            <MiniRow title="اصل درخواست‌شده" value={money(g.requested_principal, g.currency)}/>
            <MiniRow title="مبلغ رزروشده" value={money(g.reserved_guarantee_amount, g.currency)}/>
            <MiniRow title="مبلغ صادرشده" value={money(g.issued_guarantee_amount, g.currency)}/>
            <MiniRow title="تعهد جاری ضمانت" value={money(g.current_guarantee_exposure, g.currency)}/>
            <MiniRow title="مانده وام گزارش‌شده" value={money(g.outstanding_principal, g.loan_currency)}/>
            <MiniRow title="وضعیت وام" value={valueOrUnavailable(g.loan_state)}/>
          </div>) : <p className="detail-empty">ضمانتی در این پرونده ثبت نشده است.</p>}
        </article>
      </div>
      <div className="detail-columns">
        <article className="detail-card"><h3>حقوق حمایتی دوره‌ای</h3>
          {data.monthly_pension_entitlements.length ? data.monthly_pension_entitlements.map(p => <div className="detail-entry" key={p.id}>
            <MiniRow title="دوره" value={p.period_reference}/><MiniRow title="مبلغ ثبت‌شده" value={money(p.amount,p.currency)}/>
            <MiniRow title="وضعیت" value={p.lifecycle_status}/></div>) : <p className="detail-empty">سابقه‌ای ثبت نشده است.</p>}
        </article>
        <article className="detail-card"><h3>حمایت پس از خروج</h3>
          {data.post_exit_support_cases.length ? data.post_exit_support_cases.map(c => <div className="detail-entry" key={c.id}>
            <MiniRow title="وضعیت پرونده" value={c.lifecycle_status}/><MiniRow title="مدت" value={String(c.duration_months) + " ماه"}/>
            {c.entitlements.map(e => <MiniRow key={e.id} title={"دوره " + e.period_reference}
              value={money(e.amount,e.currency) + " · " + e.lifecycle_status}/>)}</div>) : <p className="detail-empty">پرونده‌ای ثبت نشده است.</p>}
        </article>
      </div>
      <article className="detail-card"><h3>بازده تخصیص‌یافته در برنامه</h3>
        <p className="detail-empty">این ارقام در سطح برنامه و فرد گزارش شده‌اند، نه صرفاً این دوره مشارکت.</p>
        {data.program_return_allocations.length ? data.program_return_allocations.map((r,i) =>
          <MiniRow key={r.currency + i} title={"بازده ثبت‌شده (" + r.currency + ")"} value={money(r.amount,r.currency)}/>) :
          <p className="detail-empty">بازده تخصیص‌یافته‌ای گزارش نشده است.</p>}
      </article>
      <p className="detail-note">ارزش‌گذاری‌ها مشاهده‌های منبع‌دارند، نه قیمت منتخب یا تضمین‌شده. نبود داده نیز به معنی صفر یا تسویه نیست.</p>
    </>}</Result>
  </section>;
}
export function LenderGuaranteeDetail({ guarantee, onClose }: { guarantee: Guarantee; onClose: () => void }) {
  return <section className="detail-surface" aria-labelledby="lender-guarantee-title">
    <div className="detail-heading"><div><small>ضمانت متعلق به تأمین‌کننده انتخاب‌شده</small><h2 id="lender-guarantee-title">جزئیات ضمانت</h2></div>
      <button className="detail-close" type="button" onClick={onClose}>بستن جزئیات</button></div>
    <div className="detail-columns">
      <article className="detail-card"><h3>وضعیت ضمانت</h3>
        <MiniRow title="شناسه پرونده" value={guarantee.guarantee_case_id}/>
        <MiniRow title="وضعیت" value={guarantee.case_state}/>
        <MiniRow title="تعهد جاری" value={money(guarantee.current_guarantee_exposure,guarantee.currency)}/>
      </article>
      <article className="detail-card"><h3>اطلاعات وام گزارش‌شده</h3>
        <MiniRow title="وضعیت وام" value={valueOrUnavailable(guarantee.loan_state)}/>
        <MiniRow title="مانده اصل وام" value={money(guarantee.outstanding_principal,guarantee.loan_currency)}/>
        <p className="detail-empty">نبود مانده گزارش‌شده به معنی تسویه وام نیست.</p>
      </article>
    </div>
  </section>;
}
export function AdminServiceQueue({ token, workspaces }: { token: string; workspaces: AdminWorkspaceAccess[] }) {
  const allowed = allowedAdminServices(workspaces);
  const [chosen, setChosen] = useState<ServiceCode | null>(null);
  const [paging, setPaging] = useState<{ service: ServiceCode | null; offset: number }>({ service: null, offset: 0 });
  const selected = chosen && allowed.includes(chosen) ? chosen : allowed[0] ?? null;
  const offset = selected && paging.service === selected ? paging.offset : 0;
  const limit = 25;
  const scope = (selected ?? "none") + ":" + offset;
  const state = useScopedResource<IntakePage | null>(scope, token, () => selected
    ? api<unknown>(adminServiceQueuePath(selected, limit, offset), token)
      .then(raw => verifiedIntakePage(raw, selected, offset, limit))
    : Promise.resolve(null));
  return <section className="detail-surface" aria-labelledby="admin-intake-title">
    <div className="detail-heading"><div><small>صف ثبت اولیه؛ بدون تصمیم‌گیری یا پرداخت</small><h2 id="admin-intake-title">درخواست‌های خدمات</h2></div>
      {selected && <label className="detail-select-label">خدمت مجاز
        <select value={selected} onChange={e => {
          const next = e.target.value as ServiceCode;
          if (allowed.includes(next)) { setChosen(next); setPaging({ service: next, offset: 0 }); }
        }}>{allowed.map(code => <option key={code} value={code}>{serviceLabel(code)}</option>)}</select>
      </label>}
    </div>
    {!selected ? <p className="detail-empty">حوزه خدمت مجازی برای این حساب ثبت نشده است.</p>
      : <Result state={state}>{data => <>
        {!data || !data.items.length ? <p className="detail-empty">درخواستی در این صفحه از خدمت دریافت نشده است.</p>
          : <div className="detail-rows">{data.items.map(item => <div className="detail-mini-row" key={item.id}>
            <strong>درخواست {item.id.slice(0,8)}…</strong><span>پرونده فرد {item.participant_id.slice(0,8)}…</span>
            <span>دریافت‌شده</span><time dateTime={item.submitted_at}>{new Date(item.submitted_at).toLocaleDateString("fa-IR")}</time>
          </div>)}</div>}
        {data && <div className="detail-pagination">
          <button type="button" disabled={offset === 0} onClick={() => setPaging({service:selected,offset:Math.max(0,offset-limit)})}>صفحه قبل</button>
          <span>صفحه {(offset/limit+1).toLocaleString("fa-IR")}</span>
          <button type="button" disabled={data.items.length < limit} onClick={() => setPaging({service:selected,offset:offset+limit})}>صفحه بعد</button>
        </div>}
      </>}</Result>}
    <p className="detail-note">وضعیت RECEIVED فقط ثبت درخواست را نشان می‌دهد؛ این صفحه درخواست را تأیید، رد یا پرداخت نمی‌کند.</p>
  </section>;
}
