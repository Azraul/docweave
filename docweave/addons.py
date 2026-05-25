"""Addon post-processing — enriches index.json with optional data."""


def run_addons(index: dict, config: dict, project_root: str):
    """Run post-processing addons to enrich the index."""
    addons = config.get("addons", {})

    if addons.get("graph", {}).get("enabled"):
        index["addons"] = index.get("addons", {})
        index["addons"]["graph"] = {"enabled": True}

    if "timeline" in addons:
        run_timeline_addon(index, config, project_root)


import re


def run_timeline_addon(index: dict, config: dict, project_root: str):
    """Build timeline from notes with a date field matching addons.timeline.field."""
    addon_cfg = config["addons"]["timeline"]
    field_name = addon_cfg.get("field")
    date_format = addon_cfg.get("format", "iso")

    if not field_name:
        return

    timeline = []
    unparseable = []

    for slug, note in index["notes"].items():
        raw = note.get(field_name)
        if not raw:
            continue

        entry = {
            "slug": slug,
            "title": note.get("title", slug),
            "type": note.get("type"),
        }

        if date_format == "iso":
            entry["date"] = str(raw)
            timeline.append(entry)
        elif date_format == "era":
            entry["raw"] = str(raw)
            entry["sort_key"] = _era_sort_key(str(raw))
            timeline.append(entry)
        else:
            entry["date"] = str(raw)
            unparseable.append(entry)

    if date_format == "era":
        timeline.sort(key=lambda e: e.get("sort_key", ""))
    else:
        timeline.sort(key=lambda e: e.get("date", ""))

    index["addons"] = index.get("addons", {})
    index["addons"]["timeline"] = {
        "entries": timeline,
        "unparseable": unparseable,
        "field": field_name,
        "format": date_format,
    }


def _era_sort_key(raw: str) -> str:
    """Convert era strings like '~3500 BCE', '~1350 CE' into a sortable key.

    Handles ranges: '~700–900 CE' extracts the start year (~700).
    Handles multi-year: '1489 CE, 1493 CE' extracts the last year (1493).

    Produces a string that sorts chronologically (oldest first) when sorted
    lexicographically. BCE entries get prefix 0, CE entries get prefix 1.
    """
    if not raw:
        return "zzzz"

    s = raw.strip().lstrip("~").strip()

    # Split on whitespace AND on en-dash/em-dash/hyphen ranges
    # so "700–900" becomes ["700", "900"] and we can extract the first year.
    parts = re.split(r"[\s–—-]+", s)
    year = 0
    bc = False

    for p in parts:
        p_clean = p.replace(",", "")
        if p_clean.isdigit():
            year = int(p_clean)
        elif p_clean.upper() in ("BCE", "BC"):
            bc = True

    if bc:
        # ~4000 BCE → sort key "0_5999" (9999 - 4000)
        return f"0_{9999 - year:04d}"
    else:
        # ~1350 CE → sort key "1_1350"
        return f"1_{year:04d}"
