import { describe, expect, it } from "vitest";
import { previewSurfaceFromLocation, previewSurfaceUrl } from "./preview-routing";
import type { Surface } from "./workspace-access";

const surfaces: Surface[] = ["individual", "institution", "lender", "admin"];

describe("direct links into the read-only Badban preview", () => {
  it("opens every environment from a link that can be copied into Windows Chrome or Edge", () => {
    for (const surface of surfaces) {
      expect(previewSurfaceFromLocation("/", previewSurfaceUrl(surface).split("?")[1] ? "?" + previewSurfaceUrl(surface).split("?")[1] : "")).toBe(surface);
    }
  });
  it("never treats authenticated or callback URLs as preview routes", () => {
    expect(previewSurfaceFromLocation("/app", "?preview=admin")).toBeNull();
    expect(previewSurfaceFromLocation("/auth/callback", "?preview=admin")).toBeNull();
  });
  it("rejects unknown, missing and altered role names", () => {
    expect(previewSurfaceFromLocation("/", "")).toBeNull();
    expect(previewSurfaceFromLocation("/", "?preview=ADMIN")).toBeNull();
    expect(previewSurfaceFromLocation("/", "?preview=unknown")).toBeNull();
  });
  it("preserves the exact four-surface allowlist even with irrelevant query parameters", () => {
    expect(previewSurfaceFromLocation("/", "?preview=individual&src=desktop")).toBe("individual");
    expect(previewSurfaceFromLocation("/", "?preview=admin&preview=individual")).toBe("admin");
  });
});
