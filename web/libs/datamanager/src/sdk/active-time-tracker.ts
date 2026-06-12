/**
 * Tracks user activity so annotation lead_time only counts time the user is
 * actually working. After IDLE_TIMEOUT_MS without mouse/keyboard/scroll/touch
 * input the clock pauses; it resumes on the next interaction. Hiding the tab
 * pauses the clock immediately.
 */

export const ACTIVE_TIME_IDLE_TIMEOUT_MS = 30_000;

const ACTIVITY_EVENTS = ["mousemove", "mousedown", "keydown", "wheel", "touchstart", "scroll"] as const;

// Bounds memory for very long sessions; at the pathological rate of one
// idle/resume cycle per minute this still covers >24h of labeling.
const MAX_CLOSED_WINDOWS = 2_000;

type ActiveWindow = { start: number; end: number };

export class ActiveTimeTracker {
  private closedWindows: ActiveWindow[] = [];
  private windowStart: number | null = null;
  private lastActivityAt = 0;
  private attached = false;

  get isAttached() {
    return this.attached;
  }

  /** Attach global listeners once; safe to call repeatedly and in non-browser environments. */
  ensureAttached() {
    if (this.attached || typeof window === "undefined" || typeof document === "undefined") return;
    this.attached = true;

    const onActivity = () => this.recordActivity(Date.now());

    for (const eventName of ACTIVITY_EVENTS) {
      window.addEventListener(eventName, onActivity, { capture: true, passive: true });
    }
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        this.suspend(Date.now());
      } else {
        this.recordActivity(Date.now());
      }
    });

    this.recordActivity(Date.now());
  }

  recordActivity(now: number) {
    if (this.windowStart === null) {
      this.windowStart = now;
    } else if (now - this.lastActivityAt > ACTIVE_TIME_IDLE_TIMEOUT_MS) {
      // The previous activity window ended; it gets the idle grace period.
      this.pushClosedWindow(this.windowStart, this.lastActivityAt + ACTIVE_TIME_IDLE_TIMEOUT_MS);
      this.windowStart = now;
    }
    if (now > this.lastActivityAt) this.lastActivityAt = now;
  }

  /** Stop counting immediately (e.g., tab hidden) without the idle grace period. */
  suspend(now: number) {
    if (this.windowStart === null) return;
    this.pushClosedWindow(this.windowStart, Math.min(now, this.lastActivityAt + ACTIVE_TIME_IDLE_TIMEOUT_MS));
    this.windowStart = null;
  }

  /**
   * Seconds of active time between startMs and now. Falls back to wall-clock
   * time when the tracker was never attached so non-browser callers keep the
   * legacy behavior.
   */
  activeSecondsSince(startMs: number, nowMs = Date.now()): number {
    if (!this.attached) {
      return Math.max(0, nowMs - startMs) / 1000;
    }

    let activeMs = 0;
    for (const closedWindow of this.closedWindows) {
      activeMs += Math.max(0, Math.min(closedWindow.end, nowMs) - Math.max(closedWindow.start, startMs));
    }
    if (this.windowStart !== null) {
      const openEnd = Math.min(nowMs, this.lastActivityAt + ACTIVE_TIME_IDLE_TIMEOUT_MS);
      activeMs += Math.max(0, openEnd - Math.max(this.windowStart, startMs));
    }
    return activeMs / 1000;
  }

  private pushClosedWindow(start: number, end: number) {
    if (end <= start) return;
    this.closedWindows.push({ start, end });
    if (this.closedWindows.length > MAX_CLOSED_WINDOWS) {
      this.closedWindows.splice(0, this.closedWindows.length - MAX_CLOSED_WINDOWS);
    }
  }
}

export const activeTimeTracker = new ActiveTimeTracker();
