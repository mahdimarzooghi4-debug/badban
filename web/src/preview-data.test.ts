import { describe, expect, it } from "vitest";
import { previewPageIds, previewWorkspaces } from "./preview-data";
import type { Surface } from "./workspace-access";

const surfaces: Surface[] = ["individual", "institution", "lender", "admin"];

describe("read-only workspace previews", () => {
  it("contains all four canonical Badban environments in one preview bundle", () => {
    expect(Object.keys(previewWorkspaces).sort()).toEqual([...surfaces].sort());
  });

  it("provides a dashboard and a page for every navigation item", () => {
    for (const surface of surfaces) {
      const workspace = previewWorkspaces[surface];
      expect(workspace.pages.dashboard).toBeDefined();
      for (const item of workspace.menu) {
        expect(workspace.pages[item.id]).toBeDefined();
      }
    }
  });

  it("marks every workspace as read-only", () => {
    for (const surface of surfaces) {
      expect(previewWorkspaces[surface].readOnly).toBe(true);
    }
  });

  it("keeps every preview page explicitly separate from live operational data", () => {
    for (const surface of surfaces) {
      for (const page of Object.values(previewWorkspaces[surface].pages)) {
        expect(page.description).toContain("نمونه");
      }
    }
  });

  it("does not expose action or mutation definitions in preview content", () => {
    for (const surface of surfaces) {
      const workspace = previewWorkspaces[surface];
      expect(JSON.stringify(workspace)).not.toMatch(/submitRequest|approve|transfer|payment|mutate/i);
    }
  });

  it("keeps all menu pages reachable from the same four-environment bundle", () => {
    expect(surfaces.map(surface => previewPageIds(surface).length)).toEqual([5, 5, 5, 9]);
  });
});
