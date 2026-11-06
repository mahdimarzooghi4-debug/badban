import { useEffect, useState, type ReactNode } from "react";
import { amount, api, type Beneficiary, type Guarantee, type Page, type Program, type Provider } from "./api";
import { InstitutionFinancialDetail, LenderGuaranteeDetail } from "./operational-details";
import {
  READ_PAGE_SIZE, nextPageOffset, previousPageOffset, readPagePath,
  verifiedProgramsPage, verifiedProvidersPage, verifiedPagedBeneficiaries, verifiedPagedGuarantees,
} from "./paged-read-data";
import "./paged-workspaces.css";

type LoadState<T> =
  | { owner: string; scope: string; status: "loading" }
  | { owner: string; scope: string; status: "error"; message: string }
  | { owner: string; scope: string; status: "ready"; data: T };

function useLivePage<T>(token: string, scope: string, loader: () => Promise<T>): LoadState<T> {
  const [state, setState] = useState<LoadState<T>>({ owner: token, scope, status: "loading" });
  useEffect(() => {
    let active = true;
    setState({ owner: token, scope, status: "loading" });
    Promise.resolve().then(loader).then(
      data => { if (active) setState({ owner: token, scope, status: "ready", data }); },
      error => { if (active) setState({
        owner: token, scope, status: "error",
        message: error instanceof Error ? error.message : "دریافت فهرست امکان‌پذیر نشد.",
      }); },
    );
    return () => { active = false; };
    // The caller's token, scope and page offset are an indivisible read identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, scope]);
  return state.scope === scope && state.owner === token ? state : { owner: token, scope, status: "loading" };
}
function Loaded<T>({ state, children }: { state: LoadState<T>; children: (value: T) => ReactNode }) {
  if (state.status === "loading") return <p className="read-feedback" role="status">در حال خواندن اطلاعات از بادبان…</p>;
  if (state.status === "error") return <p className="read-feedback read-feedback--error" role="alert">{state.message}</p>;
  return <>{children(state.data)}</>;
}
function ReadPanel({ title, subtitle, children, extra }: {
  title: string; subtitle: string; children: ReactNode; extra?: ReactNode;
}) {
  return <section className="read-panel">
    <div className="read-heading"><div><h2>{title}</h2><p>{subtitle}</p></div>{extra}</div>
    {children}
  </section>;
}
function Paginator({ offset, page, change, label }: {
  offset: number; page: LoadState<Page<unknown>>; change: (offset: number) => void; label: string;
}) {
  const next = page.status === "ready" ? nextPageOffset(offset, page.data.items.length) : null;
  return <div className="read-paginator" aria-label={"صفحه‌بندی " + label}>
    <button type="button" disabled={offset===0||page.status!=="ready"}
      onClick={() => change(previousPageOffset(offset))}>صفحه قبل</button>
    <span>صفحه {(Math.floor(offset / READ_PAGE_SIZE) + 1).toLocaleString("fa-IR")}</span>
    <button type="button" disabled={next===null} onClick={() => { if (next!==null) change(next); }}>صفحه بعد</button>
  </div>;
}
function InstitutionPeople({ token, programId, programName }: { token: string; programId: string; programName: string }) {
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [selected, setSelected] = useState<{ participantId: string; episodeId: string } | null>(null);
  const scope = "people:" + programId + ":" + offset + ":" + refresh;
  const state = useLivePage<Page<Beneficiary>>(token, scope, () =>
    api<unknown>(readPagePath("beneficiaries", READ_PAGE_SIZE, offset, programId), token)
      .then(raw => verifiedPagedBeneficiaries(raw, programId, READ_PAGE_SIZE, offset)));
  const selectedRow = state.status === "ready" && selected
    ? state.data.items.find(item => item.participant_id === selected.participantId && item.episode_id === selected.episodeId)
    : null;
  return <>
    <ReadPanel title="افراد منتسب به برنامه" subtitle="فهرست واقعی مشارکت‌ها؛ بدون اطلاعات هویتی حساس"
      extra={<button className="read-refresh" type="button" onClick={() => { setSelected(null); setRefresh(r=>r+1); }}>بازخوانی افراد</button>}>
      <Loaded state={state}>{data => data.items.length ? <div className="read-list">
        {data.items.map(person => <div className="read-line" key={person.episode_id}>
          <div><strong>پرونده {person.participant_id.slice(0,8)}…</strong>
            <small>دوره مشارکت: {person.episode_id.slice(0,8)}…</small></div>
          <div><strong>وضعیت: {person.participation_status}</strong>
            <small>رضایت: {person.consent_state}</small></div>
          <button type="button" className="read-action" onClick={() => setSelected({participantId:person.participant_id,episodeId:person.episode_id})}>جزئیات مالی</button>
        </div>)}
      </div> : <p className="read-empty">در این صفحه، فردی برای نمایش وجود ندارد.</p>}</Loaded>
      <Paginator offset={offset} page={state} label="افراد" change={next => { setOffset(next); setSelected(null); }}/>
    </ReadPanel>
    {selectedRow && selected && <InstitutionFinancialDetail key={programId+":"+selected.episodeId}
      token={token} programId={programId} programName={programName} participant={selectedRow}
      participantId={selected.participantId} episodeId={selected.episodeId} onClose={() => setSelected(null)}/>}
  </>;
}
export function InstitutionWorkspace({ token }: { token: string }) {
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [selectedProgram, setSelectedProgram] = useState<string | null>(null);
  const scope="programs:"+offset+":"+refresh;
  const state=useLivePage<Page<Program>>(token,scope,()=>api<unknown>(readPagePath("programs",READ_PAGE_SIZE,offset),token)
    .then(raw=>verifiedProgramsPage(raw,READ_PAGE_SIZE,offset)));
  const selected=state.status==="ready"&&selectedProgram
    ?state.data.items.find(row=>row.program_id===selectedProgram):null;
  return <div className="workspace-body read-workspace">
    <ReadPanel title="برنامه‌های مجاز سازمان" subtitle="فقط برنامه‌هایی که بک‌اند در اختیار این حساب قرار داده است"
      extra={<button className="read-refresh" type="button" onClick={()=>{setSelectedProgram(null);setRefresh(r=>r+1);}}>بازخوانی برنامه‌ها</button>}>
      <Loaded state={state}>{page => page.items.length ? <div className="read-selector-grid">
        {page.items.map(program=><button type="button" key={program.program_id}
          className={"read-selector"+(selected?.program_id===program.program_id?" read-selector--selected":"")}
          onClick={()=>setSelectedProgram(program.program_id)}>
          <span className="read-tile-icon" aria-hidden="true">▣</span><strong>{program.name}</strong>
          <small>کد: {program.code}</small><small>وضعیت: فعال</small>
        </button>)}
      </div>:<p className="read-empty">برنامه مجازی در این صفحه یافت نشد.</p>}</Loaded>
      <Paginator offset={offset} page={state} label="برنامه‌ها" change={next=>{setOffset(next);setSelectedProgram(null);}}/>
    </ReadPanel>
    {selected && <InstitutionPeople key={selected.program_id} token={token} programId={selected.program_id} programName={selected.name}/>}
    <p className="read-policy">اصل سرمایه سازمانی متعلق به سازمان می‌ماند و فرد فقط مطابق قرارداد از منافع آن بهره‌مند می‌شود. ورود گروهی و واریز سازمانی در این نسخه فعال نیستند.</p>
  </div>;
}
function ProviderGuarantees({ token, providerId }: { token: string; providerId: string }) {
  const [offset,setOffset]=useState(0);
  const [refresh,setRefresh]=useState(0);
  const [selectedGuarantee,setSelectedGuarantee]=useState<string|null>(null);
  const scope="guarantees:"+providerId+":"+offset+":"+refresh;
  const state=useLivePage<Page<Guarantee>>(token,scope,()=>
    api<unknown>(readPagePath("guarantees",READ_PAGE_SIZE,offset,providerId),token)
      .then(raw=>verifiedPagedGuarantees(raw,providerId,READ_PAGE_SIZE,offset)));
  const selected=state.status==="ready"&&selectedGuarantee
    ?state.data.items.find(g=>g.guarantee_case_id===selectedGuarantee):null;
  return <>
    <ReadPanel title="ضمانت‌ها و وضعیت تسهیلات" subtitle="فقط ضمانت‌های تأمین‌کننده انتخاب‌شده"
      extra={<button type="button" className="read-refresh" onClick={()=>{setSelectedGuarantee(null);setRefresh(r=>r+1);}}>بازخوانی ضمانت‌ها</button>}>
      <Loaded state={state}>{page=>page.items.length?<div className="read-list">{page.items.map(g=>
        <div className="read-line" key={g.guarantee_case_id}>
          <div><strong>ضمانت {g.guarantee_case_id.slice(0,8)}…</strong><small>وضعیت: {g.case_state}</small></div>
          <div><strong>تعهد ضمانت: {amount(g.current_guarantee_exposure,g.currency)}</strong>
            <small>مانده وام: {amount(g.outstanding_principal,g.loan_currency)}</small></div>
          <button className="read-action" type="button" onClick={()=>setSelectedGuarantee(g.guarantee_case_id)}>جزئیات ضمانت</button>
        </div>)}</div>:<p className="read-empty">در این صفحه ضمانتی ثبت نشده است.</p>}</Loaded>
      <Paginator offset={offset} page={state} label="ضمانت‌ها" change={next=>{setOffset(next);setSelectedGuarantee(null);}}/>
    </ReadPanel>
    {selected && <LenderGuaranteeDetail key={selected.guarantee_case_id} guarantee={selected} onClose={()=>setSelectedGuarantee(null)}/>}
  </>;
}
export function LenderWorkspace({ token }: { token: string }) {
  const [offset,setOffset]=useState(0);
  const [refresh,setRefresh]=useState(0);
  const [selectedProvider,setSelectedProvider]=useState<string|null>(null);
  const scope="providers:"+offset+":"+refresh;
  const state=useLivePage<Page<Provider>>(token,scope,()=>api<unknown>(readPagePath("providers",READ_PAGE_SIZE,offset),token)
    .then(raw=>verifiedProvidersPage(raw,READ_PAGE_SIZE,offset)));
  const selected=state.status==="ready"&&selectedProvider
    ?state.data.items.find(item=>item.provider_id===selectedProvider):null;
  return <div className="workspace-body read-workspace">
    <ReadPanel title="تأمین‌کنندگان مجاز" subtitle="انتخاب محدوده تأمین‌کننده بر اساس مجوز واقعی بک‌اند"
      extra={<button className="read-refresh" type="button" onClick={()=>{setSelectedProvider(null);setRefresh(r=>r+1);}}>بازخوانی تأمین‌کنندگان</button>}>
      <Loaded state={state}>{page=>page.items.length?<div className="read-selector-grid">{page.items.map(provider=>
        <button type="button" key={provider.provider_id}
          className={"read-selector"+(selected?.provider_id===provider.provider_id?" read-selector--selected":"")}
          onClick={()=>setSelectedProvider(provider.provider_id)}>
          <span className="read-tile-icon" aria-hidden="true">◇</span>
          <strong>{provider.display_name}</strong><small>کد: {provider.provider_code}</small>
        </button>)}</div>:<p className="read-empty">هیچ تأمین‌کننده مجازی در این صفحه یافت نشد.</p>}</Loaded>
      <Paginator offset={offset} page={state} label="تأمین‌کنندگان" change={next=>{setOffset(next);setSelectedProvider(null);}}/>
    </ReadPanel>
    {selected && <ProviderGuarantees key={selected.provider_id} token={token} providerId={selected.provider_id}/>}
    <p className="read-policy">مانده وام و مبلغ ضمانت، دو مفهوم مستقل‌اند. هیچ تصمیم اعتباری، صدور ضمانت یا پرداختی از این نما انجام نمی‌شود.</p>
  </div>;
}
