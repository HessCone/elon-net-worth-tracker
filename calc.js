/* Pure helpers shared by the page and the node tests. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.WorthCalc = factory();
})(typeof self !== "undefined" ? self : this, function () {
  var TZ = "America/Chicago";
  var DAY = 24 * 3600 * 1000;

  function startOfZonedDay(timeZone, nowMs) {
    var ymd = new Intl.DateTimeFormat("en-CA", {
      timeZone: timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(new Date(nowMs));
    var parts = ymd.split("-");
    var y = +parts[0], m = +parts[1], d = +parts[2];
    var targetUtc = Date.UTC(y, m - 1, d, 0, 0, 0);
    var guess = Date.UTC(y, m - 1, d, 12, 0, 0);
    var fmt = new Intl.DateTimeFormat("en-US", {
      timeZone: timeZone,
      hourCycle: "h23",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    var shown = {};
    fmt.formatToParts(new Date(guess)).forEach(function (part) { shown[part.type] = part.value; });
    var asUtc = Date.UTC(+shown.year, +shown.month - 1, +shown.day, +shown.hour, +shown.minute, +shown.second);
    return guess - (asUtc - targetUtc);
  }

  // Prefer the newest point at or before the cutoff. If none is close enough and
  // allowAfter is set, use the oldest point shortly after the cutoff instead.
  function changeSince(hist, worthUsd, cutoffMs, maxGapMs, allowAfter) {
    var before = null;
    var beforeT = -Infinity;
    var after = null;
    var afterT = Infinity;
    (hist || []).forEach(function (point) {
      var t = Date.parse(point.t);
      if (isNaN(t)) return;
      if (t <= cutoffMs && t >= beforeT) { before = point; beforeT = t; }
      if (t > cutoffMs && t <= afterT) { after = point; afterT = t; }
    });
    if (before && (maxGapMs == null || cutoffMs - beforeT <= maxGapMs)) {
      return { delta: worthUsd - before.worth_usd, base: before };
    }
    if (allowAfter && after && maxGapMs != null && afterT - cutoffMs <= maxGapMs) {
      return { delta: worthUsd - after.worth_usd, base: after };
    }
    return null;
  }

  function dateKey(iso, timeZone) {
    return new Intl.DateTimeFormat("en-CA", {
      timeZone: timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(new Date(iso));
  }

  function dailyCloses(hist, timeZone) {
    var sorted = (hist || []).slice().sort(function (a, b) { return a.t < b.t ? -1 : a.t > b.t ? 1 : 0; });
    var keys = [];
    var by = {};
    sorted.forEach(function (point) {
      var key = dateKey(point.t, timeZone);
      if (!by[key]) keys.push(key);
      by[key] = point;
    });
    return keys.map(function (key, i) {
      var point = by[key];
      var prev = i > 0 ? by[keys[i - 1]] : null;
      return {
        key: key,
        t: point.t,
        worth_usd: point.worth_usd,
        delta: prev ? point.worth_usd - prev.worth_usd : null,
        seeded: !!point.seeded,
      };
    }).reverse();
  }

  function shareText(worthLabel, changeLabel, pageUrl) {
    var text = "Elon Musk net worth: " + worthLabel;
    if (changeLabel) text += " (" + changeLabel + ")";
    if (pageUrl) text += " via " + pageUrl;
    text += " by @HessCone";
    return text;
  }

  return {
    TZ: TZ,
    DAY: DAY,
    startOfZonedDay: startOfZonedDay,
    changeSince: changeSince,
    dailyCloses: dailyCloses,
    shareText: shareText,
  };
});
