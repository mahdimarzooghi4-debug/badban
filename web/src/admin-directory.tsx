import { useEffect, useState, type ReactNode } from "react";
import { api, type AdminWorkspace } from "./api";
import {
  adminDirectoryPath,
  verifiedHumanIdentityPage,
  verifiedLegalEntityPage,
  verifiedProgramPage,
  type DirectoryPage,
  type HumanIdentity,
  type LegalEntityReference,
  type ProgramReference,
} from "./admin-directory-data";
import "./admin-directory.css";

type Resource<T> =
  | { scope: string; owner: string; status: "loading" }
  | { scope: string; owner: string; status: "ready"; data: T }
  | { scope: string; owner: string; status: "error"; message: string };

function useDirectory<T>(
  scope: string,
  token: string,
  load: () => Promise<T>,
): Resource<T> {
  const [saved, setSaved] = useState<Resource<T>>({
    scope,
    owner: token,
    status: "loading",
  });
  useEffect(() => {
    let active = true;
    setSaved({ scope, owner: token, status: "loading" });
    Promise.resolve()
      .then(load)
      .then((data) => {
        if (active) setSaved({ scope, owner: token, status: "ready", data });
      })
      .catch((error: unknown) => {
        if (active) {
          setSaved({
            scope,
            owner: token,
            status: "error",
            message: error instanceof Error ? error.message : "دریافت دایرکتوری ممکن نشد.",
          });
        }
      });
    return () => {
      active = false;
    };
    // Scope and authenticated owner define the request identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, token]);
  return saved.scope === scope && saved.owner === token
    ? saved
    : { scope, owner: token, status: "loading" };
}

function Feedback<T>({
  state,
  children,
}: {
  state: Resource<T>;
  children: (data: T) => ReactNode;
}) {
  if (state.status === "loading") {
    return <p className="directory-feedback" role="status">در حال دریافت داده‌های مجاز…</p>;
  }
  if (state.status === "error") {
    return <p className="directory-feedback directory-feedback--error" role="alert">{state.message}</p>;
  }
  return <>{children(state.data)}</>;
}

function shortId(value: string): string {
  return value.slice(0, 8) + "…" + value.slice(-4);
}
function date(value: string): string {
  return new Date(value).toLocaleDateString("fa-IR");
}
function pageControls<T>(
  data: DirectoryPage<T>,
  offset: number,
  setOffset: (value: number) => void,
): ReactNode {
  return (
    <div className="directory-pagination">
      <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 25))}>
        صفحه قبل
      </button>
      <span>صفحه {(offset / 25 + 1).toLocaleString("fa-IR")}</span>
      <button
        type="button"
        disabled={data.items.length < 25}
        onClick={() => setOffset(offset + 25)}
      >
        صفحه بعد
      </button>
    </div>
  );
}

function HumanIdentityList({ token }: { token: string }) {
  const [offset, setOffset] = useState(0);
  const state = useDirectory("identities:" + offset, token, () =>
    api<unknown>(adminDirectoryPath("identities", 25, offset), token)
      .then((raw) => verifiedHumanIdentityPage(raw, 25, offset)),
  );
  return (
    <section className="directory-panel" id="admin-people-directory">
      <div className="directory-heading">
        <div><small>مدیریت دسترسی · فقط هویت‌های انسانی</small><h3>هویت‌های انسانی</h3></div>
        <span>شناسه مرجع، نوع حساب و وضعیت</span>
      </div>
      <Feedback state={state}>
        {(page) => page.items.length ? (
          <div className="directory-list">
            {page.items.map((item: HumanIdentity) => (
              <article className="directory-row" key={item.identity_id}>
                <div><strong>{shortId(item.identity_id)}</strong><small>شناسه هویت</small></div>
                <div><strong>{item.identity_type}</strong><small>{item.status === "ACTIVE" ? "فعال" : item.status}</small></div>
                <time dateTime={item.created_at}>{date(item.created_at)}</time>
              </article>
            ))}
          </div>
        ) : <p className="directory-empty">هویت انسانی در این صفحه وجود ندارد.</p>}
      </Feedback>
      <Feedback state={state}>
        {(page) => pageControls(page, offset, setOffset)}
      </Feedback>
      <p className="directory-note">
        این فهرست حساب‌های انسانی مجاز برای راهبری است؛ فهرست ذی‌نفعان یا پرونده افراد نیست.
        شناسه ورود و اطلاعات تماس نمایش داده نمی‌شود.
      </p>
    </section>
  );
}

function LegalEntityList({ token }: { token: string }) {
  const [offset, setOffset] = useState(0);
  const state = useDirectory("legal-entities:" + offset, token, () =>
    api<unknown>(adminDirectoryPath("legal-entities", 25, offset), token)
      .then((raw) => verifiedLegalEntityPage(raw, 25, offset)),
  );
  return (
    <section className="directory-panel" id="admin-legal-entity-directory">
      <div className="directory-heading">
        <div><small>مرجع سازمانی · فقط خواندنی</small><h3>سازمان‌ها و شخصیت‌های حقوقی</h3></div>
        <span>بدون شناسه ثبتی</span>
      </div>
      <Feedback state={state}>
        {(page) => page.items.length ? (
          <div className="directory-list">
            {page.items.map((item: LegalEntityReference) => (
              <article className="directory-row" key={item.legal_entity_id}>
                <div><strong>{item.legal_name}</strong><small>{item.entity_type}</small></div>
                <div><strong>{item.status}</strong><small>نسخه {item.version.toLocaleString("fa-IR")}</small></div>
                <small>{shortId(item.legal_entity_id)}</small>
                <time dateTime={item.created_at}>{date(item.created_at)}</time>
              </article>
            ))}
          </div>
        ) : <p className="directory-empty">سازمانی برای نمایش وجود ندارد.</p>}
      </Feedback>
      <Feedback state={state}>
        {(page) => pageControls(page, offset, setOffset)}
      </Feedback>
      <p className="directory-note">
        شناسه ثبتی، مجوزهای حقوقی، مدارک و اطلاعات مالی در این فهرست ارائه نمی‌شوند.
      </p>
    </section>
  );
}

function ProgramList({ token }: { token: string }) {
  const [offset, setOffset] = useState(0);
  const state = useDirectory("programs:" + offset, token, () =>
    api<unknown>(adminDirectoryPath("programs", 25, offset), token)
      .then((raw) => verifiedProgramPage(raw, 25, offset)),
  );
  return (
    <section className="directory-panel" id="admin-program-directory">
      <div className="directory-heading">
        <div><small>برنامه‌های ثبت‌شده · فقط خواندنی</small><h3>برنامه‌ها</h3></div>
        <span>وضعیت و پیوند شخصیت حقوقی</span>
      </div>
      <Feedback state={state}>
        {(page) => page.items.length ? (
          <div className="directory-list">
            {page.items.map((item: ProgramReference) => (
              <article className="directory-row" key={item.program_id}>
                <div><strong>{item.name}</strong><small>کد: {item.code}</small></div>
                <div><strong>{item.status === "ACTIVE" ? "فعال" : "غیرفعال"}</strong><small>نسخه {item.version.toLocaleString("fa-IR")}</small></div>
                <small>{item.legal_entity_id ? shortId(item.legal_entity_id) : "بدون شخصیت حقوقی ثبت‌شده"}</small>
                <time dateTime={item.created_at}>{date(item.created_at)}</time>
              </article>
            ))}
          </div>
        ) : <p className="directory-empty">برنامه‌ای برای نمایش وجود ندارد.</p>}
      </Feedback>
      <Feedback state={state}>
        {(page) => pageControls(page, offset, setOffset)}
      </Feedback>
      <p className="directory-note">
        این فهرست، اعضا، تعداد ذی‌نفعان، شرایط احراز یا اطلاعات مالی برنامه را نمایش نمی‌دهد.
      </p>
    </section>
  );
}

export function AdminDirectory({
  token,
  workspaces,
}: {
  token: string;
  workspaces: AdminWorkspace[];
}) {
  const allowed = (code: string, capability: string, roles: string[]) =>
    workspaces.some((workspace) =>
      workspace.workspace_code === code &&
      workspace.scope_type === "GLOBAL" &&
      workspace.scope_id === null &&
      workspace.capabilities.includes(capability) &&
      workspace.role_codes.some((role) => roles.includes(role)),
    );
  const identities = allowed(
    "ADMIN_HUMAN_IDENTITY_DIRECTORY",
    "READ_HUMAN_IDENTITY_DIRECTORY",
    ["GOVERNANCE_APPROVER"],
  );
  const legalEntities = allowed(
    "ADMIN_LEGAL_ENTITY_DIRECTORY",
    "READ_LEGAL_ENTITY_DIRECTORY",
    ["GOVERNANCE_APPROVER", "LEGAL_COMPLIANCE", "AUDITOR"],
  );
  const programs = allowed(
    "ADMIN_PROGRAM_DIRECTORY",
    "READ_PROGRAM_DIRECTORY",
    ["GOVERNANCE_APPROVER", "AUDITOR", "OPERATIONS"],
  );
  if (!identities && !legalEntities && !programs) return null;
  return (
    <section className="directory-workspace" aria-label="دایرکتوری‌های مدیریتی">
      <div className="directory-intro">
        <h2>دایرکتوری‌های مرجع</h2>
        <p>
          اطلاعات واقعی و صفحه‌بندی‌شده بر اساس نقش فعال حساب. هر API مجوز را مستقل کنترل می‌کند.
          اطلاعات ذی‌نفعان فقط در محدوده برنامه یا خدمت مجاز قابل مشاهده است.
        </p>
      </div>
      {identities && <HumanIdentityList token={token} />}
      {legalEntities && <LegalEntityList token={token} />}
      {programs && <ProgramList token={token} />}
    </section>
  );
}
