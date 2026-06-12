/**
 * Bridge-managed users carry synthetic placeholder emails
 * (*@runtime.opentrain.invalid) that must never surface in the UI.
 */

import { displayableEmail, isBridgeManagedEmail, isBridgeOrgOwnerEmail } from "./bridge-users";
import { userDisplayName } from "./helpers";

describe("isBridgeManagedEmail", () => {
  it("detects bridge placeholder emails regardless of case", () => {
    expect(isBridgeManagedEmail("ol-42@runtime.opentrain.invalid")).toBe(true);
    expect(isBridgeManagedEmail("OL-42@RUNTIME.OPENTRAIN.INVALID")).toBe(true);
  });

  it("rejects regular emails and empty values", () => {
    expect(isBridgeManagedEmail("alice@example.com")).toBe(false);
    expect(isBridgeManagedEmail("")).toBe(false);
    expect(isBridgeManagedEmail(null)).toBe(false);
    expect(isBridgeManagedEmail(undefined)).toBe(false);
  });
});

describe("isBridgeOrgOwnerEmail", () => {
  it("detects the per-tenant service account", () => {
    expect(isBridgeOrgOwnerEmail("ol-org-7@runtime.opentrain.invalid")).toBe(true);
  });

  it("rejects regular shadow users and external emails", () => {
    expect(isBridgeOrgOwnerEmail("ol-42@runtime.opentrain.invalid")).toBe(false);
    expect(isBridgeOrgOwnerEmail("ol-org-7@example.com")).toBe(false);
  });
});

describe("displayableEmail", () => {
  it("passes through regular emails", () => {
    expect(displayableEmail("alice@example.com")).toBe("alice@example.com");
  });

  it("suppresses bridge placeholder emails", () => {
    expect(displayableEmail("ol-42@runtime.opentrain.invalid")).toBe("");
    expect(displayableEmail(null)).toBe("");
  });
});

describe("userDisplayName (bridge-aware)", () => {
  it("prefers full name in snake_case or camelCase", () => {
    expect(userDisplayName({ first_name: "Ada", last_name: "Lovelace" })).toBe("Ada Lovelace");
    expect(userDisplayName({ firstName: "Ada", lastName: "Lovelace" })).toBe("Ada Lovelace");
  });

  it("falls back to username then email for regular users", () => {
    expect(userDisplayName({ username: "ada", email: "ada@example.com" })).toBe("ada");
    expect(userDisplayName({ email: "ada@example.com" })).toBe("ada@example.com");
  });

  it("never falls back to a bridge placeholder email", () => {
    expect(userDisplayName({ email: "ol-42@runtime.opentrain.invalid" })).toBe("Member");
    expect(userDisplayName({ username: "ol-42@runtime.opentrain.invalid" })).toBe("Member");
  });

  it("returns empty string for genuinely empty users", () => {
    expect(userDisplayName({})).toBe("");
    expect(userDisplayName()).toBe("");
  });
});
