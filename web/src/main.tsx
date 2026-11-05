import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { beginSignIn, completeSignIn, localSignOut } from "./auth";
import { amount, client, type AdminWorkspace, type Beneficiary,
  type Guarantee, type Provider, type ServiceCode, type ServiceRequest } from "./api";
import "./styles.css";

type Surface = "individual" | "institution" | "lender" | "admin";
type LoadState<T> = { kind: "loading" } | { kind: "ready"; data: T } | { kind: "error"; message: string };

const sections: Array<{ id: Surface; name: string; description: string; symbol: string }> = [
  { id: "individual", name: "مشتریان", description: "پرونده مالی و درخواست خدمات", symbol: "♙" },
  { id: "institution", name: "سازمان‌های حمایتگر", description: "افراد منتسب به برنامه‌های مجاز", symbol: "♧" },
  { id: "lender", name: "تأمین‌کنندگان تسهیلات", description: "ضمانت‌ها و وضعیت وام‌های مرتبط", symbol: "▣" },
  { id: "admin", name: "مدیریت مرکزی", description: "دسترسی‌های مدیریتی و راهبری", symbol: "◈" },
];

const services: Array<{ code: ServiceCode; title: string; detail: string; symbol: string }> = [
  { code: "LOAN_GUARANTEE", title: "ضمانت وام", detail: "درخواست بررسی ضمانت تسهیلات", symbol: "♢" },
  { code: "MONTHLY_PENSION", title: "مستمری ماهانه", detail: "درخواست خدمات حمایتی دوره‌ای", symbol: "◷" },
  { code: "POST_EXIT_SUPPORT", title: "آینده مالی", detail: "درخواست حمایت پس از خروج", symbol: "♡" },
];

function Brand({ light = false }: { light?: boolean }) {
  return <span className={"brand" + (light ? " brand--light" : "")} aria-label="بادبان">
    <span className="brand-sail" aria-hidden="true">◢</span>
    <span><strong>بادبان</strong><small>سرمایه، اعتبار، توانمندسازی</small></span>
  </span>;
}

function Button({ children, onClick, outline = false, disabled = false }:
  { children: React.ReactNode; onClick?: () => void; outline?: boolean; disabled?: boolean }) {
  return <button className={"button" + (outline ? " button--outline" : "")}
    type="button" disabled={disabled} onClick={onClick}>{children}</button>;
}

function Landing({ signIn, openWorkspace }: { signIn: () => void; openWorkspace: (s: Surface) => void }) {
  return <div className="landing">
    <header className="site-header">
      <a href="#home" aria-label="خانه بادبان"><Brand light /></a>
      <nav aria-label="ناوبری اصلی">
        <a href="#home">خانه</a><a href="#about">درباره بادبان</a><a href="#benefits">راهکارها</a>
        <a href="#audiences">مخاطبان</a><a href="#contact">همکاری</a>
      </nav>
      <Button onClick={signIn}>ورود به سامانه</Button>
    </header>
    <main>
      <section className="hero" id="home">
        <div className="hero-photo" role="img" aria-label="قایق بادبانی در افق دریا هنگام غروب" />
        <div className="hero-shade" />
        <div className="hero-copy">
          <p className="eyebrow">بادبان</p>
          <h1>پلی مطمئن میان<br />سرمایه و فرصت‌های مالی</h1>
          <p>بستری یکپارچه برای مدیریت سرمایه، همکاری نهادهای حمایتگر و
            دسترسی مسئولانه به تسهیلات؛ با حفظ مالکیت منابع و شفافیت تعهدات.</p>
          <div className="hero-actions">
            <Button onClick={signIn}>ورود به سامانه</Button>
            <a className="button button--dark-outline" href="#about">آشنایی با بادبان</a>
          </div>
        </div>
      </section>
      <section className="benefits" id="benefits" aria-label="مزیت‌های بادبان">
        {[
          ["◈", "دسترسی به فرصت‌های مالی", "مسیرهای روشن برای خدمات و تسهیلات"],
          ["♧", "همکاری سازمانی", "تأمین سرمایه با حفظ حقوق مالکیت"],
          ["◇", "پشتوانه و ضمانت", "شفافیت تعهدات و کنترل ریسک"],
          ["▤", "ردپای مالی", "پیگیری گزارش‌ها و وضعیت‌های معتبر"],
        ].map(([symbol, title, detail]) =>
          <article className="benefit" key={title}><span className="benefit-icon">{symbol}</span>
            <h2>{title}</h2><p>{detail}</p></article>)}
      </section>
      <section className="about-section section-container" id="about">
        <div className="about-content">
          <span className="section-kicker">آشنایی با بادبان</span><h2>بادبان چیست؟</h2>
          <p>بادبان بستری مالی و اعتباری برای پیوند سرمایه‌های شخصی و منابع حمایتگر با
            فرصت‌های مالی است. نقش سازمان، تأمین‌کننده تسهیلات و فرد، در این بستر از هم تفکیک می‌شود.</p>
          <p className="muted">مالکیت اصل سرمایه، حق بهره‌مندی و امکان برداشت مستقل‌اند.
            دریافت خدمات و ضمانت نیز مطابق مجوزها و شواهد معتبر انجام می‌شود.</p>
          <a className="button button--outline" href="#audiences">اطلاعات بیشتر درباره بادبان</a>
        </div>
        <div className="about-photo" role="img" aria-label="نمای ساختمان اداری مدرن با شیشه‌های آبی" />
      </section>
      <section className="audiences section-container" id="audiences">
        <h2>ذی‌نفعان و مخاطبان بادبان</h2><div className="audience-grid">
          {sections.map(item =>
            <article className="audience-card" key={item.id}>
              <span className="audience-icon" aria-hidden="true">{item.symbol}</span>
              <h3>{item.name}</h3><p>{item.description}</p>
              <button type="button" onClick={() => openWorkspace(item.id)}>مشاهده محیط <span aria-hidden="true">‹</span></button>
            </article>)}
        </div>
      </section>
      <section className="trust section-container">
        <h2>اعتماد، شفافیت و حکمرانی</h2>
        <div className="trust-grid">
          {[["◉", "شفافیت کامل", "در فرایندها و جریان منابع"],
            ["▱", "مالکیت روشن", "حقوق و تعهدات مشخص"],
            ["♧", "کنترل مسئولانه", "بر پایه ارزیابی و مدیریت ریسک"],
            ["◇", "قابلیت حسابرسی", "ردپای تغییرات و مستندات"]]
            .map(([symbol, title, detail]) =>
              <div key={title}><span>{symbol}</span><h3>{title}</h3><p>{detail}</p></div>)}
        </div>
      </section>
      <section className="callout section-container" id="contact">
        <div><h2>به شبکه حمایت و توانمندسازی بادبان بپیوندید</h2>
          <p>برای آشنایی با خدمات و مسیرهای همکاری، از محیط متناسب با نقش خود وارد شوید.</p></div>
        <Button onClick={signIn}>ورود و آغاز آشنایی</Button>
      </section>
    </main>
    <footer className="footer"><Brand light />
      <div><h3>دسترسی سریع</h3><a href="#home">خانه</a><a href="#audiences">محیط‌های بادبان</a><a href="#benefits">راهکارها</a></div>
      <div><h3>اطلاعات بیشتر</h3><a href="#about">درباره بادبان</a><a href="#contact">همکاری</a></div>
      <p className="footnote">© بادبان؛ حقوق محفوظ است.</p>
    </footer>
  </div>;
}

function Remote<T>({ state, render }: { state: LoadState<T>; render: (data: T) => React.ReactNode }) {
  if (state.kind === "loading") return <div className="notice" role="status">در حال دریافت اطلاعات از بادبان…</div>;
  if (state.kind === "error") return <div className="notice notice--error" role="alert">{state.message}</div>;
  return <>{render(state.data)}</>;
}

function useRemote<T>(token: string, loader: (t: string) => Promise<T>, scope: string): LoadState<T> {
  const [state, setState] = useState<LoadState<T>>({ kind: "loading" });
  useEffect(() => {
    let active = true;
    setState({ kind: "loading" });
    loader(token).then(data => active && setState({ kind: "ready", data }))
      .catch((e: unknown) => active && setState({ kind: "error", message: e instanceof Error ? e.message : "خطا در دریافت اطلاعات" }));
    return () => { active = false; };
    // Each scope change is a distinct authorized read; the backend remains authoritative.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, scope]);
  return state;
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="panel"><h2>{title}</h2>{children}</section>;
}
function Empty({ children }: { children: React.ReactNode }) {
  return <div className="empty">{children}</div>;
}

function Individual({ token }: { token: string }) {
  const financial = useRemote(token, client.financial, "individual-financial");
  const requestState = useRemote(token, client.requests, "individual-requests");
  const [items, setItems] = useState<ServiceRequest[] | null>(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const pendingKey = useRef<{ code: ServiceCode; key: string } | null>(null);

  async function submit(code: ServiceCode) {
    if (busy) return;
    setBusy(true); setStatus("");
    if (pendingKey.current?.code !== code) pendingKey.current = { code, key: crypto.randomUUID() };
    try {
      const item = await client.submitRequest(token, code, pendingKey.current.key);
      setItems(prev => [item, ...(prev ?? (requestState.kind === "ready" ? requestState.data.items : []))]);
      setStatus("درخواست ثبت شد؛ وضعیت: دریافت‌شده. این به معنی تأیید یا پرداخت نیست.");
      pendingKey.current = null;
    } catch (error) {
      setStatus(error instanceof Error ? error.message + " — برای تلاش دوباره همین درخواست حفظ می‌شود." : "خطا در ثبت");
    } finally { setBusy(false); }
  }

  return <div className="workspace-body">
    <div className="welcome"><h2>پرونده مالی شما، شفاف و یکپارچه</h2>
      <p>مبالغ و وضعیت‌ها فقط از سرویس بادبان دریافت می‌شوند.</p></div>
    <Panel title="خدمات بادبان">
      <div className="service-grid">{services.map(service => <article className="service-card" key={service.code}>
        <span className="service-icon">{service.symbol}</span><h3>{service.title}</h3><p>{service.detail}</p>
        <Button onClick={() => void submit(service.code)} disabled={busy}>ثبت درخواست</Button>
      </article>)}</div>
      {status && <p className="notice" role="status">{status}</p>}
    </Panel>
    <Panel title="درخواست‌های من">
      <Remote state={requestState} render={data => {
        const rows = items ?? data.items;
        return rows.length ? <div className="rows">{rows.map(r =>
          <div className="data-row" key={r.id}><strong>{services.find(s => s.code === r.service_code)?.title ?? r.service_code}</strong>
            <span>دریافت‌شده</span><small>{new Date(r.submitted_at).toLocaleDateString("fa-IR")}</small></div>)}</div>
          : <Empty>هنوز درخواستی ثبت نشده است.</Empty>;
      }} />
    </Panel>
    <Panel title="پرونده مالی"><Remote state={financial} render={data => <>
      <div className="metric-grid">
        <div className="metric"><span>ضمانت‌های ثبت‌شده</span><strong>{data.guarantee_cases.length.toLocaleString("fa-IR")}</strong></div>
        <div className="metric"><span>مستمری‌های ثبت‌شده</span><strong>{data.monthly_entitlements.length.toLocaleString("fa-IR")}</strong></div>
        <div className="metric"><span>پرونده‌های پس از خروج</span><strong>{data.post_exit_cases.length.toLocaleString("fa-IR")}</strong></div>
      </div>
      <div className="rows">{data.balances.map(b => <div className="data-row" key={b.currency}>
        <strong>مانده اصل تسهیلات ({b.currency})</strong>
        <span>{amount(b.outstanding_principal, b.currency)}</span>
        <small>پرداخت: {b.payment_status === "NOT_CONFIGURED" ? "متصل نیست" : "نامشخص"}</small>
      </div>)}</div>
      {!data.balances.length && <Empty>هنوز اطلاعات مالی قابل نمایش وجود ندارد.</Empty>}
      <div className="notice">واریز و برداشت وجه در API فعلی فعال نشده‌اند. داده سرمایه شخصی و سرمایه سازمانی در این نما با یکدیگر جمع نمی‌شوند.</div>
      <div className="disabled-actions"><Button disabled>واریز وجه — غیرفعال</Button><Button disabled outline>درخواست برداشت — غیرفعال</Button></div>
    </>} /></Panel>
  </div>;
}

function Institution({ token }: { token: string }) {
  const programs = useRemote(token, client.programs, "institution-programs");
  const [selected, setSelected] = useState("");
  const people = useRemote(token, t => selected ? client.beneficiaries(t, selected) : Promise.resolve({ items: [], limit: 50, offset: 0 } as { items: Beneficiary[]; limit: number; offset: number }), selected);
  return <div className="workspace-body">
    <Panel title="برنامه‌های مجاز سازمان"><Remote state={programs} render={data =>
      data.items.length ? <div className="selector-cards">{data.items.map(p =>
        <button className={selected === p.program_id ? "selector selected" : "selector"} key={p.program_id}
          onClick={() => setSelected(p.program_id)} type="button"><strong>{p.name}</strong><small>{p.code} · {p.status}</small></button>)}</div>
        : <Empty>برنامه مجازی به این حساب اختصاص داده نشده است.</Empty>} />
    </Panel>
    <Panel title="افراد منتسب به برنامه">{!selected ? <Empty>برای مشاهده افراد، یکی از برنامه‌های مجاز را انتخاب کنید.</Empty>
      : <Remote state={people} render={data => data.items.length ? <div className="rows">{data.items.map(r =>
        <div className="data-row" key={r.episode_id}><strong>پرونده {r.participant_id.slice(0, 8)}…</strong>
          <span>{r.participation_status}</span><small>وضعیت رضایت: {r.consent_state}</small></div>)}</div>
        : <Empty>در این برنامه فردی برای نمایش ثبت نشده است.</Empty>} />}
    </Panel>
    <div className="notice">ورود گروهی افراد و تأمین مالی سازمانی هنوز API عملیاتی مصوب ندارند؛ هیچ پرداخت یا انتساب جدیدی از این صفحه انجام نمی‌شود.</div>
  </div>;
}

function Lender({ token }: { token: string }) {
  const providers = useRemote(token, client.providers, "lender-providers");
  const [selected, setSelected] = useState("");
  const guarantees = useRemote(token, t => selected ? client.guarantees(t, selected) : Promise.resolve({ items: [], limit: 50, offset: 0 } as { items: Guarantee[]; limit: number; offset: number }), selected);
  return <div className="workspace-body">
    <Panel title="تأمین‌کنندگان مجاز"><Remote state={providers} render={data =>
      data.items.length ? <div className="selector-cards">{data.items.map((p: Provider) =>
        <button type="button" onClick={() => setSelected(p.provider_id)}
          className={selected === p.provider_id ? "selector selected" : "selector"} key={p.provider_id}>
          <strong>{p.display_name}</strong><small>{p.provider_code}</small></button>)}</div>
        : <Empty>دسترسی به هیچ تأمین‌کننده‌ای ثبت نشده است.</Empty>} /></Panel>
    <Panel title="ضمانت‌ها و وضعیت تسهیلات">
      {!selected ? <Empty>یک تأمین‌کننده مجاز را انتخاب کنید.</Empty> :
        <Remote state={guarantees} render={data =>
          data.items.length ? <div className="rows">{data.items.map((g: Guarantee) =>
            <div className="data-row data-row--lender" key={g.guarantee_case_id}>
              <strong>ضمانت {g.guarantee_case_id.slice(0, 8)}…</strong><span>وضعیت: {g.case_state}</span>
              <span>مبلغ ضمانت: {amount(g.current_guarantee_exposure, g.currency)}</span>
              <span>مانده وام: {amount(g.outstanding_principal, g.loan_currency)}</span>
            </div>)}</div> : <Empty>هیچ ضمانتی برای این تأمین‌کننده گزارش نشده است.</Empty>} />}
    </Panel>
    <div className="notice">مبلغ ضمانت و مانده وام مستقل‌اند. این صفحه امکان صدور ضمانت یا پرداخت تسهیلات ندارد.</div>
  </div>;
}

function Admin({ token }: { token: string }) {
  const data = useRemote(token, client.workspaces, "admin-workspaces");
  return <div className="workspace-body"><Panel title="حوزه‌های مدیریتی مجاز">
    <Remote state={data} render={d => d.items.length ? <div className="selector-cards">
      {d.items.map((w: AdminWorkspace, i: number) =>
        <div className="selector" key={w.workspace_code + i}>
          <strong>{w.workspace_code}</strong><small>{w.capabilities.join(" · ") || "بدون عملیات مجاز"}</small>
        </div>)}</div> : <Empty>هیچ حوزه مدیریتی فعالی برای این حساب ثبت نشده است.</Empty>} />
  </Panel><div className="notice">نمایه دسترسی فقط برای راهبری است. هر دستور مالی یا مدیریتی به مجوز مستقل بک‌اند نیاز دارد؛ این نسخه هیچ دستور حساس صادر نمی‌کند.</div></div>;
}

const navigation: Record<Surface, string[]> = {
  individual: ["خانه", "خدمات", "درخواست‌ها", "مالی", "حساب"],
  institution: ["داشبورد", "افراد", "تأمین سرمایه", "سوابق مالی", "گزارش‌ها"],
  lender: ["داشبورد", "ضمانت‌ها", "تسهیلات", "سوابق", "گزارش‌ها"],
  admin: ["داشبورد", "افراد", "سازمان‌ها و برنامه‌ها", "سرمایه و پشتوانه", "ضمانت و تسهیلات",
    "مالی و تطبیق", "سیاست‌ها و ریسک", "دسترسی و راهبری", "گزارش‌ها و حسابرسی"],
};

function Workspace({ token, surface, choose, logout }: {
  token: string; surface: Surface; choose: (s: Surface | null) => void; logout: () => void;
}) {
  const selected = sections.find(s => s.id === surface)!;
  return <div className={"workspace workspace--" + surface} dir="rtl">
    <aside className="sidebar">
      <Brand light /><p>{selected.name}</p>
      <nav aria-label={"منوی " + selected.name}>
        {navigation[surface].map((name, index) => <div className={"nav-item" + (!index ? " nav-item--active" : "")}
          key={name}><span aria-hidden="true">{["▦", "♧", "◇", "▤", "◈", "♢", "♧", "◇", "▣"][index]}</span>
          {name}{index !== 0 && <small>در مراحل بعد</small>}</div>)}
      </nav>
      <button className="sidebar-back" onClick={() => choose(null)} type="button">تغییر محیط</button>
      <button className="sidebar-logout" type="button" onClick={logout}>خروج از حساب (محلی)</button>
    </aside>
    <main className="workspace-main">
      <div className="workspace-top"><span>بادبان / {selected.name}</span><strong>{selected.description}</strong></div>
      <div className="workspace-heading"><h1>{selected.name}</h1><p>اطلاعات معتبر از API بادبان</p></div>
      {surface === "individual" ? <Individual token={token}/> : surface === "institution" ?
        <Institution token={token}/> : surface === "lender" ? <Lender token={token}/> : <Admin token={token}/>}
    </main>
  </div>;
}

function App() {
  const [token, setToken] = useState<string | null>(null);
  const [surface, setSurface] = useState<Surface | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(window.location.pathname === "/auth/callback");

  useEffect(() => {
    if (window.location.pathname !== "/auth/callback") return;
    let live = true;
    completeSignIn().then(accessToken => { if (live) { setToken(accessToken); setLoading(false); } })
      .catch((e: unknown) => { if (live) { setLoading(false); setError(e instanceof Error ? e.message : "ورود ناموفق بود."); } });
    return () => { live = false; };
  }, []);

  function openWorkspace(next: Surface) {
    if (!token) { setError("برای ورود به محیط عملیاتی ابتدا احراز هویت کنید."); return; }
    setError("");
    setSurface(next);
    window.history.replaceState(null, "", "/app");
  }
  function signIn() {
    setError("");
    if (token) { setSurface(null); window.history.replaceState(null, "", "/app"); return; }
    void beginSignIn().catch((e: unknown) => setError(e instanceof Error ? e.message : "ورود امکان‌پذیر نیست."));
  }
  async function logout() {
    await localSignOut();
    setToken(null); setSurface(null); setError("");
    window.history.replaceState(null, "", "/");
  }

  if (loading) return <div className="auth-state" role="status">در حال تکمیل ورود امن…</div>;
  if (token && surface) return <Workspace key={surface} token={token} surface={surface}
    choose={s => { setSurface(s); if (!s) window.history.replaceState(null, "", "/"); }} logout={() => void logout()} />;
  if (token) return <div className="choose-surface">
    <header><Brand /><Button outline onClick={() => void logout()}>خروج محلی</Button></header>
    <h1>انتخاب محیط بادبان</h1><p>فقط اطلاعاتی نمایش داده می‌شود که بک‌اند به حساب شما اجازه داده باشد.</p>
    <div className="audience-grid">{sections.map(s => <button className="audience-card" key={s.id}
      type="button" onClick={() => openWorkspace(s.id)}><span className="audience-icon">{s.symbol}</span>
      <strong>{s.name}</strong><small>{s.description}</small></button>)}</div>
  </div>;
  return <><Landing signIn={signIn} openWorkspace={openWorkspace}/>{error &&
    <div className="floating-error" role="alert">{error}<button type="button" onClick={() => setError("")}>بستن</button></div>}</>;
}

createRoot(document.getElementById("root")!).render(<App />);
