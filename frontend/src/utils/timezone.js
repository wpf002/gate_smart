/**
 * Timezone utilities for GateSmart.
 * Allows displaying race times in the user's preferred timezone.
 */

export const TIMEZONE_OPTIONS = [
  { value: 'local',               label: 'Auto — device timezone', abbr: null },
  { value: 'America/New_York',    label: 'Eastern (ET)',  abbr: 'ET' },
  { value: 'America/Chicago',     label: 'Central (CT)',  abbr: 'CT' },
  { value: 'America/Denver',      label: 'Mountain (MT)', abbr: 'MT' },
  { value: 'America/Los_Angeles', label: 'Pacific (PT)',  abbr: 'PT' },
  { value: 'Europe/London',       label: 'London (GMT/BST)', abbr: 'LON' },
];

/**
 * Resolve a stored timezone preference to a real IANA zone.
 * 'local' (the Auto option) reads the device's current zone via the Intl API.
 */
export function resolveTimezone(tz) {
  if (!tz || tz === 'local') {
    try { return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined; }
    catch { return undefined; }
  }
  return tz;
}

/**
 * Format an ISO datetime string into HH:MM am/pm in the given IANA timezone.
 * Falls back to device local time when tz is 'local' or null.
 *
 * @param {string} isoString  - ISO 8601 datetime (e.g. "2024-04-10T19:30:00Z")
 * @param {string} tz         - IANA timezone or 'local'
 * @returns {{ time: string, abbr: string|null }}
 */
export function formatRaceTime(isoString, tz) {
  if (!isoString) return { time: '', abbr: null };
  const date = new Date(isoString);
  if (isNaN(date.getTime())) return { time: '', abbr: null };

  const useLocal = !tz || tz === 'local';
  const timeZone = useLocal ? undefined : tz;
  const time = date.toLocaleTimeString('en-US', {
    timeZone,
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
  // For Auto/'local', look up the abbreviation against the resolved IANA zone
  // so the user still sees a sensible label like "CT" or "PT" rather than nothing.
  const lookupTz = useLocal ? resolveTimezone(tz) : tz;
  const opt = TIMEZONE_OPTIONS.find((o) => o.value === lookupTz);
  return { time, abbr: opt?.abbr ?? null };
}
