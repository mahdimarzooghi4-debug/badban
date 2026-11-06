import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { beginSignIn, completeSignIn, localSignOut } from "./auth";
import { client, type AdminWorkspace, type Service, type ServiceCode } from "./api";
import { ApplicantRequests } from "./applicant-requests";
import { ApplicantAccount } from "./applicant-profile";
import { validateApplicantRequest } from "./applicant-requests-data";
import { loadApplicantFinancialCase } from "./applicant-financial-data";
import { ApplicantFinancialCase } from "./applicant-financial";
import { activeCatalogueServices } from "./applicant-services";
import "./styles.css";
import "./operational-details.css";
import { AdminServiceQueue } from "./operational-details";
import { AdminGovernance } from "./operational-governance";
import { AdminDirectory } from "./admin-directory";
import { InstitutionWorkspace, LenderWorkspace } from "./paged-workspaces";

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
  return <span className={"brand" + (light ? " brand--light" : "")}>
    <img className="brand-logo" src="/assets/badban-logo.png"
      alt="بادبان — سرمایه، اعتبار، توانمندسازی" width="180" height="70" />
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
  const [saved, setSaved] = useState<{ scope: string; owner: string; result: LoadState<T> }>({
    scope, owner: token, result: { kind: "loading" },
  });
  useEffect(() => {
    let active = true;
    setSaved({ scope, owner: token, result: { kind: "loading" } });
    loader(token).then(data => { if (active) setSaved({ scope, owner: token, result: { kind: "ready", data } }); })
      .catch((e: unknown) => { if (active) setSaved({ scope, owner: token, result: { kind: "error", message: e instanceof Error ? e.message : "خطا در دریافت اطلاعات" } }); });
    return () => { active = false; };
    // Each authenticated caller and exact scope owns an independent read state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, scope]);
  return saved.scope === scope && saved.owner === token ? saved.result : { kind: "loading" };
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="panel"><h2>{title}</h2>{children}</section>;
}
function Empty({ children }: { children: React.ReactNode }) {
  return <div className="empty">{children}</div>;
}

function Individual({ token, logout }: { token: string; logout: () => void }) {
  const catalogue = useRemote(token, client.catalogue, "individual-service-catalogue");
  const financial = useRemote(token, loadApplicantFinancialCase, "individual-financial");
  const [requestRefreshKey, setRequestRefreshKey] = useState(0);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const pendingKey = useRef<{ code: ServiceCode; key: string } | null>(null);

  async function submit(code: ServiceCode) {
    if (busy) return;
    setBusy(true); setStatus("");
    if (pendingKey.current?.code !== code) pendingKey.current = { code, key: crypto.randomUUID() };
    try {
      validateApplicantRequest(await client.submitRequest(token, code, pendingKey.current.key), code);
      setRequestRefreshKey(current => current + 1);
      setStatus("درخواست ثبت شد؛ وضعیت: دریافت‌شده. این به معنی تأیید یا پرداخت نیست.");
      pendingKey.current = null;
    } catch (error) {
      setStatus(error instanceof Error ? error.message + " — برای تلاش دوباره همین درخواست حفظ می‌شود." : "خطا در ثبت");
    } finally { setBusy(false); }
  }

  const [tab, setTab] = useState<"home" | "financial" | "services" | "requests" | "account">("home");
  const tabs = [
    { id: "home", name: "خانه", icon: "/assets/figma/applicant-home.svg" },
    { id: "financial", name: "مالی", icon: "/assets/figma/applicant-wallet.svg" },
    { id: "services", name: "خدمات", icon: "/assets/figma/applicant-services.svg" },
    { id: "requests", name: "درخواست‌ها", icon: "/assets/figma/applicant-requests.svg" },
    { id: "account", name: "حساب", icon: "/assets/figma/applicant-account.svg" },
  ] as const;

  const renderCatalogue = (data: { items: Service[] }, requestable: boolean) => {
    const offered = activeCatalogueServices(data.items);
    if (!offered.length) return <Empty>در حال حاضر خدمت فعالی برای ثبت درخواست موجود نیست.</Empty>;
    return <div className="service-grid">{offered.map(service => {
      const visual = services.find(s => s.code === service.service_code);
      if (!visual) return null;
      const content = <><span className="service-icon">{visual.symbol}</span>
        <h3>{service.display_name}</h3><p>{service.description}</p></>;
      return requestable
        ? <article className="service-card" key={service.service_code}>{content}
            <Button onClick={() => void submit(service.service_code)} disabled={busy}>ثبت درخواست</Button>
          </article>
        : <button type="button" className="service-card" key={service.service_code}
            onClick={() => setTab("services")}>{content}
            <span className="service-more">مشاهده خدمات ‹</span>
          </button>;
    })}</div>;
  };

  return <div className="workspace-body individual-screen">
    {tab === "home" && <>
      <div className="welcome"><h2>پرونده مالی شما، شفاف و یکپارچه</h2>
        <p>خدمات، سوابق درخواست و پرونده مالی در یک نگاه</p>
        <button className="welcome-link" onClick={() => setTab("financial")} type="button">مشاهده پرونده مالی</button>
      </div>
      <Panel title="خدمات بادبان"><Remote state={catalogue}
        render={data => renderCatalogue(data, false)} /></Panel>
      <Panel title="پرونده مالی من"><button className="finance-shortcut" type="button" onClick={() => setTab("financial")}>
        <span className="shortcut-icon">▣</span><span><strong>مشاهده سوابق و وضعیت مالی</strong>
          <small>اطلاعات دریافت‌شده از بک‌اند بادبان</small></span><span aria-hidden="true">‹</span>
      </button></Panel>
      <Panel title="آخرین درخواست‌ها"><ApplicantRequests token={token} refreshKey={requestRefreshKey} compact /></Panel>
    </>}

    {tab === "services" && <Panel title="خدمات بادبان">
      <Remote state={catalogue} render={data => renderCatalogue(data, true)} />
      {status && <p className="notice" role="status">{status}</p>}
      <p className="notice">درخواست فقط با وضعیت «دریافت‌شده» ثبت می‌شود؛ هیچ تأیید، ضمانت یا پرداختی ایجاد نمی‌کند.</p>
    </Panel>}

    {tab === "requests" && <Panel title="درخواست‌های من">
      <ApplicantRequests token={token} refreshKey={requestRefreshKey} />
    </Panel>}

    {tab === "financial" && <section className="applicant-financial-container">
      <Remote state={financial} render={data => <ApplicantFinancialCase data={data} />} />
    </section>}

    {tab === "account" && <Panel title="حساب من">
      <ApplicantAccount token={token} onFinancialCase={() => setTab("financial")} onLogout={logout} />
      <p className="notice">خروج از حساب در ناوبری، فقط نشست محلی را پاک می‌کند و خروج از ارائه‌دهنده هویت نیست.</p>
    </Panel>}

    <nav className="individual-tabs" aria-label="تب‌های اپلیکیشن افراد">
      {tabs.map(t => <button type="button" key={t.id}
        aria-current={tab === t.id ? "page" : undefined}
        className={"individual-tab" + (tab === t.id ? " individual-tab--selected" : "")}
        onClick={() => { setTab(t.id); setStatus(""); }}>
        <span aria-hidden="true" className="individual-tab-glyph"
          style={{ maskImage: `url(${t.icon})`, WebkitMaskImage: `url(${t.icon})` }}/><strong>{t.name}</strong>
      </button>)}
    </nav>
  </div>;
}

function Institution({ token }: { token: string }) {
  return <InstitutionWorkspace token={token} />;
}

function Lender({ token }: { token: string }) {
  return <LenderWorkspace token={token} />;
}

function Admin({ token }: { token: string }) {
  const data = useRemote(token, client.workspaces, "admin-workspaces");
  const me = useRemote(token, client.me, "admin-current-identity");
  return <div className="workspace-body"><Panel title="حوزه‌های مدیریتی مجاز">
    <Remote state={data} render={d => d.items.length ? <div className="selector-cards">
      {d.items.map((w: AdminWorkspace, i: number) =>
        <div className="selector" key={w.workspace_code + i}>
          <strong>{w.workspace_code}</strong><small>{w.capabilities.join(" · ") || "بدون عملیات مجاز"}</small>
        </div>)}</div> : <Empty>هیچ حوزه مدیریتی فعالی برای این حساب ثبت نشده است.</Empty>} />
  </Panel><AdminServiceQueue token={token} workspaces={data.kind === "ready" ? data.data.items : []} /><AdminGovernance token={token} workspaces={data.kind === "ready" ? data.data.items : []} currentIdentityId={me.kind === "ready" ? me.data.identity_id : null} /><AdminDirectory token={token} workspaces={data.kind === "ready" ? data.data.items : []} /><div className="notice">دستورهای دسترسی فقط با مجوز راهبری بک‌اند اجرا می‌شوند. تأیید درخواست باید توسط هویتی غیر از درخواست‌کننده انجام شود. هیچ عملیات مالی در این صفحه وجود ندارد.</div></div>;
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
      {surface === "individual" ? <Individual token={token} logout={logout}/> : surface === "institution" ?
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
