import requests
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import shutil


class OnlineMangaProvider:
    """Fetches official manga metadata, volume-to-chapter breakdown, and covers from AniList & MangaDex APIs."""

    ANILIST_URL = "https://graphql.anilist.co"
    MANGADEX_URL = "https://api.mangadex.org"

    @classmethod
    def search_manga_metadata(cls, manga_title: str) -> Optional[Dict[str, Any]]:
        """Query AniList API for official title, author, description, total volumes, and cover URL."""
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
            res = requests.post(cls.ANILIST_URL, json={"query": query, "variables": {"search": manga_title}}, timeout=10)
            if res.status_code == 200:
                data = res.json().get("data", {}).get("Media")
                if data:
                    # Find Story/Art staff
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
        except Exception as e:
            print(f"[Kira Warning] Failed to query online metadata for '{manga_title}': {e}")
        return None

    @classmethod
    def fetch_volume_chapter_mapping(cls, manga_title: str) -> Optional[Dict[int, List[int]]]:
        """Query MangaDex API to automatically fetch official volume-to-chapter mapping for any manga."""
        try:
            # 1. Search MangaDex for target manga ID
            search_res = requests.get(
                f"{cls.MANGADEX_URL}/manga",
                params={"title": manga_title, "order[relevance]": "desc", "limit": 5},
                timeout=10
            )
            if search_res.status_code != 200:
                return None

            manga_list = search_res.json().get("data", [])
            if not manga_list:
                return None

            # Pick best match
            manga_id = manga_list[0]["id"]

            # 2. Get volume aggregate
            agg_res = requests.get(f"{cls.MANGADEX_URL}/manga/{manga_id}/aggregate", timeout=10)
            if agg_res.status_code != 200:
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
                        # Extract integer chapter numbers (ignoring sub-chapters for volume mapping grouping)
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
            print(f"[Kira Warning] Failed to fetch volume mapping from MangaDex for '{manga_title}': {e}")
            return None

    @classmethod
    def fetch_volume_covers(cls, manga_title: str) -> Dict[int, str]:
        """Fetch all official volume cover URLs from MangaDex API."""
        try:
            search_res = requests.get(
                f"{cls.MANGADEX_URL}/manga",
                params={"title": manga_title, "order[relevance]": "desc", "limit": 5},
                timeout=10
            )
            if search_res.status_code != 200:
                return {}

            manga_list = search_res.json().get("data", [])
            if not manga_list:
                return {}

            manga_id = manga_list[0]["id"]
            cover_res = requests.get(
                f"{cls.MANGADEX_URL}/cover",
                params={"manga[]": [manga_id], "limit": 100},
                timeout=10
            )
            if cover_res.status_code != 200:
                return {}

            volume_covers = {}
            for c in cover_res.json().get("data", []):
                vol_str = c.get("attributes", {}).get("volume")
                file_name = c.get("attributes", {}).get("fileName")
                if vol_str and vol_str.isdigit() and file_name:
                    vol_num = int(vol_str)
                    volume_covers[vol_num] = f"https://uploads.mangadex.org/covers/{manga_id}/{file_name}"

            return volume_covers
        except Exception as e:
            print(f"[Kira Warning] Failed to fetch volume covers for '{manga_title}': {e}")
            return {}

    @classmethod
    def download_image(cls, image_url: str, output_path: Path) -> bool:
        """Download remote image URL to local file path."""
        try:
            res = requests.get(image_url, stream=True, timeout=15)
            if res.status_code == 200:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    shutil.copyfileobj(res.raw, f)
                return True
        except Exception as e:
            print(f"[Kira Warning] Could not download image from {image_url}: {e}")
        return False

