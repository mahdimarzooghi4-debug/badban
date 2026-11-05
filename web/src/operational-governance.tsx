import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { api } from "./api";
import {
  governanceQueuePath, verifiedGrantPage, verifiedBenefitReviewPage, type GrantQueueKind,
  type GrantStatus, type ReviewStatus, type GovernanceGrant, type BenefitLineageReview,
} from "./governance-data";
import {
  buildGrantRequest, buildGrantRevokeBody, grantMutationPath, grantRequestPath,
  type GrantAction, type GrantRequestDraft,
} from "./governance-actions";
import "./operational-governance.css";

type Workspace = {
  workspace_code: string; scope_type: "GLOBAL" | "SERVICE"; scope_id: string | null;
  role_codes: string[]; capabilities: string[];
};
type State<T> = { scope: string; owner: string; status: "loading" } |
  { scope: string; owner: string; status: "ready"; data: T } |
  { scope: string; owner: string; status: "error"; message: string };
function useQueue<T>(scope: string, token: string, load: () => Promise<T>): State<T> {
  const [state,setState] = useState<State<T>>({scope,owner:token,status:"loading"});
  useEffect(() => {
    let active=true;
    setState({scope,owner:token,status:"loading"});
    Promise.resolve().then(load).then(data=>{if(active)setState({scope,owner:token,status:"ready",data});},
      (error:unknown)=>{if(active)setState({scope,owner:token,status:"error",message:error instanceof Error?error.message:"دریافت صف امکان‌پذیر نیست."});});
    return ()=>{active=false;};
    // The status and offset are included in scope, and token identifies the caller.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[scope,token]);
  return state.scope===scope&&state.owner===token?state:{scope,owner:token,status:"loading"};
}
function Feedback<T>({state,children}:{state:State<T>;children:(data:T)=>ReactNode}) {
  if(state.status==="loading")return <p className="gov-feedback" role="status">در حال دریافت سوابق مجاز…</p>;
  if(state.status==="error")return <p className="gov-feedback gov-feedback--error" role="alert">{state.message}</p>;
  return <>{children(state.data)}</>;
}
function shortId(id:string):string{return id.slice(0,8)+"…"+id.slice(-4);}
function date(value:string|null):string{return value?new Date(value).toLocaleString("fa-IR"):"بدون تاریخ پایان";}
function grantStatusLabel(value:GrantStatus):string{return value==="REQUESTED"?"در انتظار بررسی":value==="ACTIVE"?"فعال":"لغوشده";}
function reviewStatusLabel(value:ReviewStatus):string{return value==="REQUESTED"?"در انتظار بررسی":value==="APPROVED"?"تأییدشده":"ردشده";}

function GrantRequestForm({token,kind,onCreated,onCancel}:{token:string;kind:GrantQueueKind;onCreated:()=>void;onCancel:()=>void}) {
  const [draft,setDraft]=useState<GrantRequestDraft>({identityId:"",scopeId:"",validFrom:"",validUntil:"",reasonReference:""});
  const [busy,setBusy]=useState(false),[message,setMessage]=useState("");
  const scopeLabel=kind==="support-institution"?"شناسه برنامه فعال":"شناسه تأمین‌کننده فعال";
  async function submit(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();if(busy)return;setBusy(true);setMessage("");
    try {
      const body=buildGrantRequest(kind,draft);
      await api<GovernanceGrant>(grantRequestPath(kind),token,{method:"POST",body:JSON.stringify(body)});
      onCreated();
    } catch(error) {
      setMessage(error instanceof Error?error.message:"ثبت درخواست مجوز انجام نشد.");
    } finally {setBusy(false);}
  }
  function update<K extends keyof GrantRequestDraft>(key:K,value:GrantRequestDraft[K]) {
    setDraft(current=>({...current,[key]:value}));
  }
  return <form className="gov-request-form" onSubmit={event=>void submit(event)}>
    <div className="gov-form-title"><strong>درخواست دسترسی جدید</strong><span>درخواست ابتدا با وضعیت «در انتظار بررسی» ثبت می‌شود.</span></div>
    <div className="gov-form-grid">
      <label>شناسه هویت انسانی فعال
        <input dir="ltr" autoComplete="off" spellCheck={false} required value={draft.identityId}
          onChange={e=>update("identityId",e.target.value)} placeholder="UUID هویت" />
      </label>
      <label>{scopeLabel}
        <input dir="ltr" autoComplete="off" spellCheck={false} required value={draft.scopeId}
          onChange={e=>update("scopeId",e.target.value)} placeholder="UUID محدوده" />
      </label>
      <label>شروع اعتبار
        <input type="datetime-local" required value={draft.validFrom} onChange={e=>update("validFrom",e.target.value)} />
      </label>
      <label>پایان اعتبار (اختیاری)
        <input type="datetime-local" value={draft.validUntil} onChange={e=>update("validUntil",e.target.value)} />
      </label>
      <label className="gov-form-wide">مرجع دلیل درخواست
        <input required maxLength={255} value={draft.reasonReference}
          onChange={e=>update("reasonReference",e.target.value)} placeholder="شناسه مصوبه یا مرجع مستند" />
      </label>
    </div>
    <p className="gov-form-note">فهرست جست‌وجوی هویت و سازمان در API فعلی موجود نیست؛ شناسه‌ها باید از مرجع مجاز دریافت شوند. ثبت درخواست به‌تنهایی دسترسی ایجاد نمی‌کند.</p>
    {message&&<p className="gov-feedback gov-feedback--error" role="alert">{message}</p>}
    <div className="gov-form-actions">
      <button type="submit" disabled={busy}>{busy?"در حال ثبت…":"ثبت درخواست مجوز"}</button>
      <button type="button" className="gov-secondary" disabled={busy} onClick={onCancel}>انصراف</button>
    </div>
  </form>;
}

function GrantActions({token,kind,grant,currentIdentityId,onChanged}:{token:string;kind:GrantQueueKind;grant:GovernanceGrant;currentIdentityId:string|null;onChanged:()=>void}) {
  const [action,setAction]=useState<GrantAction|null>(null);
  const [reason,setReason]=useState("");
  const [busy,setBusy]=useState(false),[message,setMessage]=useState("");
  const isMaker=currentIdentityId!==null&&grant.granted_by===currentIdentityId;
  async function execute() {
    if(!action||busy||!currentIdentityId)return;
    setBusy(true);setMessage("");
    try {
      if(action==="approve") {
        await api<GovernanceGrant>(grantMutationPath(kind,grant.id,"approve"),token,{method:"POST"});
      } else {
        const body=buildGrantRevokeBody(reason);
        await api<GovernanceGrant>(grantMutationPath(kind,grant.id,"revoke"),token,{method:"POST",body:JSON.stringify(body)});
      }
      onChanged();
    } catch(error) {
      setMessage(error instanceof Error?error.message:"عملیات مجوز انجام نشد.");
    } finally {setBusy(false);}
  }
  const canRevoke=grant.status==="REQUESTED"||grant.status==="ACTIVE";
  return <div className="gov-actions">
    {grant.status==="REQUESTED"&&<button type="button" disabled={!currentIdentityId||busy||isMaker}
      onClick={()=>{setAction("approve");setMessage("");}}>تأیید</button>}
    {canRevoke&&<button type="button" className="gov-danger" disabled={!currentIdentityId||busy}
      onClick={()=>{setAction("revoke");setMessage("");}}>لغو دسترسی</button>}
    {grant.status==="REQUESTED"&&isMaker&&<small>درخواست‌کننده نمی‌تواند تأییدکننده همان درخواست باشد.</small>}
    {!currentIdentityId&&canRevoke&&<small>برای اقدام، هویت فعلی باید از بک‌اند تأیید شود.</small>}
    {action==="approve"&&<div className="gov-confirm">
      <p>تأیید این دسترسی فقط با هویت راهبر دیگری مجاز است. بک‌اند این شرط را دوباره کنترل می‌کند.</p>
      <button type="button" disabled={busy||isMaker||!currentIdentityId} onClick={()=>void execute()}>{busy?"در حال اجرا…":"تأیید نهایی دسترسی"}</button>
      <button type="button" className="gov-secondary" disabled={busy} onClick={()=>setAction(null)}>بازگشت</button>
    </div>}
    {action==="revoke"&&<div className="gov-confirm">
      <label>دلیل لغو دسترسی
        <input required maxLength={255} value={reason} onChange={e=>setReason(e.target.value)} placeholder="مرجع دلیل لغو" />
      </label>
      <button type="button" disabled={busy||!currentIdentityId||!reason.trim()} onClick={()=>void execute()}>{busy?"در حال اجرا…":"ثبت لغو با دلیل"}</button>
      <button type="button" className="gov-secondary" disabled={busy} onClick={()=>setAction(null)}>بازگشت</button>
    </div>}
    {message&&<small className="gov-action-error" role="alert">{message}</small>}
  </div>;
}

function GrantQueue({token,kind,currentIdentityId}:{token:string;kind:GrantQueueKind;currentIdentityId:string|null}) {
  const [status,setStatus]=useState<GrantStatus>("REQUESTED");
  const [offset,setOffset]=useState(0),[refresh,setRefresh]=useState(0);
  const [formOpen,setFormOpen]=useState(false),[notice,setNotice]=useState("");
  const limit=25,role=kind==="support-institution"?"ROLE_SUPPORT_INSTITUTION_OPERATOR":"ROLE_LENDER_OPERATOR";
  const scope=kind+":"+status+":"+offset+":"+refresh;
  const state=useQueue(scope,token,()=>api<unknown>(governanceQueuePath(kind,status,limit,offset),token)
    .then(raw=>verifiedGrantPage(raw,status,role,kind==="support-institution"?"PROGRAM":"PROVIDER",limit,offset)));
  const title=kind==="support-institution"?"مجوزهای سازمان‌های حمایتگر":"مجوزهای تأمین‌کنندگان تسهیلات";
  function changed(message:string) {setRefresh(v=>v+1);setNotice(message);}
  return <section className="gov-panel">
    <div className="gov-heading"><div><small>دسترسی و راهبری · گردش‌کار کنترل‌شده</small><h3>{title}</h3></div>
      <div className="gov-heading-tools">
        <button type="button" className="gov-create" disabled={!currentIdentityId} onClick={()=>{setFormOpen(v=>!v);setNotice("");}}>درخواست دسترسی جدید</button>
        <label>وضعیت <select value={status} onChange={e=>{setStatus(e.target.value as GrantStatus);setOffset(0);setNotice("");}}>
          <option value="REQUESTED">در انتظار بررسی</option><option value="ACTIVE">فعال</option><option value="REVOKED">لغوشده</option>
        </select></label>
      </div>
    </div>
    {notice&&<p className="gov-action-success" role="status">{notice}</p>}
    {formOpen&&<GrantRequestForm token={token} kind={kind} onCancel={()=>setFormOpen(false)}
      onCreated={()=>{setFormOpen(false);setStatus("REQUESTED");setOffset(0);changed("درخواست ثبت شد؛ تا تأیید راهبر دوم دسترسی فعال نمی‌شود.");}}/>}
    <Feedback state={state}>{page=>page.items.length?<div className="gov-list">{page.items.map((g:GovernanceGrant)=>
      <article className="gov-row" key={g.id}>
        <div><strong>{shortId(g.id)}</strong><small>شناسه هویت: {shortId(g.identity_id)}</small></div>
        <div><strong>{g.role_code}</strong><small>{g.scope_type}: {shortId(g.scope_id)}</small></div>
        <div><strong>{grantStatusLabel(g.status)}</strong><small>نسخه {g.version.toLocaleString("fa-IR")}</small></div>
        <div><strong>شروع: {date(g.valid_from)}</strong><small>پایان: {date(g.valid_until)}</small></div>
        <small>مرجع دلیل: {g.reason_ref??"ثبت نشده"}</small>
        <GrantActions token={token} kind={kind} grant={g} currentIdentityId={currentIdentityId}
          onChanged={()=>changed(g.status==="REQUESTED"?"وضعیت درخواست تغییر کرد؛ فهرست دوباره دریافت شد.":"دسترسی لغو شد؛ فهرست دوباره دریافت شد.")}/>
      </article>)}</div>:<p className="gov-empty">رکوردی با این وضعیت در این صفحه وجود ندارد.</p>}</Feedback>
    <div className="gov-pagination"><button type="button" disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-limit))}>صفحه قبل</button>
      <span>صفحه {(offset/limit+1).toLocaleString("fa-IR")}</span>
      <button type="button" disabled={state.status!=="ready"||state.data.items.length<limit} onClick={()=>setOffset(offset+limit)}>صفحه بعد</button>
    </div>
  </section>;
}

function BenefitReviewQueue({token}:{token:string}) {
  const [status,setStatus]=useState<ReviewStatus>("REQUESTED");
  const [offset,setOffset]=useState(0),limit=25,scope="benefit:"+status+":"+offset;
  const state=useQueue(scope,token,()=>api<unknown>(governanceQueuePath("benefit-lineage",status,limit,offset),token)
    .then(raw=>verifiedBenefitReviewPage(raw,status,limit,offset)));
  return <section className="gov-panel">
    <div className="gov-heading"><div><small>حکمرانی شواهد و سوابق</small><h3>بازبینی اتصال سوابق حمایتی</h3></div>
      <label>وضعیت <select value={status} onChange={e=>{setStatus(e.target.value as ReviewStatus);setOffset(0);}}>
        <option value="REQUESTED">در انتظار بررسی</option><option value="APPROVED">تأییدشده</option><option value="REJECTED">ردشده</option>
      </select></label>
    </div>
    <Feedback state={state}>{page=>page.items.length?<div className="gov-list">{page.items.map((r:BenefitLineageReview)=>
      <article className="gov-row gov-row--review" key={r.id}>
        <div><strong>{r.benefit_type==="MONTHLY_PENSION"?"مستمری ماهانه":"حمایت پس از خروج"}</strong><small>رکورد: {shortId(r.benefit_record_id)}</small></div>
        <div><strong>فرد: {shortId(r.participant_id)}</strong><small>برنامه: {shortId(r.program_id)}</small></div>
        <div><strong>دوره مشارکت: {shortId(r.participation_episode_id)}</strong><small>درخواست‌کننده: {shortId(r.requested_by)}</small></div>
        <div><strong>{reviewStatusLabel(r.status)}</strong><small>{date(r.created_at)}</small></div>
        <small>مرجع مدرک: {r.evidence_reference.slice(0,32)}{r.evidence_reference.length>32?"…":""}</small>
        <small>مرجع دلیل: {r.reason_reference}</small>
      </article>)}</div>:<p className="gov-empty">رکوردی با این وضعیت در این صفحه وجود ندارد.</p>}</Feedback>
    <div className="gov-pagination"><button type="button" disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-limit))}>صفحه قبل</button>
      <span>صفحه {(offset/limit+1).toLocaleString("fa-IR")}</span>
      <button type="button" disabled={state.status!=="ready"||state.data.items.length<limit} onClick={()=>setOffset(offset+limit)}>صفحه بعد</button>
    </div>
  </section>;
}
export function AdminGovernance({token,workspaces,currentIdentityId}:{token:string;workspaces:Workspace[];currentIdentityId:string|null}) {
  const allowed=(code:string,capability:string)=>workspaces.some(w=>w.workspace_code===code&&
    w.scope_type==="GLOBAL"&&w.scope_id===null&&w.role_codes.includes("ROLE_GOVERNANCE_APPROVER")&&w.capabilities.includes(capability));
  const support=allowed("ADMIN_ACCESS_GOVERNANCE","MANAGE_SUPPORT_INSTITUTION_GRANTS");
  const lender=allowed("ADMIN_ACCESS_GOVERNANCE","MANAGE_LENDER_GRANTS");
  const lineage=allowed("ADMIN_BENEFIT_LINEAGE_REVIEW","READ_LEGACY_BENEFIT_LINEAGE_REVIEW_QUEUE");
  if(!support&&!lender&&!lineage)return null;
  return <section className="gov-workspace" aria-label="دسترسی و راهبری">
    <div className="gov-intro"><h2>دسترسی و راهبری</h2><p>درخواست، تأیید و لغو مجوزهای برنامه و تأمین‌کننده با کنترل تفکیک درخواست‌کننده و تأییدکننده؛ صف بازبینی سوابق حمایتی همچنان فقط خواندنی است. هر عملیات در بک‌اند مستقل از نمایش پنل مجدداً مجوزسنجی و ثبت حسابرسی می‌شود.</p></div>
    {support&&<GrantQueue token={token} kind="support-institution" currentIdentityId={currentIdentityId}/>}
    {lender&&<GrantQueue token={token} kind="lender" currentIdentityId={currentIdentityId}/>}
    {lineage&&<BenefitReviewQueue token={token}/>}
  </section>;
}
