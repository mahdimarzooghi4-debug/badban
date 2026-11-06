import { useState } from "react";
import "./preview-desktop-pages.css";

type ListSurface = "institution" | "lender" | "admin";

function ListPageHeader({breadcrumb,title,subtitle,scope,tag}:{
  breadcrumb:string;title:string;subtitle:string;scope:string;tag:string;
}) {
  return <>
    <div className="figma-list-breadcrumb">{breadcrumb}</div>
    <header className="figma-list-heading"><h1>{title}</h1><p>{subtitle}</p></header>
    <div className="figma-list-scope"><strong>{scope}</strong><span>{tag}</span></div>
  </>;
}

type Filter<T extends string> = {id:T; label:string};
function ListFilters<T extends string>({filters,active,onChange}:{
  filters:readonly Filter<T>[];active:T;onChange:(id:T)=>void;
}) {
  return <div className="figma-list-filters" role="group" aria-label="فیلتر نمایشی فهرست">
    {filters.map(x=><button key={x.id} type="button" aria-pressed={active===x.id}
      onClick={()=>onChange(x.id)} className={active===x.id?"figma-list-filter is-active":"figma-list-filter"}>{x.label}</button>)}
  </div>;
}
const people = [
  {name:"مریم احمدی",type:"beneficiary",role:"مددجو",id:"BD-P-۱۰۱",money:"۱۵۰ میلیون ریال",status:"پیش‌نویس"},
  {name:"علی مرادی",type:"employee",role:"کارمند",id:"BD-P-۱۰۲",money:"۱۲۰ میلیون ریال",status:"پیش‌نویس"},
  {name:"سارا محمدی",type:"beneficiary",role:"مددجو",id:"BD-P-۱۰۳",money:"۸۵ میلیون ریال",status:"در انتظار تطبیق"},
  {name:"رضا رضایی",type:"employee",role:"کارمند",id:"BD-P-۱۰۴",money:"۹۰ میلیون ریال",status:"پیش‌نویس"},
] as const;
type OrgFilter="all"|"beneficiary"|"employee";
function InstitutionPeople(){
  const [filter,setFilter]=useState<OrgFilter>("all");
  const visible=people.filter(x=>filter==="all"||x.type===filter);
  return <section className="figma-list-page figma-list-page--institution" data-figma-frame="244:113">
    <ListPageHeader breadcrumb="پنل سازمان / افراد" title="افراد سازمان"
      subtitle="نمای مشترک مددجویان و کارکنان، با مرزبندی اطلاعات هر پرونده"
      scope="سازمان همراهی فردا • پنل سازمانی مستقل" tag="داده نمایشی"/>
    <div className="figma-list-intro"><div className="figma-list-section-icon">
      <img src="/assets/figma/institution-person.svg" alt=""/></div>
      <div><h2>فهرست افراد منتسب به سازمان</h2>
        <p>داده‌های این فهرست نمایشی‌اند؛ عملیات واقعی به مجوز برنامه نیاز دارد.</p></div>
    </div>
    <div className="figma-list-toolbar">
      <ListFilters filters={[{id:"all",label:"همه: ۱۸"},{id:"beneficiary",label:"مددجو: ۱۲"},{id:"employee",label:"کارمند: ۶"}]}
        active={filter} onChange={setFilter}/>
      <div className="figma-list-static-actions" aria-label="عملیات غیرفعال در نسخه نمایشی">
        <span>ورود گروهی افراد</span><span className="figma-list-action-dark">افزودن فرد +</span>
      </div>
    </div>
    <div className="figma-list-records">
      {visible.map(x=><article className="figma-list-record figma-list-record--institution" key={x.id}>
        <strong className="figma-list-name"><img src="/assets/figma/institution-person.svg" alt=""/>{x.name}</strong>
        <span>{x.role}</span><span dir="ltr">{x.id}</span><strong>{x.money}</strong>
        <span className={x.status==="پیش‌نویس"?"figma-list-status figma-list-status--blue":"figma-list-status figma-list-status--pending"}>{x.status}</span>
      </article>)}
    </div>
    <p className="figma-list-footnote">نمایش اشخاص و مبالغ فرضی است. دسترسی هر سازمان فقط به برنامه مجاز خودش محدود است.</p>
  </section>;
}

const guarantees=[
  {id:"GU-۲۰۴",type:"ضمانت خارجی",amount:"۳۰۰ میلیون ریال",balance:"۱۸۰ میلیون ریال",status:"فعال"},
  {id:"GU-۲۰۵",type:"ضمانت خارجی",amount:"۲۵۰ میلیون ریال",balance:"—",status:"در انتظار اطلاعات"},
  {id:"GU-۲۰۶",type:"ضمانت خارجی",amount:"۱۵۰ میلیون ریال",balance:"۹۰ میلیون ریال",status:"فعال"},
  {id:"GU-۲۰۷",type:"ضمانت خارجی",amount:"۸۰ میلیون ریال",balance:"۵۰ میلیون ریال",status:"فعال"},
] as const;
type GuaranteeFilter="all"|"active"|"waiting";
function LenderGuarantees(){
  const [filter,setFilter]=useState<GuaranteeFilter>("all");
  const visible=guarantees.filter(x=>filter==="all"||(filter==="active"?x.status==="فعال":x.status==="در انتظار اطلاعات"));
  return <section className="figma-list-page figma-list-page--lender" data-figma-frame="259:103">
    <ListPageHeader breadcrumb="پنل تأمین‌کننده / ضمانت‌ها" title="ضمانت‌های تأمین‌کننده"
      subtitle="فهرست پرونده‌های ضمانت متعلق به همین تأمین‌کننده، با وضعیت و مبلغ مستقل"
      scope="صندوق تأمین اعتبار نمونه • دسترسی صرفاً به پرونده‌های همین تأمین‌کننده" tag="داده نمایشی"/>
    <div className="figma-list-intro">
      <div className="figma-list-section-icon"><img src="/assets/figma/finance-shield.svg" alt=""/></div>
      <div><h2>فهرست ضمانت‌ها</h2><p>نمایش فقط پرونده‌های مرتبط؛ وضعیت و مبالغ ضمانت از منبع معتبر خوانده می‌شود.</p></div>
    </div>
    <div className="figma-list-toolbar">
      <ListFilters filters={[{id:"all",label:"همه پرونده‌ها"},{id:"active",label:"فعال"},{id:"waiting",label:"در انتظار اطلاعات"}]}
        active={filter} onChange={setFilter}/>
    </div>
    <div className="figma-list-records">
      {visible.map(x=><article key={x.id} className="figma-list-record figma-list-record--lender">
        <strong className="figma-list-name"><img src="/assets/figma/finance-shield.svg" alt=""/>{x.type}</strong>
        <span dir="ltr">{x.id}</span><strong>{x.amount}</strong><strong>{x.balance}</strong>
        <span className={x.status==="فعال"?"figma-list-status figma-list-status--gold":"figma-list-status figma-list-status--blue"}>{x.status}</span>
      </article>)}
    </div>
    <p className="figma-list-footnote">مبالغ ضمانت و مانده وام در این نما صرفاً سناریوی طراحی‌اند؛ هیچ ضمانت یا تعهد واقعی ساخته نمی‌شود.</p>
  </section>;
}

const adminPeople=[
  {id:"BD-P-۱۰۱",name:"فرد نمونه ۱۰۱",group:"برنامه الف",money:"سرمایه ۱۵۰ میلیون",status:"منتسب به برنامه",category:"program"},
  {id:"BD-P-۱۰۲",name:"فرد نمونه ۱۰۲",group:"برنامه ب",money:"سرمایه ۱۲۰ میلیون",status:"منتسب به برنامه",category:"program"},
  {id:"BD-P-۱۰۳",name:"فرد نمونه ۱۰۳",group:"بدون مرجع قطعی",money:"—",status:"نامشخص",category:"unconfirmed"},
] as const;
type AdminFilter="all"|"program"|"unconfirmed";
function AdminPeople(){
  const [filter,setFilter]=useState<AdminFilter>("all");
  const visible=adminPeople.filter(x=>filter==="all"||x.category===filter);
  return <section className="figma-list-page figma-list-page--admin" data-figma-frame="271:122">
    <ListPageHeader breadcrumb="مدیریت مرکزی / افراد" title="مدیریت افراد"
      subtitle="مشاهده و پیگیری پرونده‌های افراد؛ اطلاعات حساس فقط با مجوز و نیاز واقعی"
      scope="دسترسی مدیریتی • داده‌های نمایشی • کنترل‌های حساس تنها با مجوز و تأیید مستقل"
      tag="نمایش طراحی"/>
    <div className="figma-list-intro">
      <div><h2>فهرست افراد و انتساب‌ها</h2><p>انتساب به برنامه، مالکیت سرمایه و وضعیت مالی سه موضوع مستقل هستند.</p></div>
    </div>
    <div className="figma-list-toolbar">
      <ListFilters filters={[{id:"all",label:"همه افراد"},{id:"program",label:"افراد برنامه‌ای"},{id:"unconfirmed",label:"بدون وضعیت تأییدشده"}]}
        active={filter} onChange={setFilter}/>
    </div>
    <div className="figma-list-records">
      {visible.map(x=><article key={x.id} className="figma-list-record figma-list-record--admin">
        <strong>{x.name}</strong><span dir="ltr">{x.id}</span><span>{x.group}</span>
        <strong>{x.money}</strong><span className={x.status==="نامشخص"?"figma-list-status figma-list-status--blue":"figma-list-status figma-list-status--gold"}>{x.status}</span>
      </article>)}
    </div>
    <div className="figma-list-warning">داده‌های هویتی و تماس، صرفاً با قرارداد دسترسی معتبر قابل مشاهده‌اند؛ نام‌ها و ارقام این صفحه نمایشی هستند.</div>
  </section>;
}

export function DesktopInnerPreview({surface,pageId}:{
  surface:ListSurface; pageId:string;
}){
  if(surface==="institution"&&pageId==="people")return <InstitutionPeople/>;
  if(surface==="lender"&&pageId==="guarantees")return <LenderGuarantees/>;
  if(surface==="admin"&&pageId==="people")return <AdminPeople/>;
  return null;
}
