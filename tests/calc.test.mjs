import { createRequire } from "module";
import assert from "assert";

const require = createRequire(import.meta.url);
const calc = require("../calc.js");

const TZ = calc.TZ;

// 2026-11-26 01:40 UTC is 7:40 PM on Nov 25 in Central Standard Time (UTC-6).
const evening = Date.parse("2026-11-26T01:40:02Z");
assert.strictEqual(calc.startOfZonedDay(TZ, evening), Date.parse("2026-11-25T06:00:00Z"));

// 2026-07-15 17:00 UTC is noon CDT (UTC-5). Midnight that day is 05:00 UTC.
const summer = Date.parse("2026-07-15T17:00:00Z");
assert.strictEqual(calc.startOfZonedDay(TZ, summer), Date.parse("2026-07-15T05:00:00Z"));

const hist = [
  { t: "2026-10-27T21:00:00Z", worth_usd: 900_000_000_000, seeded: true },
  { t: "2026-11-19T01:00:00Z", worth_usd: 850_000_000_000, seeded: true },
  { t: "2026-11-25T05:00:00Z", worth_usd: 810_000_000_000, seeded: true },
  { t: "2026-11-26T01:40:00Z", worth_usd: 823_000_000_000, seeded: false },
];
const now = Date.parse("2026-11-26T01:40:00Z");
const worth = 823_000_000_000;
const today = calc.changeSince(hist, worth, calc.startOfZonedDay(TZ, now), 36 * 3600 * 1000, false);
assert.strictEqual(today.base.t, "2026-11-25T05:00:00Z");
assert.strictEqual(today.delta, 13_000_000_000);

const week = calc.changeSince(hist, worth, now - 7 * calc.DAY, 2 * calc.DAY, true);
assert.strictEqual(week.base.t, "2026-11-19T01:00:00Z");

// The October point is ~20 hours after the exact 30-day cutoff, so it only counts
// when a near miss just inside the window is allowed.
const monthStrict = calc.changeSince(hist, worth, now - 30 * calc.DAY, 4 * calc.DAY, false);
assert.strictEqual(monthStrict, null);
const month = calc.changeSince(hist, worth, now - 30 * calc.DAY, 4 * calc.DAY, true);
assert.strictEqual(month.base.t, "2026-10-27T21:00:00Z");

const tooOld = calc.changeSince(
  [{ t: "2026-01-01T00:00:00Z", worth_usd: 1 }],
  worth,
  calc.startOfZonedDay(TZ, now),
  36 * 3600 * 1000,
);
assert.strictEqual(tooOld, null);

const days = calc.dailyCloses(hist, TZ);
assert.strictEqual(days[0].t, "2026-11-26T01:40:00Z");
assert.ok(days.length >= 3);

const text = calc.shareText("$823.46B", "up $6.54B today", "https://hesscone.github.io/elon-net-worth-tracker/");
assert.ok(text.endsWith("by @HessCone"));
assert.ok(text.includes("$823.46B"));
assert.ok(text.includes("https://hesscone.github.io/elon-net-worth-tracker/"));
assert.ok(text.indexOf("via ") < text.indexOf("by @HessCone"));

const local = calc.shareText("$823.46B", "", "");
assert.strictEqual(local, "Elon Musk net worth: $823.46B by @HessCone");

console.log("calc tests ok");
