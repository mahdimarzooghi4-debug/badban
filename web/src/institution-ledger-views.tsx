import { useEffect, useState } from "react";
import { amount, api, ApiError, type Program } from "./api";
import {
  READ_PAGE_SIZE,
  nextPageOffset,
  previousPageOffset,
  readPagePath,
  verifiedProgramsPage,
} from "./paged-read-data";
import {
  financialHistoryPath,
  financialStatementPath,
  LEDGER_PAGE_SIZE,
  verifiedFinancialHistoryPage,
  verifiedProgramStatement,
  type FinancialHistoryPage,
  type ProgramStatement,
} from "./institution-ledger-data";
import "./institution-empty-views.css";
import "./institution-ledger-views.css";

type Mode = "history" | "reports";
type LoadState<T> =
  | { owner: string; scope: string; status: "loading" }
  | { owner: string; scope: string; status: "error"; message: string; statusCode: number }
  | { owner: string; scope: string; status: "ready"; data: T };

function useLive<T>(token: string, scope: string, loader: () => Promise<T>): LoadState<T> {
  const [saved, setSaved] = useState<LoadState<T>>({ owner: token, scope, status: "loading" });
  useEffect(() => {
    let active = true;
    setSaved({ owner: token, scope, status: "loading" });
    loader()
      .then(data => { if (active) setSaved({ owner: token, scope, status: "ready", data }); })
      .catch((error: unknown) => {
        if (!active) return;
        setSaved({
          owner: token,
          scope,
          status: "error",
          message: error instanceof Error ? error.message : "خطا در دریافت اطلاعات دفترکل",
          statusCode: error instanceof ApiError ? error.status : 0,
        });
      });
    return () => { active = false; };
    // Scope and authenticated owner fully identify each read request.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, scope]);
  return saved.owner === token && saved.scope === scope
    ? saved
    : { owner: token, scope, status: "loading" };
}

function unavailableMessage(state: Extract<LoadState<unknown>, { status: "error" }>): string {
  if (state.statusCode === 503) {
    return "منبع ثبت‌های دفترکل برای این برنامه در دسترس نیست. نبود شواهد به معنی صفر بودن مانده نیست.";
  }
  if (state.statusCode === 409) {
    return "شواهد مالی با محدوده برنامه یا شخصیت حقوقی سازگار نیست؛ برای جلوگیری از گزارش ناقص، نمایش متوقف شد.";
  }
  return state.message;
}

function SourceNote() {
  return <section className="institution-page-status" aria-label="منبع داده مالی">
    <div className="institution-page-status__identity">
      <strong>پنل سازمان حمایتگر</strong>
      <span>فقط داده دفترکل در برنامه‌های مجاز سازمان</span>
    </div>
    <span className="institution-page-status__badge">ثبت داخلی؛ نه تأیید انتقال بانکی</span>
  </section>;
}

function ProgramSelector({
  programs,
  selectedProgram,
  onSelect,
  onRefresh,
  offset,
  onOffset,
}: {
  programs: LoadState<{ items: Program[]; limit: number; offset: number }>;
  selectedProgram: string | null;
  onSelect: (value: string) => void;
  onRefresh: () => void;
  offset: number;
  onOffset: (value: number) => void;
}) {
  const rows = programs.status === "ready" ? programs.data.items : [];
  const next = programs.status === "ready"
    ? nextPageOffset(offset, rows.length, READ_PAGE_SIZE)
    : null;
  return <section className="institution-ledger-program">
    <div className="institution-ledger-program__select">
      <label htmlFor="institution-ledger-program-select">برنامه مجاز سازمان</label>
      <select
        id="institution-ledger-program-select"
        value={selectedProgram ?? ""}
        disabled={programs.status !== "ready" || rows.length === 0}
        onChange={event => onSelect(event.target.value)}
      >
        <option value="">انتخاب برنامه برای مشاهده اطلاعات مالی</option>
        {rows.map(program => <option key={program.program_id} value={program.program_id}>
          {program.name} · {program.code}
        </option>)}
      </select>
      <button type="button" className="institution-ledger-refresh" onClick={onRefresh}>
        بازخوانی برنامه‌ها
      </button>
    </div>
    {programs.status === "loading" && <p className="institution-ledger-feedback" role="status">در حال دریافت برنامه‌های مجاز…</p>}
    {programs.status === "error" && <p className="institution-ledger-feedback institution-ledger-feedback--error" role="alert">{programs.message}</p>}
    {programs.status === "ready" && rows.length === 0 &&
      <p className="institution-ledger-feedback">هیچ برنامه فعالی با مجوز این حساب در این صفحه یافت نشد.</p>}
    <div className="institution-ledger-pager" aria-label="صفحه‌بندی برنامه‌ها">
      <button type="button" disabled={offset === 0 || programs.status !== "ready"}
        onClick={() => onOffset(previousPageOffset(offset, READ_PAGE_SIZE))}>برنامه‌های قبلی</button>
      <span>صفحه {(Math.floor(offset / READ_PAGE_SIZE) + 1).toLocaleString("fa-IR")}</span>
      <button type="button" disabled={next === null}
        onClick={() => { if (next !== null) onOffset(next); }}>برنامه‌های بعدی</button>
    </div>
  </section>;
}

function DataPager({
  offset,
  total,
  limit,
  onOffset,
}: {
  offset: number;
  total: number;
  limit: number;
  onOffset: (value: number) => void;
}) {
  return <div className="institution-ledger-pager" aria-label="صفحه‌بندی سوابق دفترکل">
    <button type="button" disabled={offset === 0}
      onClick={() => onOffset(previousPageOffset(offset, limit))}>صفحه قبل</button>
    <span>صفحه {(Math.floor(offset / limit) + 1).toLocaleString("fa-IR")} · {total.toLocaleString("fa-IR")} ردیف</span>
    <button type="button" disabled={offset + limit >= total}
      onClick={() => onOffset(offset + limit)}>صفحه بعد</button>
  </div>;
}

function ledgerLayerLabel(value: string): string {
  if (value === "MONETARY") return "دفترکل پولی";
  if (value === "MEMORANDUM_CONTROL") return "کنترلی / یادداشتی";
  return "منعکس‌کننده منبع خارجی";
}
function normalBalanceLabel(value: string): string {
  if (value === "DEBIT") return "ماهیت بدهکار";
  if (value === "CREDIT") return "ماهیت بستانکار";
  return "ماهیت یادداشتی";
}

function HistoryContent({ data }: { data: FinancialHistoryPage }) {
  return <section className="institution-empty-panel">
    <header className="institution-empty-panel__heading">
      <img src="/assets/figma/institution-history.svg" width="25" height="25" alt="" />
      <div>
        <h2>سوابق ثبت‌شده در دفترکل بادبان</h2>
        <p>فقط اسناد کامل و ثبت‌شده؛ بدون نمایش ثبت‌های آماده یا اسناد خارج از برنامه</p>
      </div>
      <span className="institution-empty-panel__state">منبع: دفترکل داخلی</span>
    </header>
    <p className="institution-ledger-disclaimer">
      این سوابق، ثبت داخلی بادبان هستند و به‌تنهایی تأیید انتقال بانکی، واریز، برداشت یا پرداخت واقعی محسوب نمی‌شوند.
    </p>
    {data.items.length === 0 ? <div className="institution-ledger-feedback" role="status">
      در این صفحه سابقه‌ای وجود ندارد؛ برای مشاهده صفحه قبل از صفحه‌بندی استفاده کنید.
    </div> : <div className="institution-ledger-entry-list">
      {data.items.map(entry => <article className="institution-ledger-entry" key={entry.id}>
        <header className="institution-ledger-entry__header">
          <div>
            <strong>{entry.business_event_type}</strong>
            <code dir="ltr">{entry.id}</code>
          </div>
          <span>{entry.currency} · POSTED</span>
        </header>
        <div className="institution-ledger-entry__meta">
          <span>زمان اثر: <b dir="ltr">{new Date(entry.effective_at).toLocaleString("fa-IR")}</b></span>
          <span>زمان ثبت: <b dir="ltr">{new Date(entry.posted_at).toLocaleString("fa-IR")}</b></span>
          {entry.reversal_of_entry_id && <span>ثبت جبرانی برای: <code dir="ltr">{entry.reversal_of_entry_id}</code></span>}
        </div>
        <div className="institution-ledger-table-wrap">
          <table className="institution-ledger-table">
            <thead><tr>
              <th>حساب</th><th>مالک اقتصادی</th><th>طبقه حساب</th>
              <th>لایه دفترکل</th><th>ماهیت حساب</th><th>بدهکار</th><th>بستانکار</th>
            </tr></thead>
            <tbody>{entry.postings.map((posting, index) => <tr key={entry.id + ":" + index}>
              <td><strong>{posting.account_name}</strong><small dir="ltr">{posting.account_code}</small></td>
              <td>{posting.economic_owner_type}</td>
              <td>{posting.account_class}</td>
              <td>{ledgerLayerLabel(posting.ledger_layer)}</td>
              <td>{normalBalanceLabel(posting.normal_balance)}</td>
              <td dir="ltr">{amount(posting.debit_amount, posting.currency)}</td>
              <td dir="ltr">{amount(posting.credit_amount, posting.currency)}</td>
            </tr>)}</tbody>
          </table>
        </div>
        <footer className="institution-ledger-entry__footer">
          <span>ماهیت حساب برای هر ردیف جداگانه نمایش داده شده است</span>
          <span>مرجع شواهد: {entry.evidence_reference ?? "در این ثبت ارائه نشده است"}</span>
          {entry.policy_version_reference && <span>نسخه سیاست: {entry.policy_version_reference}</span>}
        </footer>
      </article>)}
    </div>}
  </section>;
}

function StatementContent({ data }: { data: ProgramStatement }) {
  return <section className="institution-empty-panel">
    <header className="institution-empty-panel__heading">
      <img src="/assets/figma/institution-chart.svg" width="25" height="25" alt="" />
      <div>
        <h2>صورت‌وضعیت دفترکل برنامه</h2>
        <p>ردیف‌های حسابی تجمیع‌شده بر اساس حساب، ارز، مالک اقتصادی و لایه دفترکل</p>
      </div>
      <span className="institution-empty-panel__state">منبع: دفترکل داخلی</span>
    </header>
    <p className="institution-ledger-disclaimer">
      این گزارش، صورت‌وضعیت داخلی دفترکل است؛ نه صورت‌حساب بانکی، نه گزارش حسابرسی‌شده و نه تأیید پرداخت.
      هیچ جمع کل بین ارزها یا لایه‌های متفاوت محاسبه نمی‌شود.
    </p>
    <div className="institution-ledger-metadata">
      <div><span>زمان برش منبع</span><strong dir="ltr">{new Date(data.snapshot_at).toLocaleString("fa-IR")}</strong></div>
      <div><span>نسخه قرارداد منبع</span><strong>{data.contract_version}</strong></div>
      <div><span>نسخه نگاشت حساب</span><strong>{data.mapping_version}</strong></div>
      <div><span>شناسه شخصیت حقوقی</span><code dir="ltr">{data.legal_entity_id}</code></div>
      <div className="institution-ledger-metadata__hash"><span>هش محتوای منبع</span><code dir="ltr">{data.content_hash}</code></div>
    </div>
    {data.items.length === 0 ? <div className="institution-ledger-feedback" role="status">
      در این صفحه ردیف حسابی وجود ندارد.
    </div> : <div className="institution-ledger-table-wrap">
      <table className="institution-ledger-table">
        <thead><tr>
          <th>حساب</th><th>مالک اقتصادی</th><th>لایه</th>
          <th>ماهیت حساب</th><th>ارز</th><th>مانده طبق ماهیت حساب</th>
        </tr></thead>
        <tbody>{data.items.map(row => <tr key={[
          row.account_code, row.currency, row.legal_entity_id, row.economic_owner_type,
          row.ledger_layer, row.normal_balance,
        ].join(":")}>
          <td><strong>{row.account_name}</strong><small dir="ltr">{row.account_code}</small><small>{row.account_class}</small></td>
          <td>{row.economic_owner_type}</td>
          <td>{ledgerLayerLabel(row.ledger_layer)}</td>
          <td>{normalBalanceLabel(row.normal_balance)}</td>
          <td dir="ltr">{row.currency}</td>
          <td dir="ltr"><strong>{amount(row.balance, row.currency)}</strong></td>
        </tr>)}</tbody>
      </table>
    </div>}
    <details className="institution-ledger-evidence">
      <summary>ردپای شواهد منبع ({data.evidence_references.length.toLocaleString("fa-IR")})</summary>
      <p>این مراجع، شناسه ثبت‌های دفترکل مشارکت‌کننده در هش منبع هستند؛ شناسه تراکنش بانکی نیستند.</p>
      <ul>{data.evidence_references.map(reference => <li key={reference}><code dir="ltr">{reference}</code></li>)}</ul>
    </details>
  </section>;
}

function InstitutionLedgerWorkspace({ token, mode }: { token: string; mode: Mode }) {
  const [programOffset, setProgramOffset] = useState(0);
  const [programRefresh, setProgramRefresh] = useState(0);
  const [selectedProgram, setSelectedProgram] = useState<string | null>(null);
  const [dataOffset, setDataOffset] = useState(0);
  const [dataRefresh, setDataRefresh] = useState(0);
  const programsScope = "institution-ledger-programs:" + programOffset + ":" + programRefresh;
  const programs = useLive(token, programsScope, () =>
    api<unknown>(readPagePath("programs", READ_PAGE_SIZE, programOffset), token)
      .then(raw => verifiedProgramsPage(raw, READ_PAGE_SIZE, programOffset)));
  const selected = programs.status === "ready" && selectedProgram
    ? programs.data.items.find(program => program.program_id === selectedProgram) ?? null
    : null;
  const programId = selected?.program_id ?? null;
  const historyScope = "institution-ledger-history:" + (programId ?? "none") + ":" + dataOffset + ":" + dataRefresh;
  const history = useLive<FinancialHistoryPage | null>(token, historyScope, () => {
    if (mode !== "history" || !programId) return Promise.resolve(null);
    return api<unknown>(financialHistoryPath(programId, LEDGER_PAGE_SIZE, dataOffset), token)
      .then(raw => verifiedFinancialHistoryPage(raw, programId, LEDGER_PAGE_SIZE, dataOffset));
  });
  const statementScope = "institution-ledger-statement:" + (programId ?? "none") + ":" + dataOffset + ":" + dataRefresh;
  const statement = useLive<ProgramStatement | null>(token, statementScope, () => {
    if (mode !== "reports" || !programId) return Promise.resolve(null);
    return api<unknown>(financialStatementPath(programId, LEDGER_PAGE_SIZE, dataOffset), token)
      .then(raw => verifiedProgramStatement(raw, programId, LEDGER_PAGE_SIZE, dataOffset));
  });
  const title = mode === "history" ? "سوابق مالی سازمان" : "گزارش‌های سازمان";
  const refreshData = () => { setDataOffset(0); setDataRefresh(value => value + 1); };
  return <div className="workspace-body institution-empty-pages">
    <SourceNote />
    <ProgramSelector
      programs={programs}
      selectedProgram={programId}
      onSelect={value => { setSelectedProgram(value || null); setDataOffset(0); setDataRefresh(value => value + 1); }}
      onRefresh={() => { setSelectedProgram(null); setProgramOffset(0); setProgramRefresh(value => value + 1); }}
      offset={programOffset}
      onOffset={value => { setProgramOffset(value); setSelectedProgram(null); setDataOffset(0); }}
    />
    <section className="institution-ledger-content">
      <div className="institution-ledger-content__heading">
        <div><span>{title}</span><strong>{selected ? selected.name : "ابتدا برنامه مجاز را انتخاب کنید"}</strong></div>
        <button type="button" className="institution-ledger-refresh" disabled={!programId} onClick={refreshData}>
          بازخوانی اطلاعات مالی
        </button>
      </div>
      {!programId ? <p className="institution-ledger-feedback" role="status">
        برای مشاهده سوابق یا صورت‌وضعیت، یک برنامه از فهرست مجاز سازمان انتخاب کنید.
      </p> : mode === "history" ? (
        history.status === "loading" ? <p className="institution-ledger-feedback" role="status">در حال دریافت سوابق ثبت‌شده…</p>
          : history.status === "error" ? <p className="institution-ledger-feedback institution-ledger-feedback--error" role="alert">{unavailableMessage(history)}</p>
            : history.data ? <>
              <HistoryContent data={history.data} />
              <DataPager offset={dataOffset} total={history.data.total_entries} limit={LEDGER_PAGE_SIZE} onOffset={setDataOffset} />
            </> : null
      ) : (
        statement.status === "loading" ? <p className="institution-ledger-feedback" role="status">در حال ساخت صورت‌وضعیت از ثبت‌های دفترکل…</p>
          : statement.status === "error" ? <p className="institution-ledger-feedback institution-ledger-feedback--error" role="alert">{unavailableMessage(statement)}</p>
            : statement.data ? <>
              <StatementContent data={statement.data} />
              <DataPager offset={dataOffset} total={statement.data.total_rows} limit={LEDGER_PAGE_SIZE} onOffset={setDataOffset} />
            </> : null
      )}
    </section>
  </div>;
}

export function InstitutionHistoryView({ token }: { token: string }) {
  return <InstitutionLedgerWorkspace token={token} mode="history" />;
}
export function InstitutionReportsView({ token }: { token: string }) {
  return <InstitutionLedgerWorkspace token={token} mode="reports" />;
}
