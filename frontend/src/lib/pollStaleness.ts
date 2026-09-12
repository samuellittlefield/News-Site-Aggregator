/** Shared staleness/thinness classification for VoteHub-average-driven cards
 *  (poll-staleness-labels). One helper, not three copies — `classify()` in
 *  SourceHealthSection is the precedent (PR #12).
 *
 *  This labels a number; it never changes one. `compute_average`'s rolling
 *  21-day window (measured from now, not from the data) drains on its own
 *  schedule when an upstream feed goes quiet — this makes that visible
 *  instead of letting a card silently jump or vanish. See
 *  docs/features/poll-staleness-labels/.
 */

/** Judgement call, not a finding (see the feature plan's Open Questions) —
 *  approval polling normally arrives weekly, so 10 days without a new poll is
 *  genuinely unusual. Single named constant so it's trivially tunable. */
export const STALE_THRESHOLD_DAYS = 10;

/** Below this many polls, the average is one or two pollsters' numbers, not a
 *  real average — call that out rather than let it read as authoritative. */
export const THIN_POLL_COUNT_THRESHOLD = 3;

export function daysSince(iso: string): number {
  return (Date.now() - new Date(iso).getTime()) / 86_400_000;
}

/** More than the threshold old. Exactly-at-threshold is still fresh. */
export function isStale(newestFieldworkEnd: string | null | undefined): boolean {
  if (!newestFieldworkEnd) return true;
  return daysSince(newestFieldworkEnd) > STALE_THRESHOLD_DAYS;
}

export function isThinAverage(nPolls: number): boolean {
  return nPolls < THIN_POLL_COUNT_THRESHOLD;
}

/** Format a date-only or full-datetime ISO string as e.g. "Aug 28", always
 *  reading the calendar date in UTC. `end_date` is stored tz-aware UTC; a
 *  poll ending 2026-08-28T00:00:00Z must not render as the 27th just because
 *  the reader is west of Greenwich (AC edge case — verify in US locales). */
export function fmtFieldworkDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export interface AverageStaleness {
  stale: boolean;
  thin: boolean;
  /** "Aug 28", or null if there's no fieldwork date at all (AC-8: a
   *  genuinely empty table has no date to name — never fabricate one). */
  newestLabel: string | null;
}

/** The one place every VoteHub-average-driven card gets its staleness
 *  verdict from, so the threshold can't drift between them. */
export function classifyAverage(
  newestFieldworkEnd: string | null | undefined,
  nPolls: number
): AverageStaleness {
  return {
    stale: isStale(newestFieldworkEnd),
    thin: isThinAverage(nPolls),
    newestLabel: newestFieldworkEnd ? fmtFieldworkDate(newestFieldworkEnd) : null,
  };
}
