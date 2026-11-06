import { describe, expect, it } from "vitest";
import { previewPageIds, previewWorkspaces } from "./preview-data";
import type { Surface } from "./workspace-access";

const surfaces: Surface[] = ["individual", "institution", "lender", "admin"];

describe("Badban preview navigation", () => {
  it("has one switchable entry for every environment", () => {
    expect(Object.keys(previewWorkspaces).sort()).toEqual([...surfaces].sort());
  });

  it("keeps the preview read-only and navigable", () => {
    for (const surface of surfaces) {
      const workspace = previewWorkspaces[surface];
      expect(workspace.readOnly).toBe(true);
      expect(workspace.menu.length).toBeGreaterThan(0);
      for (const item of workspace.menu) {
        expect(workspace.pages[item.id]).toBeDefined();
      }
    }
  });

  it("contains no empty environment bundles", () => {
    for (const surface of surfaces) {
      expect(previewPageIds(surface).length).toBeGreaterThan(1);
    }
  });
});
