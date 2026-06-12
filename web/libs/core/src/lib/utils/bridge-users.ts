/**
 * Bridge-managed users are provisioned by the OpenTrain control plane with
 * synthetic placeholder emails. Those addresses are an implementation detail
 * and must never surface in the UI — render display names instead.
 */

const BRIDGE_EMAIL_SUFFIX = "@runtime.opentrain.invalid";
const BRIDGE_ORG_OWNER_PREFIX = "ol-org-";

export function isBridgeManagedEmail(email?: string | null): boolean {
  return typeof email === "string" && email.toLowerCase().endsWith(BRIDGE_EMAIL_SUFFIX);
}

/** The per-tenant service account that owns the runtime organization. */
export function isBridgeOrgOwnerEmail(email?: string | null): boolean {
  return isBridgeManagedEmail(email) && (email as string).toLowerCase().startsWith(BRIDGE_ORG_OWNER_PREFIX);
}

/** Email safe to show in UI; empty string for bridge-managed placeholders. */
export function displayableEmail(email?: string | null): string {
  return email && !isBridgeManagedEmail(email) ? email : "";
}
