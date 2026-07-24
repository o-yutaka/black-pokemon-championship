from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable

API_ROOT = "https://api.pokemontcg.io/v2/cards"
_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60
_IMAGE_PATTERN = re.compile(r"https?://images\.pokemontcg\.io/[^\s]+", re.IGNORECASE)
_API_CARD_PATTERN = re.compile(r"(?:api\.pokemontcg\.io/v2/cards/|pokemontcg\.io/card/)([A-Za-z0-9.-]+)", re.IGNORECASE)


def _cache_path() -> Path:
    configured = os.environ.get("BLACK_CARD_ART_CACHE")
    return Path(configured).expanduser() if configured else Path.home() / ".cache" / "black-battle-studio" / "card-art.json"


def _load_cache() -> dict[str, Any]:
    path = _cache_path()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_cache(cache: dict[str, Any]) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(path)


def _request(url: str) -> dict[str, Any]:
    headers = {"Accept": "application/json", "User-Agent": "BLACK-Battle-Studio/1.0"}
    api_key = os.environ.get("POKEMON_TCG_API_KEY")
    if api_key:
        headers["X-Api-Key"] = api_key
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=8) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("Pokemon TCG API returned a non-object payload")
    return payload


def _images(card: dict[str, Any]) -> dict[str, str] | None:
    images = card.get("images")
    if not isinstance(images, dict):
        return None
    small = images.get("small")
    large = images.get("large")
    if not isinstance(small, str) and not isinstance(large, str):
        return None
    return {
        "small": small if isinstance(small, str) else large,
        "large": large if isinstance(large, str) else small,
        "providerId": str(card.get("id") or ""),
    }


def _from_link(link: str) -> dict[str, str] | None:
    direct = _IMAGE_PATTERN.search(link)
    if direct:
        image = direct.group(0)
        return {"small": image, "large": image, "providerId": "direct-link"}
    match = _API_CARD_PATTERN.search(link)
    if not match:
        return None
    payload = _request(f"{API_ROOT}/{urllib.parse.quote(match.group(1))}?select=id,images")
    card = payload.get("data")
    return _images(card) if isinstance(card, dict) else None


def _normalize_number(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", value or "").lstrip("0") or "0"


def _query_card(card: dict[str, Any]) -> dict[str, str] | None:
    name = str(card.get("name") or "").strip()
    number = str(card.get("number") or "").strip()
    if not name:
        return None
    clean_name = name.replace('"', "")
    clean_number = number.replace('"', "")
    clauses = [f'name:"{clean_name}"']
    if clean_number:
        clauses.append(f'number:"{clean_number}"')
    params = urllib.parse.urlencode({"q": " ".join(clauses), "select": "id,name,number,set,images", "pageSize": "20"})
    payload = _request(f"{API_ROOT}?{params}")
    candidates = payload.get("data")
    if not isinstance(candidates, list):
        return None
    wanted_number = _normalize_number(number)
    wanted_expansion = str(card.get("expansion") or "").casefold()
    ranked: list[tuple[int, dict[str, Any]]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict) or not _images(candidate):
            continue
        score = 0
        if str(candidate.get("name") or "").casefold() == name.casefold():
            score += 100
        if _normalize_number(str(candidate.get("number") or "")) == wanted_number:
            score += 50
        set_data = candidate.get("set")
        if isinstance(set_data, dict):
            haystack = " ".join(str(set_data.get(key) or "") for key in ("id", "name", "series", "ptcgoCode")).casefold()
            if wanted_expansion and wanted_expansion in haystack:
                score += 25
        ranked.append((score, candidate))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    return _images(ranked[0][1])


def resolve_card_art(cards: Iterable[dict[str, Any]], requested_ids: set[int] | None = None) -> dict[int, dict[str, str] | None]:
    now = int(time.time())
    cache = _load_cache()
    result: dict[int, dict[str, str] | None] = {}
    changed = False
    for card in cards:
        card_id = int(card["id"])
        if requested_ids is not None and card_id not in requested_ids:
            continue
        key = str(card_id)
        cached = cache.get(key)
        if isinstance(cached, dict) and now - int(cached.get("updatedAt", 0)) < _CACHE_TTL_SECONDS:
            art = cached.get("art")
            result[card_id] = art if isinstance(art, dict) else None
            continue
        art: dict[str, str] | None = None
        try:
            link = str(card.get("sourceLink") or "").strip()
            art = _from_link(link) if link else None
            if art is None:
                art = _query_card(card)
        except (OSError, ValueError, urllib.error.URLError):
            art = None
        cache[key] = {"updatedAt": now, "art": art}
        result[card_id] = art
        changed = True
    if changed:
        _save_cache(cache)
    return result
