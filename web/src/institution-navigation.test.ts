import { describe, expect, it } from "vitest";
import { institutionViewForNavigationIndex } from "./institution-navigation";

describe("supporting institution navigation", () => {
  it("keeps the existing program workspace and enables only history and reports", () => {
    expect([0, 1, 2, 3, 4, 5, 6].map(institutionViewForNavigationIndex)).toEqual([
      "home", null, null, "history", "reports", null, null,
    ]);
  });

  it("does not accidentally enable any unknown or negative navigation index", () => {
    expect(institutionViewForNavigationIndex(-1)).toBeNull();
    expect(institutionViewForNavigationIndex(7)).toBeNull();
    expect(institutionViewForNavigationIndex(Number.NaN)).toBeNull();
  });
});
