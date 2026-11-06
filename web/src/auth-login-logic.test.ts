import { describe, expect, it } from "vitest";
import {
  applyOtpInput,
  clearOtpInput,
  normalizeDigits,
  normalizePhoneInput,
} from "./auth-login-logic";

describe("Badban phone and OTP input helpers", () => {
  it("normalizes Persian and Arabic numerals to ASCII digits", () => {
    expect(normalizeDigits("۰۹۱۲٣٤")).toBe("091234");
  });

  it("normalizes phone input without assuming a country-specific number", () => {
    expect(normalizePhoneInput("+۹۸ (۹۱۲) ۱۲۳-۴۵۶۷")).toBe("+989121234567");
    expect(normalizePhoneInput("۰۹۱۲ ۱۲۳ ۴۵۶۷")).toBe("09121234567");
  });

  it("distributes a pasted four-digit code across the four cells", () => {
    expect(applyOtpInput(["", "", "", ""], 0, "۱۲۳۴")).toEqual(["1", "2", "3", "4"]);
  });

  it("fills from the focused cell and ignores non-digits", () => {
    expect(applyOtpInput(["1", "2", "", ""], 2, "۹x۸")).toEqual(["1", "2", "9", "8"]);
  });

  it("does not write beyond the fourth cell", () => {
    expect(applyOtpInput(["", "", "", ""], 2, "123456")).toEqual(["", "", "1", "2"]);
  });

  it("clears the current cell or moves back to clear the previous cell", () => {
    expect(clearOtpInput(["1", "2", "3", "4"], 2)).toEqual(["1", "2", "", "4"]);
    expect(clearOtpInput(["1", "2", "", "4"], 2)).toEqual(["1", "", "", "4"]);
  });

  it("does not mutate the supplied digit array", () => {
    const original = ["1", "", "", ""];
    applyOtpInput(original, 1, "2");
    expect(original).toEqual(["1", "", "", ""]);
  });
});
