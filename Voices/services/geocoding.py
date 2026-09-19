import hashlib
from typing import Iterable

import requests
from django.core.cache import cache


KENYA_BOUNDS = {
    "lat_min": -5.2,
    "lat_max": 5.5,
    "lon_min": 33.5,
    "lon_max": 42.0,
}

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "VAV/1.0 (resource geocoding)"
DEFAULT_CACHE_SECONDS = 60 * 60 * 24 * 30


def _is_in_kenya_bounds(lat: float, lon: float) -> bool:
    return (
        KENYA_BOUNDS["lat_min"] <= lat <= KENYA_BOUNDS["lat_max"]
        and KENYA_BOUNDS["lon_min"] <= lon <= KENYA_BOUNDS["lon_max"]
    )


def _normalize_text(value: str | None) -> str:
    return (value or "").strip().lower()


def _county_token(default_county: str) -> str:
    token = _normalize_text(default_county).replace(" county", "").strip()
    return token


def _has_explicit_county(*parts: str | None) -> bool:
    return any(" county" in _normalize_text(part) for part in parts)


def _build_queries(name: str | None, location: str | None, address: str | None, default_county: str) -> list[str]:
    name_value = (name or "").strip()
    location_value = (location or "").strip()
    address_value = (address or "").strip()

    core_parts = [part for part in [name_value, address_value, location_value] if part]
    base = ", ".join(core_parts)
    if not base and not name_value:
        return []

    queries: list[str] = []

    def enrich(query: str) -> str:
        q = query.strip()
        lowered = q.lower()
        if " county" not in lowered:
            q = f"{q}, {default_county}"
            lowered = q.lower()
        if "kenya" not in lowered:
            q = f"{q}, Kenya"
        return q

    if name_value:
        queries.append(enrich(name_value))
    if name_value and location_value:
        queries.append(enrich(f"{name_value}, {location_value}"))
    if name_value and address_value:
        queries.append(enrich(f"{name_value}, {address_value}"))
    if base:
        queries.append(enrich(base))

    unique_queries = []
    seen = set()
    for query in queries:
        key = query.lower()
        if key not in seen:
            seen.add(key)
            unique_queries.append(query)
    return unique_queries


def _cache_key_for_query(query: str) -> str:
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()
    return f"geo:v1:{digest}"


def _token_match_score(candidate_text: str, tokens: Iterable[str]) -> int:
    score = 0
    for token in tokens:
        token_clean = _normalize_text(token)
        if token_clean and token_clean in candidate_text:
            score += 1
    return score


def _pick_best_result(
    payload: list[dict],
    *,
    name: str | None,
    location: str | None,
    address: str | None,
    default_county: str,
    strict_county: bool,
) -> dict | None:
    if not payload:
        return None

    best = None
    best_score = -1
    name_tokens = [name] if name else []
    location_tokens = [location] if location else []
    address_tokens = [address] if address else []
    default_county_token = _county_token(default_county)

    for item in payload:
        try:
            lat = float(item.get("lat"))
            lon = float(item.get("lon"))
        except (TypeError, ValueError):
            continue

        if not _is_in_kenya_bounds(lat, lon):
            continue

        display = _normalize_text(item.get("display_name", ""))
        address_block = item.get("address") or {}
        country_code = _normalize_text(address_block.get("country_code", ""))
        if country_code and country_code != "ke":
            continue

        county_parts = [
            address_block.get("county"),
            address_block.get("state_district"),
            address_block.get("state"),
            address_block.get("city"),
            address_block.get("town"),
            address_block.get("village"),
        ]
        county_blob = _normalize_text(" ".join([str(value) for value in county_parts if value]))

        if strict_county and default_county_token and default_county_token not in county_blob and default_county_token not in display:
            continue

        score = 0
        score += _token_match_score(display, name_tokens) * 4
        score += _token_match_score(display, location_tokens) * 3
        score += _token_match_score(display, address_tokens) * 2

        if default_county_token and (default_county_token in county_blob or default_county_token in display):
            score += 8

        if address_block.get("county"):
            score += 1

        if score > best_score:
            best_score = score
            best = {
                "latitude": lat,
                "longitude": lon,
                "display_name": item.get("display_name", ""),
                "county": address_block.get("county"),
                "raw": item,
            }

    return best


def geocode_kenya_resource(*, name: str | None, location: str | None, address: str | None, default_county: str = "Nakuru County") -> dict | None:
    queries = _build_queries(name, location, address, default_county=default_county)
    if not queries:
        return None

    strict_county = not _has_explicit_county(name, location, address)

    for query in queries:
        key = _cache_key_for_query(query)
        cached = cache.get(key)
        if cached is not None:
            if cached == "MISS":
                continue
            return cached

        try:
            response = requests.get(
                NOMINATIM_URL,
                params={
                    "format": "json",
                    "q": query,
                    "limit": 5,
                    "countrycodes": "ke",
                    "addressdetails": 1,
                    "viewbox": f"{KENYA_BOUNDS['lon_min']},{KENYA_BOUNDS['lat_max']},{KENYA_BOUNDS['lon_max']},{KENYA_BOUNDS['lat_min']}",
                    "bounded": 1,
                },
                headers={"User-Agent": USER_AGENT},
                timeout=5,
            )
            if not response.ok:
                cache.set(key, "MISS", 60 * 10)
                continue

            payload = response.json()
            result = _pick_best_result(
                payload,
                name=name,
                location=location,
                address=address,
                default_county=default_county,
                strict_county=strict_county,
            )

            if result:
                cache.set(key, result, DEFAULT_CACHE_SECONDS)
                return result

            cache.set(key, "MISS", 60 * 10)
        except Exception:
            continue

    return None
