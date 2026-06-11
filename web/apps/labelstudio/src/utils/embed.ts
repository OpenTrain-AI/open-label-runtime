/**
 * Embed mode: the OpenTrain app shell loads the runtime in an iframe with
 * ?embed=1 (and ?embedOrigin=<opentrain origin>) on the launch URL. The flag is
 * seeded into sessionStorage at module evaluation so it survives SPA navigation
 * after the query params are gone.
 */

const EMBED_KEY = "open_label_embed";
const EMBED_ORIGIN_KEY = "open_label_embed_origin";

function urlParams(): URLSearchParams {
  try {
    return new URLSearchParams(window.location.search);
  } catch {
    return new URLSearchParams();
  }
}

function seedFromUrl() {
  const params = urlParams();
  if (params.get("embed") !== "1") return;
  try {
    window.sessionStorage.setItem(EMBED_KEY, "1");
    const origin = params.get("embedOrigin");
    if (origin) window.sessionStorage.setItem(EMBED_ORIGIN_KEY, origin);
  } catch {
    // sessionStorage unavailable (blocked third-party storage) — isEmbedded()
    // falls back to reading the URL directly.
  }
}

seedFromUrl();

export function isEmbedded(): boolean {
  try {
    if (window.sessionStorage.getItem(EMBED_KEY) === "1") return true;
  } catch {
    // ignore and fall back to the URL
  }
  return urlParams().get("embed") === "1";
}

function embedOrigin(): string | null {
  try {
    const stored = window.sessionStorage.getItem(EMBED_ORIGIN_KEY);
    if (stored) return stored;
  } catch {
    // ignore and fall back to the URL
  }
  return urlParams().get("embedOrigin");
}

/** Posts to the embedding OpenTrain shell; silently a no-op outside embed mode. */
export function notifyEmbedParent(message: Record<string, unknown>) {
  if (!isEmbedded() || window.parent === window) return;
  const origin = embedOrigin();
  if (!origin) return;
  window.parent.postMessage(message, origin);
}
