/**
 * @jest-environment jsdom
 */
import { ActiveTimeTracker } from "./active-time-tracker";

function attachedTrackerAt(startMs: number): ActiveTimeTracker {
  jest.useFakeTimers().setSystemTime(startMs);
  const tracker = new ActiveTimeTracker();
  tracker.ensureAttached();
  return tracker;
}

afterEach(() => {
  jest.useRealTimers();
});

describe("ActiveTimeTracker", () => {
  it("falls back to wall-clock time when never attached", () => {
    const tracker = new ActiveTimeTracker();
    expect(tracker.activeSecondsSince(1_000, 11_000)).toBe(10);
  });

  it("counts continuous activity fully", () => {
    const tracker = attachedTrackerAt(0);
    tracker.recordActivity(5_000);
    tracker.recordActivity(10_000);
    expect(tracker.activeSecondsSince(0, 10_000)).toBe(10);
  });

  it("pauses after the idle timeout plus grace period", () => {
    const tracker = attachedTrackerAt(0);
    tracker.recordActivity(10_000);
    // Idle from 10s on: only the 30s grace period is counted.
    expect(tracker.activeSecondsSince(0, 100_000)).toBe(40);
  });

  it("resumes counting on activity after an idle gap", () => {
    const tracker = attachedTrackerAt(0);
    tracker.recordActivity(10_000);
    tracker.recordActivity(100_000);
    tracker.recordActivity(105_000);
    expect(tracker.activeSecondsSince(0, 105_000)).toBe(45);
  });

  it("only counts activity after the requested start timestamp", () => {
    const tracker = attachedTrackerAt(0);
    tracker.recordActivity(10_000);
    expect(tracker.activeSecondsSince(5_000, 10_000)).toBe(5);
  });

  it("suspend stops counting immediately and activity reopens the clock", () => {
    const tracker = attachedTrackerAt(0);
    tracker.recordActivity(10_000);
    tracker.suspend(12_000);
    expect(tracker.activeSecondsSince(0, 50_000)).toBe(12);
    tracker.recordActivity(60_000);
    expect(tracker.activeSecondsSince(0, 61_000)).toBe(13);
  });
});
