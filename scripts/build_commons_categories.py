import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pycountry

from wheredle.game import countries
from wheredle.sourcing.commons import API, _session

OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "commons_categories.csv"

# Commons groups "Quality images" by country; this maps each country to the populated
# category we sample from. The photo's own coordinate still decides the answer, so the
# category only controls *where in the world* we look, balancing the puzzle geography.
CATEGORY_TEMPLATE = "Quality images of {name}"


def name_variants(iso2, registry_name):
    """Yield plausible Commons country names, most-canonical first, de-duplicated."""
    seen = set()
    record = pycountry.countries.get(alpha_2=iso2)
    candidates = [
        getattr(record, "common_name", None) if record else None,
        registry_name,
        getattr(record, "name", None) if record else None,
    ]
    for name in candidates:
        if not name:
            continue
        for variant in (name, name.removeprefix("the ").removeprefix("The ")):
            if variant and variant not in seen:
                seen.add(variant)
                yield variant


def _chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def main():
    """Probe Commons for each country's quality-image category and write the mapping CSV."""
    session = _session()

    # title -> (iso2, name); a title may appear once, but several titles map to one country.
    title_to_country = {}
    for country in countries.all_countries():
        for name in name_variants(country.iso2, country.name):
            title_to_country[f"Category:{CATEGORY_TEMPLATE.format(name=name)}"] = (country.iso2, name)

    file_counts = {}
    titles = list(title_to_country)
    for chunk in _chunks(titles, 50):
        params = {
            "action": "query",
            "format": "json",
            "titles": "|".join(chunk),
            "prop": "categoryinfo",
        }
        data = session.get(API, params=params, timeout=30).json()
        for page in data.get("query", {}).get("pages", {}).values():
            title = page.get("title")
            file_counts[title] = (page.get("categoryinfo") or {}).get("files", 0)

    # For each country keep the variant with the most files (0 means no usable category).
    best = {}
    for title, (iso2, name) in title_to_country.items():
        files = file_counts.get(title, 0)
        if files > best.get(iso2, (None, -1))[1]:
            best[iso2] = (CATEGORY_TEMPLATE.format(name=name), files)

    rows = sorted((iso2, cat, files) for iso2, (cat, files) in best.items() if files > 0)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["iso2", "category", "files"])
        writer.writerows(rows)

    print(f"wrote {len(rows)} country categories to {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
