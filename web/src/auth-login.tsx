import {
  useRef,
  useState,
  type ClipboardEvent,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import {
  applyOtpInput,
  clearOtpInput,
  normalizeDigits,
  normalizePhoneInput,
} from "./auth-login-logic";
import "./auth-login.css";

type AuthLoginPageProps = {
  onBack: () => void;
  onExistingSignIn: () => void;
  oidcConfigured: boolean;
  previewOtp?: boolean;
  error?: string;
  onDismissError?: () => void;
};

type OtpCodeInputProps = {
  digits: string[];
  onChange: (next: string[]) => void;
};

function OtpCodeInput({ digits, onChange }: OtpCodeInputProps) {
  const refs = useRef<Array<HTMLInputElement | null>>([]);

  function focusAfter(index: number, count: number, next: string[]) {
    const nextEmpty = next.findIndex((digit, position) => position > index && !digit);
    const target = nextEmpty >= 0 ? nextEmpty : Math.min(3, index + Math.max(count, 1) - 1);
    refs.current[target]?.focus();
  }

  function changeDigit(index: number, raw: string) {
    const normalized = normalizeDigits(raw).replace(/\D/g, "");
    const next = applyOtpInput(digits, index, normalized);
    onChange(next);
    if (normalized) focusAfter(index, normalized.length, next);
  }

  function pasteDigits(index: number, event: ClipboardEvent<HTMLInputElement>) {
    const pasted = normalizeDigits(event.clipboardData.getData("text")).replace(/\D/g, "");
    if (!pasted) return;
    event.preventDefault();
    const next = applyOtpInput(digits, index, pasted);
    onChange(next);
    focusAfter(index, pasted.length, next);
  }

  function handleKeyDown(index: number, event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Backspace") {
      event.preventDefault();
      const wasEmpty = !digits[index];
      onChange(clearOtpInput(digits, index));
      if (wasEmpty && index > 0) refs.current[index - 1]?.focus();
    } else if (event.key === "ArrowLeft" && index > 0) {
      event.preventDefault();
      refs.current[index - 1]?.focus();
    } else if (event.key === "ArrowRight" && index < 3) {
      event.preventDefault();
      refs.current[index + 1]?.focus();
    }
  }

  return <div className="auth-login__otp-row" dir="ltr" role="group" aria-label="رمز یک‌بارمصرف چهاررقمی">
    {[0, 1, 2, 3].map(index => (
      <input
        key={index}
        ref={element => { refs.current[index] = element; }}
        className="auth-login__otp-digit"
        type="text"
        inputMode="numeric"
        pattern="[0-9]*"
        maxLength={4}
        autoComplete={index === 0 ? "one-time-code" : "off"}
        aria-label={"رقم " + (index + 1) + " از ۴"}
        value={digits[index] ?? ""}
        onChange={event => changeDigit(index, event.currentTarget.value)}
        onPaste={event => pasteDigits(index, event)}
        onKeyDown={event => handleKeyDown(index, event)}
        onFocus={event => event.currentTarget.select()}
      />
    ))}
  </div>;
}

export function AuthLoginPage({
  onBack,
  onExistingSignIn,
  oidcConfigured,
  previewOtp = false,
  error = "",
  onDismissError,
}: AuthLoginPageProps) {
  const [step, setStep] = useState<"phone" | "code">(previewOtp ? "code" : "phone");
  const [phone, setPhone] = useState("");
  const [digits, setDigits] = useState(["", "", "", ""]);
  const [notice, setNotice] = useState(
    previewOtp ? "پیش‌نمایش رابط کاربری است؛ هیچ رمز یک‌بارمصرفی ارسال نشده است." : "",
  );

  function requestCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!normalizePhoneInput(phone).replace(/\D/g, "")) {
      setNotice("شماره موبایل را وارد کنید.");
      return;
    }
    setNotice("سرویس ارسال رمز یک‌بارمصرف هنوز به بادبان متصل نشده است. هیچ کدی ارسال نشده است.");
  }

  function previewCodeStep() {
    setDigits(["", "", "", ""]);
    setNotice("پیش‌نمایش رابط کاربری است؛ هیچ رمز یک‌بارمصرفی ارسال نشده است.");
    setStep("code");
  }

  function backToPhone() {
    setDigits(["", "", "", ""]);
    setNotice("");
    setStep("phone");
  }

  function submitPreviewCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice("تأیید کد تا اتصال سرویس واقعی احراز هویت فعال نمی‌شود.");
  }

  return <main className="auth-login" dir="rtl">
    <header className="auth-login__header">
      <span className="auth-login__header-label">درگاه ورود یکپارچه</span>
      <div className="auth-login__logo-box">
        <img src="/assets/badban-logo.png" alt="بادبان — سرمایه، اعتبار، توانمندسازی"
          width="160" height="60" />
      </div>
    </header>

    <div className="auth-login__shell">
      <section className="auth-login__brand-panel" aria-label="معرفی بادبان">
        <div className="auth-login__brand-copy">
          <span className="auth-login__eyebrow">بادبان / درگاه یکپارچه</span>
          <h1>یک ورود، برای دسترسی به بادبان</h1>
          <p>با یک ورود امن، به فضای اختصاصی خود در اپلیکیشن و پنل‌های بادبان دسترسی پیدا کنید.</p>
          <ul>
            <li><span aria-hidden="true">✓</span>یک حساب برای دسترسی به خدمات بادبان</li>
            <li><span aria-hidden="true">✓</span>دسترسی متناسب با نقش و مجوز شما</li>
            <li><span aria-hidden="true">✓</span>ورود با رمز یک‌بارمصرف</li>
          </ul>
        </div>
        <div className="auth-login__shield" aria-hidden="true">
          <svg viewBox="0 0 48 48" role="presentation">
            <path d="M24 4 40 11v12c0 10-6.5 17.5-16 22C14.5 40.5 8 33 8 23V11L24 4Z" />
            <path d="m17 24 5 5 10-11" />
          </svg>
        </div>
      </section>

      <section className="auth-login__form-panel">
        <div className="auth-login__form-content">
          {step === "phone" ? <>
            <span className="auth-login__step">مرحله ۱ / ورود</span>
            <h2>ورود به بادبان</h2>
            <p className="auth-login__description">برای ادامه، شماره موبایل خود را وارد کنید.</p>
            <form onSubmit={requestCode}>
              <label className="auth-login__field-label" htmlFor="badban-mobile">شماره موبایل</label>
              <input
                id="badban-mobile"
                className="auth-login__phone-input"
                type="tel"
                inputMode="tel"
                autoComplete="tel"
                dir="ltr"
                value={phone}
                onChange={event => setPhone(normalizePhoneInput(event.currentTarget.value))}
                placeholder="شماره موبایل را وارد کنید"
                required
              />
              <p className="auth-login__helper">پس از اتصال سرویس احراز هویت، کد ورود برای شما ارسال می‌شود.</p>
              <button className="auth-login__primary" type="submit">دریافت کد تأیید</button>
            </form>
            {oidcConfigured && <button className="auth-login__secondary" type="button" onClick={onExistingSignIn}>
              ورود از طریق درگاه هویت فعلی
            </button>}
            {import.meta.env.DEV && <button className="auth-login__preview-link" type="button" onClick={previewCodeStep}>
              پیش‌نمایش مرحله تأیید کد
            </button>}
          </> : <>
            <span className="auth-login__step">مرحله ۲ / تأیید شماره</span>
            <h2>تأیید شماره موبایل</h2>
            <p className="auth-login__description">رمز یک‌بارمصرف ارسال‌شده را وارد کنید.</p>
            <form onSubmit={submitPreviewCode}>
              <OtpCodeInput digits={digits} onChange={setDigits} />
              <div className="auth-login__resend">
                <span>کد را دریافت نکردید؟</span>
                <button type="button" disabled>ارسال مجدد</button>
              </div>
              <button className="auth-login__edit-phone" type="button" onClick={backToPhone}>
                ویرایش شماره موبایل
              </button>
              <button className="auth-login__primary" type="submit" disabled>
                تأیید و ورود
              </button>
            </form>
            <p className="auth-login__helper">تأیید کد پس از اتصال سرویس واقعی احراز هویت فعال می‌شود.</p>
          </>}
          {notice && <p className="auth-login__notice" role="status">{notice}</p>}
          {error && <div className="auth-login__error" role="alert">
            <span>{error}</span>
            {onDismissError && <button type="button" onClick={onDismissError}>بستن</button>}
          </div>}
          <p className="auth-login__security">
            برای حفظ امنیت حساب، رمز یک‌بارمصرف را در اختیار دیگران قرار ندهید.
          </p>
          <button className="auth-login__back" type="button" onClick={onBack}>بازگشت به صفحه اصلی</button>
        </div>
      </section>
    </div>

    <footer className="auth-login__footer">
      دسترسی به محیط‌ها و پنل‌ها بر اساس مجوزهای حساب شما انجام می‌شود.
    </footer>
  </main>;
}
