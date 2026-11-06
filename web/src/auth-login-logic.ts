const persianDigits = "۰۱۲۳۴۵۶۷۸۹";
const arabicDigits = "٠١٢٣٤٥٦٧٨٩";

export function normalizeDigits(value: string): string {
  return value.replace(/[۰-۹٠-٩]/g, digit => {
    const persianIndex = persianDigits.indexOf(digit);
    if (persianIndex >= 0) return String(persianIndex);
    const arabicIndex = arabicDigits.indexOf(digit);
    return arabicIndex >= 0 ? String(arabicIndex) : digit;
  });
}

/** Keep phone formatting out of the UI state while preserving an optional E.164 plus. */
export function normalizePhoneInput(value: string): string {
  const normalized = normalizeDigits(value).trim();
  const prefix = normalized.startsWith("+") ? "+" : "";
  return prefix + normalized.replace(/\D/g, "").slice(0, 15);
}

export function applyOtpInput(
  current: readonly string[],
  index: number,
  raw: string,
): string[] {
  const next = Array.from({ length: 4 }, (_, position) => current[position] ?? "");
  if (index < 0 || index > 3) return next;

  const digits = normalizeDigits(raw).replace(/\D/g, "").slice(0, 4 - index);
  if (!digits) {
    next[index] = "";
    return next;
  }

  for (let offset = 0; offset < digits.length; offset += 1) {
    next[index + offset] = digits[offset] ?? "";
  }
  return next;
}

/** Backspace clears the current cell, or the previous cell when the current one is empty. */
export function clearOtpInput(current: readonly string[], index: number): string[] {
  const next = Array.from({ length: 4 }, (_, position) => current[position] ?? "");
  if (index < 0 || index > 3) return next;
  if (next[index]) next[index] = "";
  else if (index > 0) next[index - 1] = "";
  return next;
}
