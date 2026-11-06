import { useState } from "react";
import { previewWorkspaces } from "./preview-data";
import type { Surface } from "./workspace-access";
import "./preview-workspaces.css";

interface PreviewWorkspaceProps {
  surface: Surface;
  onBack: () => void;
  onSelectSurface: (surface: Surface) => void;
}

function PreviewBrand() {
  return <div className="preview-brand-box">
    <img src="/assets/badban-logo.png" alt="بادبان" width="160" height="62" />
  </div>;
}

export function PreviewWorkspace({ surface, onBack, onSelectSurface }: PreviewWorkspaceProps) {
  const [pageId, setPageId] = useState("dashboard");
  const workspace = previewWorkspaces[surface];
  const page = workspace.pages[pageId] ?? workspace.pages.dashboard;

  return <div className="preview-shell" dir="rtl">
    <header className="preview-topbar">
      <div className="preview-topbar-brand">
        <PreviewBrand />
        <span>محیط‌های بادبان</span>
      </div>
      <nav className="preview-role-switcher" aria-label="تغییر محیط نمایشی">
        {(Object.keys(previewWorkspaces) as Surface[]).map(id => {
          const item = previewWorkspaces[id];
          return <button key={id} type="button"
            className={id === surface ? "preview-role-button preview-role-button--active" : "preview-role-button"}
            aria-current={id === surface ? "page" : undefined}
            onClick={() => onSelectSurface(id)}>
            <span aria-hidden="true">{item.symbol}</span>{item.shortTitle}
          </button>;
        })}
      </nav>
      <button className="preview-home-button" type="button" onClick={onBack}>بازگشت به صفحه اصلی</button>
    </header>

    <aside className="preview-sidebar">
      <div className="preview-sidebar-title">
        <span className="preview-sidebar-icon" aria-hidden="true">{workspace.symbol}</span>
        <div><strong>{workspace.title}</strong><small>محیط نمایشی</small></div>
      </div>
      <nav aria-label={"منوی " + workspace.title}>
        {workspace.menu.map(item =>
          <button key={item.id} type="button"
            className={item.id === pageId ? "preview-nav-item preview-nav-item--active" : "preview-nav-item"}
            aria-current={item.id === pageId ? "page" : undefined}
            onClick={() => setPageId(item.id)}>
            <span aria-hidden="true">◈</span>{item.label}
          </button>)}
      </nav>
      <div className="preview-sidebar-foot">
        <span>حالت فقط مشاهده</span>
        <small>بدون ورود و بدون اتصال عملیاتی</small>
      </div>
    </aside>

    <main className="preview-main">
      <div className="preview-breadcrumb">بادبان / پیش‌نمایش / {workspace.title}</div>
      <div className="preview-page-heading">
        <div><h1>{page.title}</h1><p>{page.description}</p></div>
        <span className="preview-data-badge">داده نمایشی</span>
      </div>

      {page.metrics && <section className="preview-metrics" aria-label="شاخص‌های نمایشی">
        {page.metrics.map(metric =>
          <article className="preview-metric" key={metric.label}>
            <span>{metric.label}</span><strong>{metric.value}</strong><small>{metric.detail}</small>
          </article>)}
      </section>}

      <div className="preview-sections">
        {page.sections.map(section =>
          <section className="preview-panel" key={section.title}>
            <div className="preview-panel-heading">
              <h2>{section.title}</h2>
              <span>نمونه</span>
            </div>
            {section.description && <p className="preview-panel-description">{section.description}</p>}
            {section.columns && section.rows && <div className="preview-table-wrap">
              <table className="preview-table">
                <thead><tr>{section.columns.map(column => <th key={column}>{column}</th>)}</tr></thead>
                <tbody>{section.rows.map((row, index) =>
                  <tr key={index}>{row.map((cell, cellIndex) =>
                    <td key={cellIndex}>{cell}</td>)}</tr>)}</tbody>
              </table>
            </div>}
            {section.items && <div className="preview-item-grid">
              {section.items.map(item =>
                <article className="preview-item" key={item.title}>
                  <strong>{item.title}</strong><p>{item.description}</p>
                  {item.meta && <small>{item.meta}</small>}
                </article>)}
            </div>}
            {section.emptyText && <p className="preview-empty">{section.emptyText}</p>}
          </section>)}
      </div>

      {page.note && <div className="preview-note" role="note">{page.note}</div>}
      <div className="preview-readonly-banner">
        <strong>نسخه نمایشی — فقط مشاهده</strong>
        <span>تمام اطلاعات این صفحه نمونه و غیرواقعی است. هیچ درخواست، تغییر دسترسی، محاسبه مالی یا تراکنشی انجام نمی‌شود.</span>
      </div>
    </main>
  </div>;
}
