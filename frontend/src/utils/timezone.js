/**
 * Timezone utilities for GateSmart.
 * Allows displaying race times in the user's preferred timezone.
 */

export const TIMEZONE_OPTIONS = [
  { value: 'America/New_York',    label: 'Eastern (ET)',  abbr: 'ET' },
  { value: 'America/Chicago',     label: 'Central (CT)',  abbr: 'CT' },
  { value: 'America/Denver',      label: 'Mountain (MT)', abbr: 'MT' },
  { value: 'America/Los_Angeles', label: 'Pacific (PT)',  abbr: 'PT' },
  { value: 'Europe/London',       label: 'London (GMT/BST)', abbr: 'LON' },
  { value: 'local',               label: 'Device local time', abbr: null },
];

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
  const opt = TIMEZONE_OPTIONS.find((o) => o.value === tz);
  return { time, abbr: opt?.abbr ?? null };
}
