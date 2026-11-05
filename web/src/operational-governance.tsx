import { useEffect, useState, type ReactNode } from "react";
import { api } from "./api";
import {
  governanceQueuePath, verifiedGrantPage, verifiedBenefitReviewPage, type GrantQueueKind,
  type GrantStatus, type ReviewStatus, type GovernanceGrant, type BenefitLineageReview,
} from "./governance-data";
import "./operational-governance.css";

type Workspace = { workspace_code: string; role_codes: string[]; capabilities: string[] };
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
function GrantQueue({token,kind}:{token:string;kind:GrantQueueKind}) {
  const [status,setStatus]=useState<GrantStatus>("REQUESTED");
  const [offset,setOffset]=useState(0);
  const limit=25,role=kind==="support-institution"?"ROLE_SUPPORT_INSTITUTION_OPERATOR":"ROLE_LENDER_OPERATOR";
  const scope=kind+":"+status+":"+offset;
  const state=useQueue(scope,token,()=>api<unknown>(governanceQueuePath(kind,status,limit,offset),token)
    .then(raw=>verifiedGrantPage(raw,status,role,kind==="support-institution"?"PROGRAM":"PROVIDER",limit,offset)));
  const title=kind==="support-institution"?"مجوزهای سازمان‌های حمایتگر":"مجوزهای تأمین‌کنندگان تسهیلات";
  return <section className="gov-panel">
    <div className="gov-heading"><div><small>دسترسی و راهبری · فقط خواندنی</small><h3>{title}</h3></div>
      <label>وضعیت <select value={status} onChange={e=>{setStatus(e.target.value as GrantStatus);setOffset(0);}}>
        <option value="REQUESTED">در انتظار بررسی</option><option value="ACTIVE">فعال</option><option value="REVOKED">لغوشده</option>
      </select></label>
    </div>
    <Feedback state={state}>{page=>page.items.length?<div className="gov-list">{page.items.map((g:GovernanceGrant)=>
      <article className="gov-row" key={g.id}>
        <div><strong>{shortId(g.id)}</strong><small>شناسه هویت: {shortId(g.identity_id)}</small></div>
        <div><strong>{g.role_code}</strong><small>{g.scope_type}: {shortId(g.scope_id)}</small></div>
        <div><strong>{grantStatusLabel(g.status)}</strong><small>نسخه {g.version.toLocaleString("fa-IR")}</small></div>
        <div><strong>شروع: {date(g.valid_from)}</strong><small>پایان: {date(g.valid_until)}</small></div>
        <small>مرجع دلیل: {g.reason_ref??"ثبت نشده"}</small>
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
export function AdminGovernance({token,workspaces}:{token:string;workspaces:Workspace[]}) {
  const allowed=(code:string,capability:string)=>workspaces.some(w=>w.workspace_code===code&&
    w.role_codes.includes("ROLE_GOVERNANCE_APPROVER")&&w.capabilities.includes(capability));
  const support=allowed("ADMIN_ACCESS_GOVERNANCE","MANAGE_SUPPORT_INSTITUTION_GRANTS");
  const lender=allowed("ADMIN_ACCESS_GOVERNANCE","MANAGE_LENDER_GRANTS");
  const lineage=allowed("ADMIN_BENEFIT_LINEAGE_REVIEW","READ_LEGACY_BENEFIT_LINEAGE_REVIEW_QUEUE");
  if(!support&&!lender&&!lineage)return null;
  return <section className="gov-workspace" aria-label="دسترسی و راهبری">
    <div className="gov-intro"><h2>دسترسی و راهبری</h2><p>فهرست مجوزها و درخواست‌های بازبینی بر اساس دسترسی راهبری معتبر؛ این نما هیچ مجوزی صادر یا لغو نمی‌کند.</p></div>
    {support&&<GrantQueue token={token} kind="support-institution"/>}
    {lender&&<GrantQueue token={token} kind="lender"/>}
    {lineage&&<BenefitReviewQueue token={token}/>}
  </section>;
}
