import re
import time

import requests

API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "WheredleBot/0.1 (daily geo-guessing Discord game; daniel.woods@infuse.it)"

_TAG_RE = re.compile(r"<[^>]+>")


def _session():
    """Create a requests session with the User-Agent Commons requires."""
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    return session


def _clean(html):
    """Strip HTML tags and collapse whitespace in an extmetadata value, or None."""
    if not html:
        return None
    text = _TAG_RE.sub("", html)
    return " ".join(text.split()) or None


def _pick_coord(coords):
    """Choose the best earth coordinate, preferring object location over camera location."""
    earth = [c for c in coords if c.get("globe", "earth") == "earth"]
    if not earth:
        return None
    # Object-location coords are added as secondary; primary is usually the camera position.
    secondary = [c for c in earth if "primary" not in c]
    chosen = (secondary or earth)[0]
    return {"lat": chosen["lat"], "lon": chosen["lon"]}


def _extract(page):
    """Turn a raw API page into a candidate dict, or None if it lacks image/coords."""
    info = (page.get("imageinfo") or [None])[0]
    coords = page.get("coordinates") or []
    if not info or not coords:
        return None
    coord = _pick_coord(coords)
    if not coord:
        return None
    meta = info.get("extmetadata", {}) or {}
    return {
        "title": page.get("title"),
        "pageid": page.get("pageid"),
        "image_url": info.get("thumburl") or info.get("url"),
        "width": info.get("width"),
        "height": info.get("height"),
        "mime": info.get("mime"),
        "lat": coord["lat"],
        "lon": coord["lon"],
        "author": _clean((meta.get("Artist") or {}).get("value")),
        "license": _clean((meta.get("LicenseShortName") or {}).get("value")),
        "attribution_url": info.get("descriptionurl"),
    }


def fetch_candidates(category, limit=50, session=None):
    """Yield candidate image dicts (with coordinates) from a Commons category."""
    session = session or _session()
    params = {
        "action": "query",
        "format": "json",
        "generator": "categorymembers",
        "gcmtitle": f"Category:{category}",
        "gcmtype": "file",
        "gcmlimit": str(min(limit, 500)),
        "prop": "imageinfo|coordinates",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": "1920",
        "coprop": "type|name|globe",
        "coprimary": "all",
    }
    cont = {}
    yielded = 0
    while True:
        for attempt in range(3):
            response = session.get(API, params={**params, **cont}, timeout=(5, 30))
            if response.status_code == 429:
                wait = int(response.headers.get("Retry-After", 5))
                time.sleep(wait)
                continue
            response.raise_for_status()
            break
        else:
            return
        time.sleep(0.4)  # stay well under 200 req/min per Wikimedia guidelines
        data = response.json()
        for page in data.get("query", {}).get("pages", {}).values():
            candidate = _extract(page)
            if candidate is None:
                continue
            yield candidate
            yielded += 1
            if yielded >= limit:
                return
        if "continue" in data:
            cont = data["continue"]
        else:
            return
