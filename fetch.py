#!/usr/bin/env python3
"""Pull Elon Musk's net worth from Forbes's public real-time billionaire JSON.

Stdlib only. No API key. Writes data/latest.json and data/history.json.
Numbers are whatever Forbes returns on this run. Nothing is hardcoded.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

PROFILE_URL = "https://www.forbes.com/forbesapi/person/elon-musk.json"
RTB_URL = "https://www.forbes.com/forbesapi/person/rtb/0/position/true.json"
AJAX_URL = "https://www.forbes.com/ajax/list/data?type=person&year=0&uri=rtb"
PROFILE_PAGE = "https://www.forbes.com/profile/elon-musk/"
LIST_PAGE = "https://www.forbes.com/real-time-billionaires/"

# Worth must land in this range or the payload is treated as a parse error.
MIN_USD = 1_000_000_000
MAX_USD = 1_000_000_000_000_000
# Forbes's headline is rounded finer than a raw shares x price sum.
HOLDINGS_TOLERANCE_USD = 10_000
MAX_SOURCE_AGE_SEC = 3 * 24 * 3600
MAX_FUTURE_SKEW_SEC = 10 * 60
SEED_GAP_SEC = 45 * 60
LIVE_REPLACE_SEC = 50 * 60

UA = ("Mozilla/5.0 (compatible; elon-net-worth-tracker/1.0; "
      "+https://github.com/HessCone/elon-net-worth-tracker)")

SOURCE_NAMES = {
    "forbes-profile": "Forbes Real-Time Billionaires",
    "forbes-rtb": "Forbes Real-Time Billionaires (list fallback)",
    "forbes-ajax": "Forbes Real-Time Billionaires (list feed fallback)",
}


def D(value):
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def millions_to_usd(millions):
    """Forbes reports net worth in millions of US dollars."""
    return int((D(millions) * Decimal(1_000_000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def json_number(value):
    """A JSON-safe number that round-trips the Decimal we were given."""
    q = D(value).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    text = format(q, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return json.loads(text)


def iso(dt):
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def iso_from_ms(ms):
    return iso(datetime.fromtimestamp(float(ms) / 1000, timezone.utc))


def parse_time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


def get_json(url, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "application/json,text/plain,*/*",
                "Referer": LIST_PAGE,
            })
            with urllib.request.urlopen(req, timeout=40) as response:
                raw = response.read().decode("utf-8")
            return json.loads(raw, parse_float=Decimal)
        except Exception as exc:  # noqa: BLE001 - retry any transport or parse error
            last = exc
            if i == tries - 1:
                break
            time.sleep(2 * (i + 1))
    raise last


def worth_millions(entry):
    if not isinstance(entry, dict):
        return None
    if entry.get("finalWorth") is not None:
        return D(entry["finalWorth"])
    if entry.get("finalWorthBillions") is not None:
        return D(entry["finalWorthBillions"]) * Decimal(1000)
    if entry.get("worth") is not None:
        return D(entry["worth"])
    return None


def _is_elon(uri, name):
    return uri == "elon-musk" or name == "Elon Musk"


def parse_rtb_entry(entry, source_id, api_url):
    """Normalize one Forbes real-time list entry. None if it is not Elon."""
    if not isinstance(entry, dict):
        return None
    person = entry.get("person") if isinstance(entry.get("person"), dict) else {}
    name = person.get("name") or entry.get("personName") or entry.get("name")
    uri = entry.get("uri") or person.get("uri")
    if not _is_elon(uri, name):
        return None
    millions = worth_millions(entry)
    if millions is None:
        millions = worth_millions(person)
    if millions is None:
        return None
    previous = entry.get("estWorthPrev")
    if previous is None:
        previous = person.get("estWorthPrev")
    private = entry.get("privateAssetsWorth")
    if private is None:
        private = person.get("privateAssetsWorth")
    assets = entry.get("financialAssets")
    if assets is None:
        assets = person.get("financialAssets")
    history = entry.get("wealthHistory") or person.get("wealthHistory")
    timestamp = entry.get("timestamp")
    if timestamp is None:
        timestamp = person.get("timestamp")
    rank = entry.get("rank")
    if rank is None:
        rank = entry.get("position")
    return _pack(
        source_id=source_id,
        api_url=api_url,
        millions=millions,
        previous=previous,
        private=private,
        assets=assets if isinstance(assets, list) else None,
        history=history if isinstance(history, dict) else None,
        timestamp=timestamp,
        rank=rank,
    )


def parse_ajax_entry(entry, api_url):
    if not isinstance(entry, dict):
        return None
    if not _is_elon(entry.get("uri"), entry.get("name")):
        return None
    if entry.get("worth") is None:
        return None
    millions = D(entry["worth"])
    previous = None
    if entry.get("worthChange") is not None:
        previous = millions - D(entry["worthChange"])
    return _pack(
        source_id="forbes-ajax",
        api_url=api_url,
        millions=millions,
        previous=previous,
        private=None,
        assets=None,
        history=None,
        timestamp=entry.get("timestamp"),
        rank=entry.get("rank"),
    )


def _pack(source_id, api_url, millions, previous, private, assets, history, timestamp, rank):
    return {
        "source_id": source_id,
        "source_name": SOURCE_NAMES[source_id],
        "source_url": LIST_PAGE,
        "profile_url": PROFILE_PAGE,
        "api": api_url,
        "fallback": source_id != "forbes-profile",
        "name": "Elon Musk",
        "rank": int(rank) if rank is not None else None,
        "worth_millions": millions,
        "previous_millions": D(previous) if previous is not None else None,
        "private_millions": D(private) if private is not None else None,
        "financial_assets": assets,
        "wealth_history": history,
        "timestamp_ms": int(timestamp) if timestamp is not None else None,
    }


def parse_profile(payload, api_url):
    person = payload.get("person") if isinstance(payload, dict) else None
    if not isinstance(person, dict):
        return None
    for entry in person.get("personLists") or []:
        if isinstance(entry, dict) and entry.get("listUri") == "rtb":
            parsed = parse_rtb_entry(entry, "forbes-profile", api_url)
            if parsed:
                return parsed
    return None


def parse_position_list(payload, api_url):
    if not isinstance(payload, dict):
        return None
    persons = ((payload.get("personList") or {}).get("personsLists")) or []
    if isinstance(persons, dict):
        persons = [persons]
    for entry in persons:
        parsed = parse_rtb_entry(entry, "forbes-rtb", api_url)
        if parsed:
            return parsed
    return None


def parse_ajax_list(payload, api_url):
    if not isinstance(payload, list):
        return None
    for entry in payload:
        parsed = parse_ajax_entry(entry, api_url)
        if parsed:
            return parsed
    return None


def validate(parsed, now=None):
    now = now or datetime.now(timezone.utc)
    worth = millions_to_usd(parsed["worth_millions"])
    if not (MIN_USD <= worth <= MAX_USD):
        raise ValueError(f"worth ${worth} is outside the expected range")
    if parsed["name"] != "Elon Musk":
        raise ValueError("payload was not Elon Musk")
    if parsed["timestamp_ms"] is not None:
        skew = now.timestamp() - (parsed["timestamp_ms"] / 1000)
        if skew < -MAX_FUTURE_SKEW_SEC:
            raise ValueError("source timestamp is in the future")
        if skew > MAX_SOURCE_AGE_SEC:
            raise ValueError("source timestamp is older than 3 days")
    return worth


def asset_value_usd(asset):
    """Dollar value of one Forbes financial-asset line.

    Shares are shares x price. Options are shares x (price - strike), which is
    the valuation that makes Forbes's lines add up to the published total.
    Returns None when the line cannot be priced.
    """
    if not isinstance(asset, dict) or asset.get("numberOfShares") is None:
        return None
    if asset.get("currentPrice") is not None:
        price = D(asset["currentPrice"])
    elif asset.get("sharePrice") is not None:
        price = D(asset["sharePrice"])
    else:
        return None
    shares = D(asset["numberOfShares"])
    if shares < 0 or price < 0:
        return None
    if asset.get("exerciseOptionPrice") is not None:
        price = price - D(asset["exerciseOptionPrice"])
        if price < 0:
            price = Decimal(0)
    currency = str(asset.get("currencyCode") or "USD").upper()
    if asset.get("exchangeRate") is None:
        if currency != "USD":
            return None
        fx = Decimal(1)
    else:
        fx = D(asset["exchangeRate"])
        if fx <= 0:
            return None
    return int((shares * price * fx).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _kind(asset):
    return "options" if asset.get("exerciseOptionPrice") is not None else "shares"


def build_holdings(parsed):
    """Return (rows, private_usd, included, note).

    The breakdown is included only when every line can be priced and the
    lines plus Forbes's private-assets figure match the headline total.
    """
    assets = parsed.get("financial_assets")
    if not assets:
        if parsed["fallback"]:
            note = "This Forbes feed published the total only, with no holdings breakdown."
        else:
            note = "Forbes did not include a holdings breakdown in this response."
        return [], None, False, note

    rows = []
    total = 0
    for asset in assets:
        value = asset_value_usd(asset)
        if value is None:
            return [], None, False, (
                "Holdings were left off this update because a Forbes line could not be priced."
            )
        total += value
        price = asset["currentPrice"] if asset.get("currentPrice") is not None else asset["sharePrice"]
        rows.append({
            "company": asset.get("companyName") or "Unknown",
            "ticker": asset.get("ticker") or "",
            "exchange": asset.get("exchange") or "",
            "kind": _kind(asset),
            "shares": json_number(asset["numberOfShares"]),
            "price_usd": json_number(price),
            "exercise_price_usd": (
                json_number(asset["exerciseOptionPrice"])
                if asset.get("exerciseOptionPrice") is not None else None
            ),
            "value_usd": value,
        })

    private_usd = None
    if parsed.get("private_millions") is not None:
        private_usd = millions_to_usd(parsed["private_millions"])
        total += private_usd

    worth = millions_to_usd(parsed["worth_millions"])
    if abs(total - worth) > HOLDINGS_TOLERANCE_USD:
        return [], None, False, (
            "Holdings were left off this update because Forbes's line items "
            "did not add up to the headline total."
        )
    rows.sort(key=lambda row: row["value_usd"], reverse=True)
    return rows, private_usd, True, ""


def build_latest(parsed, now):
    worth = validate(parsed, now)
    holdings, private_usd, included, note = build_holdings(parsed)
    previous = parsed.get("previous_millions")
    as_of = iso_from_ms(parsed["timestamp_ms"]) if parsed.get("timestamp_ms") else None
    return {
        "name": "Elon Musk",
        "checked_at": iso(now),
        "as_of": as_of,
        "source": {
            "id": parsed["source_id"],
            "name": parsed["source_name"],
            "url": parsed["source_url"],
            "profile_url": parsed["profile_url"],
            "api": parsed["api"],
            "fallback": parsed["fallback"],
        },
        "rank": parsed.get("rank"),
        "worth_usd": worth,
        "forbes_previous_worth_usd": millions_to_usd(previous) if previous is not None else None,
        "holdings": holdings,
        "private_assets_usd": private_usd if included else None,
        "holdings_included": included,
        "holdings_note": note,
    }


def history_point(when, worth_usd, source, seeded, rounded):
    return {
        "t": when,
        "worth_usd": int(worth_usd),
        "source": source,
        "seeded": bool(seeded),
        "rounded": bool(rounded),
    }


def seed_points(wealth_history):
    """Daily and hourly Forbes wealth-history readings, deduped to 45 minutes.

    Forbes publishes these as whole millions of dollars. lastDay (about every
    five minutes) is skipped because lastWeek already covers that window hourly.
    """
    if not isinstance(wealth_history, dict):
        return []
    raw = []
    for key in ("lastMonth", "lastWeek"):
        series = wealth_history.get(key) or []
        if not isinstance(series, list):
            continue
        for point in series:
            if not isinstance(point, dict):
                continue
            if point.get("date") is None or point.get("value") is None:
                continue
            try:
                worth = millions_to_usd(point["value"])
            except Exception:
                continue
            if not (MIN_USD <= worth <= MAX_USD):
                continue
            raw.append((int(point["date"]), worth))
    raw.sort()
    kept = []
    for ms, worth in raw:
        if kept and abs(ms - kept[-1][0]) < SEED_GAP_SEC * 1000:
            kept[-1] = (ms, worth)
        else:
            kept.append((ms, worth))
    return [
        history_point(iso_from_ms(ms), worth, "forbes-wealth-history", True, True)
        for ms, worth in kept
    ]


def merge_seeds(hist, wealth_history):
    hist = list(hist or [])
    for point in seed_points(wealth_history):
        ts = parse_time(point["t"])
        if any(abs(parse_time(item["t"]) - ts) < SEED_GAP_SEC for item in hist):
            continue
        hist.append(point)
    hist.sort(key=lambda item: item["t"])
    return hist


def upsert_live(hist, point):
    hist = list(hist or [])
    ts = parse_time(point["t"])
    worth = point["worth_usd"]
    best_i = None
    best_d = None
    for i, item in enumerate(hist):
        if item.get("seeded"):
            limit = 15 * 60
        elif item.get("source") == point["source"]:
            limit = LIVE_REPLACE_SEC
        else:
            continue
        delta = abs(parse_time(item["t"]) - ts)
        if delta <= limit and (best_d is None or delta < best_d):
            best_i, best_d = i, delta
    if best_i is not None:
        previous = hist[best_i]
        moved = abs(int(previous["worth_usd"]) - int(worth)) >= 1_000_000
        if (not previous.get("seeded")) and moved and best_d > 5 * 60:
            hist.append(point)
        else:
            hist[best_i] = point
    else:
        hist.append(point)
    hist.sort(key=lambda item: item["t"])
    return hist


def load_json(name, default):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_json(name, obj):
    path = os.path.join(DATA, name)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(obj, handle, indent=2)
        handle.write("\n")
    os.replace(temporary, path)


def fetch_parsed():
    attempts = (
        ("forbes-profile", PROFILE_URL, parse_profile),
        ("forbes-rtb", RTB_URL, parse_position_list),
        ("forbes-ajax", AJAX_URL, parse_ajax_list),
    )
    errors = []
    for source_id, url, parser in attempts:
        try:
            payload = get_json(url)
            parsed = parser(payload, url)
            if parsed is None:
                raise ValueError("Elon Musk real-time worth was not in the response")
            validate(parsed)
            if errors:
                print(f"used fallback {source_id} after: {'; '.join(errors)}", file=sys.stderr)
            return parsed
        except Exception as exc:  # noqa: BLE001 - try the next public feed
            errors.append(f"{source_id}: {exc}")
            time.sleep(1)
    print("All Forbes sources failed.", file=sys.stderr)
    for line in errors:
        print(" -", line, file=sys.stderr)
    sys.exit(1)


def main():
    os.makedirs(DATA, exist_ok=True)
    now = datetime.now(timezone.utc)
    parsed = fetch_parsed()
    latest = build_latest(parsed, now)
    hist = load_json("history.json", [])
    if not isinstance(hist, list):
        hist = []
    hist = merge_seeds(hist, parsed.get("wealth_history"))
    live = history_point(
        latest["checked_at"],
        latest["worth_usd"],
        parsed["source_id"],
        False,
        False,
    )
    hist = upsert_live(hist, live)
    save_json("latest.json", latest)
    save_json("history.json", hist)
    billions = latest["worth_usd"] / 1_000_000_000
    print(
        f"{latest['checked_at']}  source={parsed['source_id']}  "
        f"worth=${billions:.2f}B  rank={latest['rank']}  "
        f"holdings={latest['holdings_included']}  history={len(hist)}"
    )


if __name__ == "__main__":
    main()
