"""Addon post-processing — enriches index.json with optional data."""


def run_addons(index: dict, config: dict, project_root: str):
    """Run post-processing addons to enrich the index."""
    addons = config.get("addons", {})

    if addons.get("graph", {}).get("enabled"):
        index["addons"] = index.get("addons", {})
        index["addons"]["graph"] = {"enabled": True}

    if "timeline" in addons:
        run_timeline_addon(index, config, project_root)


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
        if raw is None:
            continue

        entry = {
            "slug": slug,
            "title": note.get("title", slug),
            "type": note.get("type"),
        }

        if date_format == "iso":
            entry["date"] = str(raw)
            timeline.append(entry)
        else:
            entry["date"] = str(raw)
            unparseable.append(entry)

    timeline.sort(key=lambda e: e.get("date", ""))

    index["addons"] = index.get("addons", {})
    index["addons"]["timeline"] = {
        "entries": timeline,
        "unparseable": unparseable,
        "field": field_name,
        "format": date_format,
    }
