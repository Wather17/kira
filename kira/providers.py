import time
import requests
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import shutil


class OnlineMangaProvider:
    """Fetches official manga metadata, volume-to-chapter breakdown, and covers with robust retries & fallbacks."""

    ANILIST_URL = "https://graphql.anilist.co"
    MANGADEX_URL = "https://api.mangadex.org"
    JIKAN_URL = "https://api.jikan.moe/v4"
    HEADERS = {
        "User-Agent": "KiraMangaPipeline/1.0 (https://github.com/Wather17/kira; contact: dev@kira)",
        "Accept": "application/json"
    }

    @classmethod
    def _request_with_retry(cls, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        """Execute HTTP request with exponential backoff and timeout handling."""
        kwargs.setdefault("headers", cls.HEADERS)
        kwargs.setdefault("timeout", 15)
        
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                res = requests.request(method, url, **kwargs)
                if res.status_code == 200:
                    return res
                elif res.status_code == 429:
                    # Rate limit hit -> back off
                    wait = 2.0 * attempt
                    time.sleep(wait)
                elif res.status_code in (500, 502, 503, 504):
                    time.sleep(1.0 * attempt)
                else:
                    return res
            except (requests.exceptions.RequestException, requests.exceptions.Timeout):
                if attempt < max_retries:
                    time.sleep(1.5 * attempt)
        return None

    @classmethod
    def search_manga_metadata(cls, manga_title: str) -> Optional[Dict[str, Any]]:
        """Query AniList (primary) or Jikan/MAL (fallback) for official title, author, description, and cover URL."""
        # 1. Primary: AniList GraphQL API
        query = """
        query ($search: String) {
          Media(search: $search, type: MANGA) {
            id
            title {
              english
              romaji
              native
            }
            volumes
            chapters
            description(asHtml: false)
            coverImage {
              extraLarge
              large
            }
            staff {
              edges {
                role
                node {
                  name {
                    full
                  }
                }
              }
            }
          }
        }
        """
        try:
            res = cls._request_with_retry("POST", cls.ANILIST_URL, json={"query": query, "variables": {"search": manga_title}})
            if res and res.status_code == 200:
                data = res.json().get("data", {}).get("Media")
                if data:
                    author = "Unknown"
                    staff_edges = data.get("staff", {}).get("edges", [])
                    for edge in staff_edges:
                        role = edge.get("role", "").lower()
                        if "story" in role or "art" in role or "original" in role:
                            author = edge.get("node", {}).get("name", {}).get("full", "Unknown")
                            break
                    if author == "Unknown" and staff_edges:
                        author = staff_edges[0].get("node", {}).get("name", {}).get("full", "Unknown")

                    title_dict = data.get("title", {})
                    official_title = title_dict.get("english") or title_dict.get("romaji") or manga_title

                    return {
                        "id": data.get("id"),
                        "title": official_title,
                        "romaji": title_dict.get("romaji"),
                        "author": author,
                        "description": data.get("description", ""),
                        "volumes": data.get("volumes"),
                        "chapters": data.get("chapters"),
                        "cover_url": data.get("coverImage", {}).get("extraLarge") or data.get("coverImage", {}).get("large")
                    }
        except Exception:
            pass

        # 2. Secondary Fallback: Jikan / MyAnimeList Open API
        try:
            j_res = cls._request_with_retry("GET", f"{cls.JIKAN_URL}/manga", params={"q": manga_title, "limit": 1})
            if j_res and j_res.status_code == 200:
                j_list = j_res.json().get("data", [])
                if j_list:
                    j_data = j_list[0]
                    authors = [a.get("name") for a in j_data.get("authors", [])]
                    author_str = ", ".join(authors) if authors else "Unknown"
                    return {
                        "id": j_data.get("mal_id"),
                        "title": j_data.get("title_english") or j_data.get("title") or manga_title,
                        "romaji": j_data.get("title"),
                        "author": author_str,
                        "description": j_data.get("synopsis", ""),
                        "volumes": j_data.get("volumes"),
                        "chapters": j_data.get("chapters"),
                        "cover_url": j_data.get("images", {}).get("jpg", {}).get("large_image_url")
                    }
        except Exception:
            pass

        return None

    @classmethod
    def fetch_volume_chapter_mapping(cls, manga_title: str) -> Optional[Dict[int, List[int]]]:
        """Query MangaDex API with retries to automatically fetch official volume-to-chapter mapping."""
        try:
            # 1. Search MangaDex for target manga ID
            search_res = cls._request_with_retry(
                "GET",
                f"{cls.MANGADEX_URL}/manga",
                params={"title": manga_title, "order[relevance]": "desc", "limit": 5}
            )
            if not search_res or search_res.status_code != 200:
                return None

            manga_list = search_res.json().get("data", [])
            if not manga_list:
                return None

            manga_id = manga_list[0]["id"]

            # 2. Get volume aggregate
            agg_res = cls._request_with_retry("GET", f"{cls.MANGADEX_URL}/manga/{manga_id}/aggregate")
            if not agg_res or agg_res.status_code != 200:
                return None

            volumes_data = agg_res.json().get("volumes", {})
            if not isinstance(volumes_data, dict):
                return None

            volume_mapping: Dict[int, List[int]] = {}

            for vol_num_str, vol_info in volumes_data.items():
                if not vol_num_str.isdigit():
                    continue
                vol_num = int(vol_num_str)
                chapters_dict = vol_info.get("chapters", {})

                ch_list = []
                for ch_str in chapters_dict.keys():
                    try:
                        ch_float = float(ch_str)
                        ch_int = int(ch_float)
                        if ch_int not in ch_list:
                            ch_list.append(ch_int)
                    except ValueError:
                        continue

                if ch_list:
                    volume_mapping[vol_num] = sorted(ch_list)

            return dict(sorted(volume_mapping.items())) if volume_mapping else None

        except Exception as e:
            print(f"[Kira Warning] Volume mapping lookup skipped for '{manga_title}': {e}")
            return None

    @classmethod
    def fetch_volume_covers(cls, manga_title: str) -> Dict[int, str]:
        """Fetch all official volume cover URLs from MangaDex API with retry support."""
        try:
            search_res = cls._request_with_retry(
                "GET",
                f"{cls.MANGADEX_URL}/manga",
                params={"title": manga_title, "order[relevance]": "desc", "limit": 5}
            )
            if not search_res or search_res.status_code != 200:
                return {}

            manga_list = search_res.json().get("data", [])
            if not manga_list:
                return {}

            manga_id = manga_list[0]["id"]
            cover_res = cls._request_with_retry(
                "GET",
                f"{cls.MANGADEX_URL}/cover",
                params={"manga[]": [manga_id], "limit": 100}
            )
            if not cover_res or cover_res.status_code != 200:
                return {}

            volume_covers = {}
            for c in cover_res.json().get("data", []):
                vol_str = c.get("attributes", {}).get("volume")
                file_name = c.get("attributes", {}).get("fileName")
                if vol_str and vol_str.isdigit() and file_name:
                    vol_num = int(vol_str)
                    volume_covers[vol_num] = f"https://uploads.mangadex.org/covers/{manga_id}/{file_name}"

            return volume_covers
        except Exception:
            return {}

    @classmethod
    def download_image(cls, image_url: str, output_path: Path) -> bool:
        """Download remote image URL to local file path with retry."""
        try:
            res = cls._request_with_retry("GET", image_url, stream=True)
            if res and res.status_code == 200:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    shutil.copyfileobj(res.raw, f)
                return True
        except Exception:
            pass
        return False
