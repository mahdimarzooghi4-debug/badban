import { describe, expect, it } from "vitest";
import { resolvePublicOidcConfig } from "./auth-config";

describe("public OIDC runtime configuration", () => {
  it("prefers the runtime issuer/client over public Vite fallback", () => {
    expect(resolvePublicOidcConfig(
      { authority: "https://issuer.example/realms/badban", clientId: "stage-web" },
      "https://wrong.example", "fallback",
    )).toEqual({ authority: "https://issuer.example/realms/badban", clientId: "stage-web" });
  });
  it("supports localhost only in the development fallback", () => {
    expect(resolvePublicOidcConfig(
      undefined, "http://localhost:8080/realms/badban", "badban-web",
    )?.clientId).toBe("badban-web");
  });
  it("fails closed on invalid or unsafe runtime issuer and client metadata", () => {
    for (const value of [
      {}, 4,
      { authority: "http://untrusted.example", clientId: "badban-web" },
      { authority: "https://user:password@issuer.example", clientId: "badban-web" },
      { authority: "https://issuer.example#fragment", clientId: "badban-web" },
      { authority: "https://issuer.example", clientId: "" },
      { authority: "javascript:alert(1)", clientId: "badban-web" },
    ]) {
      expect(resolvePublicOidcConfig(value, "https://safe.example", "fallback")).toBeNull();
    }
  });
  it("does not invent identity configuration", () => {
    expect(resolvePublicOidcConfig(undefined, undefined, undefined)).toBeNull();
  });
});
