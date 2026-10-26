#!/usr/bin/env python3
"""Fetch current values from MM2Values and write site/values.json + site/history.json.

Run by the GitHub Action once a day. Uses only the Python standard library.
"""
import json, re, sys, time, urllib.request, datetime, pathlib, html

ROOT = pathlib.Path(__file__).resolve().parent.parent
ITEMS = json.loads((ROOT / "scripts/items.json").read_text())
VALUES = ROOT / "site/values.json"
HISTORY = ROOT / "site/history.json"

PAGES = ["ancient", "chroma", "godly", "vintage", "legend", "rare", "uncommon", "common", "pets"]
CAT2PAGE = {"Ancient": "ancient", "Chroma": "chroma", "Godly": "godly", "Vintage": "vintage",
            "Legendary": "legend", "Rare": "rare", "Uncommon": "uncommon", "Common": "common", "Pets": "pets"}
ROW = re.compile(
    r"<div class=stackable><img src='img/([^']+)'[^>]*><b>(.*?)</b>(?:<br>)?\s*Value:\s*([\d,]*)"
    r".*?Demand:\s*([^<-]*?)\s*-.*?Stability:\s*([^<]*)<hr>", re.S)


def fetch(page):
    req = urllib.request.Request("https://mm2values.com/?p=" + page, headers={
        "User-Agent": "Mozilla/5.0 (mm2-collection-tracker value sync; once per day)"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa
            print(f"  {page}: attempt {attempt + 1} failed: {e}")
            time.sleep(5 * (attempt + 1))
    return None


def norm(s):
    s = html.unescape(s).lower().replace("'", "")
    return re.sub(r"[^a-z0-9]", "", s)


def strip_kg(s):
    return re.sub(r"(knife|gun)$", "", s)


def no_paren(s):
    return re.sub(r"\s*\(.*?\)", "", s)


def scrape():
    rows = {}
    for p in PAGES:
        t = fetch(p)
        if t is None:
            print(f"!! could not load page {p}")
            return None
        rows[p] = []
        for m in ROW.finditer(t):
            img, name, val, dem, stab = m.groups()
            name = re.sub(r"<[^>]+>", "", name).strip()
            rows[p].append({"img": img.strip(), "name": html.unescape(name), "n": norm(name),
                            "val": int(val.replace(",", "")) if val.replace(",", "") else None,
                            "dem": dem.strip(), "stab": stab.strip(), "used": False})
        print(f"  {p}: {len(rows[p])} items")
        time.sleep(1.5)
    return rows


def match(rows):
    out = {}
    pages_for = lambda i: [CAT2PAGE[i["cat"]]] if i["cat"] in CAT2PAGE else PAGES

    def take(i, r):
        r["used"] = True
        out[i["id"]] = [r["val"], r["dem"], r["stab"]]

    todo = list(ITEMS)
    # 1) by image file (most stable key on MM2Values)
    rest = []
    for i in todo:
        hit = None
        if i["img"]:
            for p in pages_for(i):
                c = [r for r in rows[p] if not r["used"] and r["img"].lower() == i["img"].lower()
                     and r["img"].lower() != "coming.png"]
                if len(c) > 1:
                    c = [r for r in c if strip_kg(r["n"]) == strip_kg(norm(no_paren(i["name"])))] or c
                if c:
                    hit = c[0]; break
        if hit: take(i, hit)
        else: rest.append(i)
    # 2) by name, then name without Knife/Gun suffix, then name without "(...)"
    for keyf in (lambda s: norm(s), lambda s: strip_kg(norm(s)), lambda s: strip_kg(norm(no_paren(s)))):
        nxt = []
        for i in rest:
            hit = None
            for p in pages_for(i):
                c = [r for r in rows[p] if not r["used"] and keyf(r["name"]) == keyf(i["name"])]
                if c: hit = c[0]; break
            if hit: take(i, hit)
            else: nxt.append(i)
        rest = nxt
    unmatched_rows = [f'{p}:{r["name"]}' for p in PAGES for r in rows[p] if not r["used"]]
    return out, [i["id"] for i in rest], unmatched_rows


def main():
    print("Fetching MM2Values ...")
    rows = scrape()
    if rows is None or sum(len(v) for v in rows.values()) < 500:
        print("!! Scrape looks broken, keeping old values.")
        sys.exit(1)
    vals, missing_items, extra_rows = match(rows)
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    print(f"matched {len(vals)} items, {len(missing_items)} of ours without MM2Values entry, "
          f"{len(extra_rows)} MM2Values entries not in our list")

    old = json.loads(VALUES.read_text()) if VALUES.exists() else {}
    hist = json.loads(HISTORY.read_text()) if HISTORY.exists() else {}
    if not hist:  # seed with the values the site shipped with
        for i in ITEMS:
            if i.get("val") is not None:
                hist[i["id"]] = [["2026-10-25", i["val"]]]
    changed = 0
    for iid, (v, _, _) in vals.items():
        if v is None: continue
        h = hist.setdefault(iid, [])
        if not h or h[-1][1] != v:
            if h and h[-1][0] == today: h[-1][1] = v
            else: h.append([today, v])
            changed += 1
    print(f"{changed} value changes recorded")

    same = old.get("v") == vals
    data = {"updated": today if not same or "updated" not in old else old["updated"],
            "source": "https://mm2values.com", "v": vals,
            "notInList": extra_rows}
    VALUES.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))
    HISTORY.write_text(json.dumps(hist, separators=(",", ":"), ensure_ascii=False))


if __name__ == "__main__":
    main()
