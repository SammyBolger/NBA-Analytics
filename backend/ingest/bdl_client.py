import os
import time
import json
import logging
from datetime import datetime, timedelta
from functools import wraps
import httpx

logger = logging.getLogger(__name__)

BDL_BASE_URL = "https://api.balldontlie.io/v1"

_cache = {}
_cache_ttl = {}
CACHE_TTL_SECONDS = 60

_last_request_time = 0
MIN_REQUEST_INTERVAL = 0.6


def get_api_key():
    return os.environ.get("BDL_API_KEY", "")


def _rate_limit():
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


def _get_cached(key):
    if key in _cache and key in _cache_ttl:
        if time.time() - _cache_ttl[key] < CACHE_TTL_SECONDS:
            return _cache[key]
    return None


def _set_cache(key, data):
    _cache[key] = data
    _cache_ttl[key] = time.time()


def _request_with_retry(url, params=None, max_retries=3):
    api_key = get_api_key()
    if not api_key:
        logger.warning("BDL_API_KEY not set")
        return None

    headers = {"Authorization": api_key}
    cache_key = f"{url}:{json.dumps(params or {}, sort_keys=True)}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    for attempt in range(max_retries):
        try:
            _rate_limit()
            with httpx.Client(timeout=15) as client:
                resp = client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    _set_cache(cache_key, data)
                    return data
                elif resp.status_code == 429:
                    wait = (2 ** attempt) * 2
                    logger.warning(f"Rate limited, waiting {wait}s")
                    time.sleep(wait)
                else:
                    logger.error(f"BDL API error {resp.status_code}: {resp.text[:200]}")
                    return None
        except Exception as e:
            logger.error(f"BDL request error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    return None


def fetch_todays_games(date_str=None):
    if not date_str:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
    url = f"{BDL_BASE_URL}/games"
    params = {"dates[]": date_str, "per_page": 50}
    data = _request_with_retry(url, params)
    if data:
        return data.get("data", [])
    return []


def fetch_games_for_dates(date_strs):
    all_games = []
    seen_ids = set()
    for d in date_strs:
        games = fetch_todays_games(d)
        for g in games:
            if g["id"] not in seen_ids:
                seen_ids.add(g["id"])
                all_games.append(g)
    return all_games


def fetch_recent_completed_games(season=2025, pages=3):
    all_games = []
    for page in range(1, pages + 1):
        data = fetch_season_games(season, page)
        if not data:
            break
        games = data.get("data", [])
        for g in games:
            s = (g.get("status") or "").lower()
            if s == "final" or "final" in s:
                all_games.append(g)
        meta = data.get("meta", {})
        if not meta.get("next_cursor"):
            break
    return all_games


def fetch_all_season_games(season=2025, max_pages=30):
    all_games = []
    cursor = 1
    for _ in range(max_pages):
        data = fetch_season_games(season, cursor)
        if not data:
            break
        games = data.get("data", [])
        all_games.extend(games)
        meta = data.get("meta", {})
        next_cursor = meta.get("next_cursor")
        if not next_cursor:
            break
        cursor = next_cursor
    return all_games


def fetch_games_for_date_range(start_date, end_date):
    from datetime import datetime as dt, timedelta
    all_games = []
    current = dt.strptime(start_date, "%Y-%m-%d")
    end = dt.strptime(end_date, "%Y-%m-%d")
    batch = []
    while current <= end:
        batch.append(current.strftime("%Y-%m-%d"))
        if len(batch) >= 7:
            games = fetch_games_for_dates(batch)
            all_games.extend(games)
            batch = []
        current += timedelta(days=1)
    if batch:
        games = fetch_games_for_dates(batch)
        all_games.extend(games)
    return all_games


def fetch_game_stats(game_id):
    url = f"{BDL_BASE_URL}/stats"
    params = {"game_ids[]": game_id, "per_page": 100}
    data = _request_with_retry(url, params)
    if data:
        return data.get("data", [])
    return []


def fetch_season_games(season=2024, page=1):
    url = f"{BDL_BASE_URL}/games"
    params = {"seasons[]": season, "per_page": 100, "cursor": page}
    data = _request_with_retry(url, params)
    return data


def fetch_players(search=None, page=1):
    url = f"{BDL_BASE_URL}/players"
    params = {"per_page": 100, "cursor": page}
    if search:
        params["search"] = search
    data = _request_with_retry(url, params)
    if data:
        return data.get("data", [])
    return []


def fetch_season_averages(season=2025, player_ids=None):
    url = f"{BDL_BASE_URL}/season_averages"
    params = {"season": season}
    if player_ids:
        for pid in player_ids:
            params.setdefault("player_ids[]", [])
        params = {"season": season}
        for pid in player_ids:
            params[f"player_ids[]"] = player_ids
        params = [("season", season)] + [("player_ids[]", pid) for pid in player_ids]
        cache_key = f"{url}:{json.dumps(params, sort_keys=True, default=str)}"
        cached = _get_cached(cache_key)
        if cached is not None:
            return cached
        api_key = get_api_key()
        if not api_key:
            return []
        headers = {"Authorization": api_key}
        _rate_limit()
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    _set_cache(cache_key, data)
                    return data.get("data", [])
                else:
                    logger.error(f"Season averages error {resp.status_code}")
                    return []
        except Exception as e:
            logger.error(f"Season averages request error: {e}")
            return []
    return []


def fetch_players_by_team(team_id):
    url = f"{BDL_BASE_URL}/players"
    params = {"per_page": 100, "cursor": 1, "team_ids[]": team_id}
    data = _request_with_retry(url, params)
    if data:
        return data.get("data", [])
    return []


def has_api_key():
    return bool(get_api_key())
