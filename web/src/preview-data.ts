import type { Surface } from "./workspace-access";

export interface PreviewMenuItem {
  id: string;
  label: string;
}
export interface PreviewMetric {
  label: string;
  value: string;
  detail: string;
}
export interface PreviewSection {
  title: string;
  description?: string;
  columns?: readonly string[];
  rows?: readonly (readonly string[])[];
  items?: readonly { title: string; description: string; meta?: string }[];
  emptyText?: string;
}
export interface PreviewPage {
  title: string;
  description: string;
  metrics?: readonly PreviewMetric[];
  sections: readonly PreviewSection[];
  note?: string;
}
export interface PreviewWorkspaceDefinition {
  title: string;
  shortTitle: string;
  description: string;
  symbol: string;
  readOnly: true;
  menu: readonly PreviewMenuItem[];
  pages: Readonly<Record<string, PreviewPage>>;
}

export const previewWorkspaces = {
  individual: {
    title: "افراد و متقاضیان",
    shortTitle: "افراد",
    description: "نمایش محیط فردی، خدمات قابل مشاهده و پرونده درخواست‌ها",
    symbol: "♙",
    readOnly: true,
    menu: [
      { id: "dashboard", label: "داشبورد" },
      { id: "services", label: "خدمات" },
      { id: "requests", label: "درخواست‌ها" },
      { id: "finance", label: "پرونده مالی" },
      { id: "profile", label: "حساب کاربری" },
    ],
    pages: {
      dashboard: {
        title: "داشبورد متقاضی",
        description: "نمای کلی محیط افراد با اطلاعات نمونه و غیرواقعی",
        metrics: [
          { label: "خدمات قابل مشاهده", value: "۳ مورد نمونه", detail: "فهرست نمایشی خدمات" },
          { label: "درخواست‌ها", value: "۲ مورد نمونه", detail: "بدون ثبت در سامانه" },
          { label: "اتصال به API", value: "غیرفعال", detail: "اطلاعات عملیاتی دریافت نمی‌شود" },
        ],
        sections: [
          {
            title: "آخرین درخواست‌ها",
            columns: ["شناسه نمایشی", "خدمت", "وضعیت نمایشی"],
            rows: [
              ["REQ-DEMO-01", "ضمانت وام", "دریافت‌شده — نمونه"],
              ["REQ-DEMO-02", "مستمری ماهانه", "پیش‌نویس نمایشی"],
            ],
          },
          {
            title: "دسترسی سریع",
            items: [
              { title: "خدمات بادبان", description: "مشاهده فهرست خدمات و توضیحات آن‌ها", meta: "فقط مشاهده" },
              { title: "پرونده مالی", description: "نمایش چیدمان بخش مالی بدون موجودی واقعی", meta: "بدون اتصال مالی" },
              { title: "درخواست‌ها", description: "مرور ساختار فهرست درخواست‌ها", meta: "داده نمونه" },
            ],
          },
        ],
      },
      services: {
        title: "خدمات بادبان",
        description: "کارت‌های خدمات برای مشاهده ظاهر و مسیر کاربری — داده نمونه",
        metrics: [{ label: "تعداد خدمات نمایشی", value: "۳", detail: "هیچ درخواستی ثبت نمی‌شود" }],
        sections: [{
          title: "فهرست خدمات",
          items: [
            { title: "ضمانت وام", description: "نمایش اطلاعات خدمت و مسیر بررسی درخواست ضمانت", meta: "فقط مشاهده" },
            { title: "مستمری ماهانه", description: "نمایش اطلاعات خدمت حمایتی دوره‌ای", meta: "فقط مشاهده" },
            { title: "آینده مالی", description: "نمایش اطلاعات خدمت حمایت پس از خروج", meta: "فقط مشاهده" },
          ],
        }],
        note: "دکمه ثبت درخواست در این پیش‌نمایش وجود ندارد و هیچ درخواست واقعی ساخته نمی‌شود.",
      },
      requests: {
        title: "درخواست‌های من",
        description: "ساختار فهرست درخواست‌ها با شناسه‌ها و وضعیت‌های غیرواقعی نمونه",
        sections: [{
          title: "فهرست درخواست‌ها",
          columns: ["شناسه نمایشی", "عنوان", "وضعیت نمایشی", "زمان"],
          rows: [
            ["REQ-DEMO-01", "ضمانت وام", "دریافت‌شده — نمونه", "زمان نمونه"],
            ["REQ-DEMO-02", "مستمری ماهانه", "پیش‌نویس نمایشی", "زمان نمونه"],
          ],
        }],
      },
      finance: {
        title: "پرونده مالی من",
        description: "نمایش چیدمان پرونده مالی بدون اتصال به داده یا حساب واقعی",
        metrics: [
          { label: "موجودی واقعی", value: "نمایش داده نمی‌شود", detail: "هیچ حسابی متصل نیست" },
          { label: "گردش واقعی", value: "نمایش داده نمی‌شود", detail: "هیچ تراکنشی خوانده نمی‌شود" },
        ],
        sections: [{
          title: "ساختار سوابق مالی",
          columns: ["نوع ردیف", "شرح", "مقدار"],
          rows: [
            ["ردیف نمونه", "نمایش جایگاه شرح مالی", "—"],
            ["ردیف نمونه", "نمایش جایگاه وضعیت", "—"],
          ],
        }],
        note: "این صفحه موجودی، بدهی، تراکنش یا تأییدیه بانکی واقعی نشان نمی‌دهد.",
      },
      profile: {
        title: "حساب کاربری",
        description: "پروفایل نمایشی بدون احراز هویت یا اطلاعات شخصی واقعی",
        sections: [{
          title: "اطلاعات نمایشی",
          items: [
            { title: "کاربر نمونه", description: "هویت واقعی به این محیط متصل نیست", meta: "غیرواقعی" },
            { title: "شماره همراه", description: "در این نسخه دریافت یا اعتبارسنجی نمی‌شود", meta: "خالی" },
            { title: "کد ملی", description: "هیچ داده هویتی دریافت نمی‌شود", meta: "خالی" },
          ],
        }],
      },
    },
  },
  institution: {
    title: "سازمان‌های حمایتگر",
    shortTitle: "سازمان‌ها",
    description: "نمایش محیط سازمان، برنامه‌ها، افراد و گزارش‌های سازمانی",
    symbol: "♧",
    readOnly: true,
    menu: [
      { id: "dashboard", label: "داشبورد" },
      { id: "people", label: "افراد" },
      { id: "funding", label: "تأمین سرمایه" },
      { id: "history", label: "سوابق مالی" },
      { id: "reports", label: "گزارش‌ها" },
    ],
    pages: {
      dashboard: {
        title: "داشبورد سازمان",
        description: "نمای کلی سازمان حمایتگر با داده‌های نمونه و غیرواقعی",
        metrics: [
          { label: "برنامه‌ها", value: "۲ مورد نمونه", detail: "صرفاً برای نمایش" },
          { label: "پرونده‌های مرتبط", value: "۶ مورد نمونه", detail: "بدون اطلاعات فردی واقعی" },
          { label: "اتصال مالی", value: "غیرفعال", detail: "هیچ منبع مالی متصل نیست" },
        ],
        sections: [{
          title: "برنامه‌های نمایشی",
          columns: ["شناسه", "عنوان برنامه", "وضعیت"],
          rows: [
            ["PROGRAM-DEMO-01", "برنامه نمونه الف", "نمایشی"],
            ["PROGRAM-DEMO-02", "برنامه نمونه ب", "نمایشی"],
          ],
        }],
      },
      people: {
        title: "افراد",
        description: "نمایش فهرست افراد مرتبط با برنامه — داده ساختگی",
        sections: [{
          title: "فهرست افراد نمونه",
          columns: ["شناسه نمایشی", "عنوان نمایشی", "دسترسی"],
          rows: [
            ["PERSON-DEMO-01", "فرد نمونه ۱", "فقط مشاهده"],
            ["PERSON-DEMO-02", "فرد نمونه ۲", "فقط مشاهده"],
            ["PERSON-DEMO-03", "فرد نمونه ۳", "فقط مشاهده"],
          ],
        }],
        note: "هیچ نام، کد ملی، شماره تماس یا پرونده واقعی در این صفحه وجود ندارد.",
      },
      funding: {
        title: "تأمین سرمایه",
        description: "نمایش ساختار برنامه و منابع سازمانی بدون ثبت یا جابه‌جایی وجه",
        sections: [{
          title: "نمای برنامه‌ها",
          items: [
            { title: "برنامه نمونه الف", description: "نمایش تفکیک برنامه، منبع و نقش سازمان", meta: "مبلغ واقعی: ندارد" },
            { title: "برنامه نمونه ب", description: "نمایش مسیر مشاهده تأمین سرمایه", meta: "بدون عملیات" },
          ],
        }],
        note: "مبالغ و مانده‌ها نمایش داده نمی‌شوند؛ این محیط به بانک یا دفترکل عملیاتی متصل نیست.",
      },
      history: {
        title: "سوابق مالی سازمان",
        description: "چیدمان سوابق دفترکل داخلی — داده نمونه و بدون تأیید انتقال بانکی",
        sections: [{
          title: "ردیف‌های نمایشی",
          columns: ["شناسه", "شرح", "مرجع", "مقدار"],
          rows: [
            ["JRN-DEMO-01", "ردیف دفترکل نمونه", "مرجع نمونه", "—"],
            ["JRN-DEMO-02", "ردیف دفترکل نمونه", "مرجع نمونه", "—"],
          ],
        }],
        note: "ثبت داخلی نمونه به معنی انتقال وجه یا تأیید بانکی نیست.",
      },
      reports: {
        title: "گزارش‌های سازمان",
        description: "نمایش چیدمان گزارش‌های برنامه‌ای بدون داده عملیاتی",
        metrics: [
          { label: "گزارش‌های نمونه", value: "۲", detail: "ساختار نمایشی" },
          { label: "داده واقعی", value: "وجود ندارد", detail: "API متصل نیست" },
        ],
        sections: [{
          title: "گزارش‌های قابل مشاهده",
          items: [
            { title: "گزارش برنامه", description: "نمایش خلاصه و ساختار گزارش برنامه", meta: "نمونه" },
            { title: "گزارش سوابق", description: "نمایش ساختار سوابق مالی سازمان", meta: "نمونه" },
          ],
        }],
      },
    },
  },
  lender: {
    title: "تأمین‌کنندگان تسهیلات",
    shortTitle: "تأمین‌کنندگان",
    description: "نمایش محیط تأمین‌کننده، ضمانت‌ها و سوابق مرتبط",
    symbol: "▣",
    readOnly: true,
    menu: [
      { id: "dashboard", label: "داشبورد" },
      { id: "guarantees", label: "ضمانت‌ها" },
      { id: "facilities", label: "تسهیلات" },
      { id: "history", label: "سوابق" },
      { id: "reports", label: "گزارش‌ها" },
    ],
    pages: {
      dashboard: {
        title: "داشبورد تأمین‌کننده",
        description: "نمای کلی ضمانت‌ها و تسهیلات با داده‌های نمونه",
        metrics: [
          { label: "درخواست ضمانت", value: "۲ مورد نمونه", detail: "وضعیت نمایشی REQUESTED" },
          { label: "تصمیم عملیاتی", value: "وجود ندارد", detail: "هیچ تصمیمی اجرا نمی‌شود" },
          { label: "اتصال به API", value: "غیرفعال", detail: "داده عملیاتی دریافت نمی‌شود" },
        ],
        sections: [{
          title: "درخواست‌های ضمانت نمونه",
          columns: ["شناسه نمایشی", "نوع", "وضعیت"],
          rows: [
            ["GRT-DEMO-01", "درخواست ضمانت", "REQUESTED — نمونه"],
            ["GRT-DEMO-02", "درخواست ضمانت", "REQUESTED — نمونه"],
          ],
        }],
      },
      guarantees: {
        title: "ضمانت‌ها",
        description: "نمایش فهرست درخواست‌های ضمانت — همه ردیف‌ها نمونه و در وضعیت REQUESTED",
        sections: [{
          title: "فهرست ضمانت‌های نمایشی",
          columns: ["شناسه نمایشی", "وضعیت ثبت‌شده در نمونه", "جزئیات"],
          rows: [
            ["GRT-DEMO-01", "REQUESTED", "درخواست نمونه"],
            ["GRT-DEMO-02", "REQUESTED", "درخواست نمونه"],
          ],
        }],
        note: "این صفحه هیچ رزرو، تخصیص پشتوانه، ارزیابی ریسک یا تصمیم ضمانتی اجرا نمی‌کند.",
      },
      facilities: {
        title: "تسهیلات",
        description: "نمایش ساختار محیط تسهیلات بدون اتصال به داده واقعی",
        sections: [{
          title: "فهرست تسهیلات",
          emptyText: "اطلاعات تسهیلات عملیاتی به این پیش‌نمایش متصل نیست؛ این بخش فقط ساختار صفحه را نشان می‌دهد.",
        }],
      },
      history: {
        title: "سوابق",
        description: "نمایش ساختار سوابق تأمین‌کننده با داده غیرواقعی",
        sections: [{
          title: "ردیف‌های نمونه",
          columns: ["شناسه نمایشی", "نوع سابقه", "وضعیت داده"],
          rows: [
            ["HISTORY-DEMO-01", "سابقه نمونه", "غیرعملیاتی"],
            ["HISTORY-DEMO-02", "سابقه نمونه", "غیرعملیاتی"],
          ],
        }],
      },
      reports: {
        title: "گزارش‌ها",
        description: "ساختار گزارش‌های تأمین‌کننده بدون محاسبه یا داده عملیاتی",
        sections: [{
          title: "گزارش‌های قابل مشاهده",
          items: [
            { title: "گزارش ضمانت‌ها", description: "نمایش چیدمان گزارش درخواست‌های ضمانت", meta: "نمونه" },
            { title: "گزارش تسهیلات", description: "نمایش چیدمان گزارش تسهیلات", meta: "بدون داده عملیاتی" },
          ],
        }],
      },
    },
  },
  admin: {
    title: "مدیریت مرکزی",
    shortTitle: "مدیریت مرکزی",
    description: "نمایش محیط مدیریت، راهبری، دسترسی و گزارش‌های کلان",
    symbol: "◈",
    readOnly: true,
    menu: [
      { id: "dashboard", label: "داشبورد" },
      { id: "people", label: "افراد" },
      { id: "organizations", label: "سازمان‌ها و برنامه‌ها" },
      { id: "capital", label: "سرمایه و پشتوانه" },
      { id: "guarantees", label: "ضمانت و تسهیلات" },
      { id: "finance", label: "مالی و تطبیق" },
      { id: "risk", label: "سیاست‌ها و ریسک" },
      { id: "access", label: "دسترسی و راهبری" },
      { id: "reports", label: "گزارش‌ها و حسابرسی" },
    ],
    pages: {
      dashboard: {
        title: "داشبورد مدیریت مرکزی",
        description: "نمای کلی حوزه‌های مدیریتی با داده‌های نمایشی",
        metrics: [
          { label: "حوزه‌های مدیریتی", value: "۳ حوزه نمونه", detail: "کدهای نمایشی" },
          { label: "عملیات فعال", value: "۰", detail: "هیچ فرمانی اجرا نمی‌شود" },
          { label: "اتصال عملیاتی", value: "غیرفعال", detail: "API و داده واقعی متصل نیست" },
        ],
        sections: [{
          title: "حوزه‌های قابل مشاهده",
          columns: ["کد حوزه", "قابلیت نمونه", "حالت"],
          rows: [
            ["ADMIN_SERVICE_OPERATIONS", "مشاهده صف کار", "فقط نمایش"],
            ["ADMIN_ACCESS_GOVERNANCE", "مشاهده راهبری دسترسی", "فقط نمایش"],
            ["ADMIN_BENEFIT_LINEAGE_REVIEW", "مشاهده ردپای مزایا", "فقط نمایش"],
          ],
        }],
      },
      people: {
        title: "افراد",
        description: "نمایش ساختار فهرست افراد بدون اطلاعات هویتی واقعی",
        sections: [{
          title: "فهرست نمونه",
          columns: ["شناسه", "نوع رکورد", "منبع"],
          rows: [
            ["PERSON-DEMO-01", "فرد نمونه", "داده ساختگی"],
            ["PERSON-DEMO-02", "فرد نمونه", "داده ساختگی"],
          ],
        }],
      },
      organizations: {
        title: "سازمان‌ها و برنامه‌ها",
        description: "نمایش ساختار فهرست سازمان‌ها و برنامه‌ها — داده نمونه",
        sections: [{
          title: "سازمان‌ها و برنامه‌های نمایشی",
          columns: ["شناسه", "عنوان", "وضعیت داده"],
          rows: [
            ["ORG-DEMO-01", "سازمان نمونه", "غیرعملیاتی"],
            ["PROGRAM-DEMO-01", "برنامه نمونه", "غیرعملیاتی"],
          ],
        }],
      },
      capital: {
        title: "سرمایه و پشتوانه",
        description: "نمایش ساختار منابع و پشتوانه بدون محاسبه یا جابه‌جایی وجه",
        sections: [{
          title: "نمایش ساختار منابع",
          items: [
            { title: "منبع دارایی نمونه", description: "نمایش تفکیک نوع دارایی و منبع", meta: "بدون مقدار واقعی" },
            { title: "پشتوانه نمونه", description: "نمایش ساختار پشتوانه و مرجع آن", meta: "بدون تخصیص" },
          ],
        }],
        note: "هیچ دارایی، مانده، ظرفیت یا تخصیص واقعی در این پیش‌نمایش وجود ندارد.",
      },
      guarantees: {
        title: "ضمانت و تسهیلات",
        description: "نمایش ساختار پرونده‌های ضمانت و تسهیلات — داده نمونه",
        sections: [{
          title: "پرونده‌های نمایشی",
          columns: ["شناسه", "نوع", "حالت"],
          rows: [
            ["GRT-DEMO-01", "درخواست ضمانت", "REQUESTED — نمونه"],
            ["FACILITY-DEMO-01", "پرونده تسهیلات", "صرفاً نمایشی"],
          ],
        }],
      },
      finance: {
        title: "مالی و تطبیق",
        description: "نمایش چیدمان مالی و تطبیق بدون دفترکل عملیاتی",
        sections: [{
          title: "حوزه‌های مالی",
          items: [
            { title: "دفترکل", description: "ساختار مشاهده ثبت‌های نمونه", meta: "بدون ثبت جدید" },
            { title: "تطبیق", description: "نمایش جایگاه گزارش تطبیق", meta: "بدون محاسبه" },
            { title: "حسابرسی", description: "نمایش جایگاه سوابق قابل حسابرسی", meta: "بدون داده واقعی" },
          ],
        }],
      },
      risk: {
        title: "سیاست‌ها و ریسک",
        description: "نمایش ساختار سیاست‌ها و حوزه ریسک بدون ارزیابی یا تصمیم",
        sections: [{
          title: "حوزه‌های قابل مشاهده",
          items: [
            { title: "نسخه سیاست", description: "نمایش جایگاه شناسه و نسخه سیاست", meta: "بدون تغییر" },
            { title: "ارزیابی ریسک", description: "نمایش ساختار پرونده ارزیابی", meta: "بدون اجرا" },
            { title: "کنترل ظرفیت", description: "نمایش ساختار کنترل‌ها", meta: "بدون محاسبه" },
          ],
        }],
        note: "هیچ امتیاز، آستانه، ارزیابی یا تصمیم ریسکی در این محیط ساخته نمی‌شود.",
      },
      access: {
        title: "دسترسی و راهبری",
        description: "نمایش ساختار نقش‌ها و حوزه‌های دسترسی بدون احراز هویت واقعی",
        sections: [{
          title: "نقش‌های نمایشی",
          columns: ["نقش", "دامنه", "وضعیت"],
          rows: [
            ["نقش نمونه اپراتور", "دامنه نمونه", "غیرعملیاتی"],
            ["نقش نمونه حسابرس", "فقط خواندن", "غیرعملیاتی"],
          ],
        }],
        note: "این صفحه مجوز واقعی صادر، اصلاح یا لغو نمی‌کند.",
      },
      reports: {
        title: "گزارش‌ها و حسابرسی",
        description: "نمایش ساختار گزارش‌های مدیریتی و سوابق حسابرسی",
        sections: [{
          title: "گزارش‌های نمونه",
          items: [
            { title: "گزارش مدیریتی", description: "نمایش ساختار گزارش‌های کلان", meta: "نمونه" },
            { title: "گزارش حسابرسی", description: "نمایش ساختار ردپای رویدادها", meta: "نمونه" },
          ],
        }],
      },
    },
  },
} as const satisfies Record<Surface, PreviewWorkspaceDefinition>;

export function previewPageIds(surface: Surface): string[] {
  return Object.keys(previewWorkspaces[surface].pages);
}
