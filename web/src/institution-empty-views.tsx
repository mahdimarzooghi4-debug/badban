import "./institution-empty-views.css";

function InstitutionPageStatus() {
  return <section className="institution-page-status" aria-label="وضعیت اتصال منبع داده">
    <div className="institution-page-status__identity">
      <strong>پنل سازمان حمایتگر</strong>
      <span>اطلاعات در محدوده برنامه‌های مجاز سازمان</span>
    </div>
    <span className="institution-page-status__badge">منبع داده مالی متصل نیست</span>
  </section>;
}

export function InstitutionHistoryView() {
  return <div className="workspace-body institution-empty-pages" aria-label="سوابق مالی سازمان">
    <InstitutionPageStatus />
    <section className="institution-empty-panel">
      <header className="institution-empty-panel__heading">
        <img src="/assets/figma/institution-history.svg" width="25" height="25" alt="" />
        <div>
          <h2>گردش تأمین سرمایه نقدی</h2>
          <p>وضعیت درخواست تأمین وجه و پرداخت واقعی یکسان نیستند.</p>
        </div>
        <span className="institution-empty-panel__state">در انتظار اتصال منبع</span>
      </header>
      <div className="institution-empty-state" role="status" aria-live="polite">
        <span className="institution-empty-state__icon" aria-hidden="true">
          <img src="/assets/figma/institution-history.svg" width="25" height="25" alt="" />
        </span>
        <h3>هنوز سابقه مالی برای نمایش وجود ندارد</h3>
        <p>
          این صفحه فعال است، اما منبع معتبر درخواست‌های تأمین وجه و پرداخت سازمانی هنوز
          به آن متصل نشده است. تا آن زمان هیچ نام، مبلغ، شناسه تراکنش یا وضعیت پرداختی نمایش داده نمی‌شود.
        </p>
        <span className="institution-empty-state__hint">بدون اطلاعات نمونه یا تراکنش ساختگی</span>
      </div>
    </section>
    <aside className="institution-page-note">
      <strong>مرزبندی وضعیت‌های مالی</strong>
      <p>
        درخواست تأمین وجه، پرداخت واقعی و انتساب وجه به فرد، وضعیت‌های مستقل‌اند.
        هرکدام فقط پس از اتصال منبع معتبر و قابل ردیابی نمایش داده خواهند شد.
      </p>
    </aside>
  </div>;
}

const reportIndicators = [
  { title: "افراد منتسب", detail: "تعداد معتبر از منبع برنامه" },
  { title: "سرمایه برنامه", detail: "مبنای مالی و مالکیت" },
  { title: "دارایی‌های منتسب سازمانی", detail: "تفکیک از دارایی شخصی" },
  { title: "ارزش‌گذاری دارایی‌ها", detail: "منبع و زمان ارزش‌گذاری" },
] as const;

export function InstitutionReportsView() {
  return <div className="workspace-body institution-empty-pages" aria-label="گزارش‌های سازمان">
    <InstitutionPageStatus />
    <section className="institution-report-indicators" aria-label="شاخص‌های گزارش">
      {reportIndicators.map(item => <article className="institution-report-indicator" key={item.title}>
        <span>{item.title}</span>
        <strong>داده تجمیعی در دسترس نیست</strong>
        <small>{item.detail}</small>
      </article>)}
    </section>
    <div className="institution-report-grid">
      <section className="institution-empty-panel institution-report-distribution">
        <header className="institution-empty-panel__heading">
          <img src="/assets/figma/institution-chart.svg" width="25" height="25" alt="" />
          <div>
            <h2>ترکیب سرمایه سازمانی</h2>
            <p>نمای تجمیعی فقط با داده مالی و انتساب معتبر ساخته می‌شود.</p>
          </div>
        </header>
        <div className="institution-report-chart-empty" role="status" aria-live="polite">
          <span className="institution-report-chart-empty__icon" aria-hidden="true">
            <img src="/assets/figma/institution-chart.svg" width="25" height="25" alt="" />
          </span>
          <h3>گزارش تجمیعی هنوز آماده نیست</h3>
          <p>
            منبع تجمیعی معتبر برای تعداد افراد، مبالغ و تفکیک مالکیت به این صفحه متصل نشده است.
            بنابراین هیچ عدد، درصد یا نمودار فرضی نمایش داده نمی‌شود.
          </p>
        </div>
      </section>
      <section className="institution-empty-panel institution-report-boundary">
        <header className="institution-empty-panel__heading">
          <img src="/assets/figma/institution-lock.svg" width="26" height="26" alt="" />
          <div><h2>محدوده گزارش</h2><p>مرزهای دسترسی و تفسیر داده</p></div>
        </header>
        <ul>
          <li>فقط برنامه‌های دارای مجوز سازمان</li>
          <li>بدون اطلاعات هویتی حساس</li>
          <li>بدون ادعای بازده یا سود قطعی</li>
          <li>تفکیک اصل سرمایه از حقوق منتفع</li>
        </ul>
      </section>
    </div>
    <aside className="institution-page-note institution-page-note--report">
      <img src="/assets/figma/institution-chart.svg" width="25" height="25" alt="" />
      <div>
        <strong>گزارش رسمی فقط با داده مالی و انتساب معتبر</strong>
        <p>این نسخه هنوز گزارش رسمی یا فایل قابل ارائه به حسابرسی تولید نمی‌کند.</p>
      </div>
    </aside>
  </div>;
}
