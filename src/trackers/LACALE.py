import asyncio
import os
import re
from typing import Any, Optional

import aiofiles
import httpx

from src.console import console
from src.tmdb import TmdbManager
from src.trackers.COMMON import COMMON
from src.trackers.FRENCH import FrenchTrackerMixin

Meta = dict[str, Any]
Config = dict[str, Any]


class LACALE(FrenchTrackerMixin):
    WEB_LABEL: str = "WEB"
    INCLUDE_SERVICE_IN_NAME: bool = False
    UHD_ONLY_FOR_REMUX_DISC: bool = True
    PREFER_ORIGINAL_TITLE: bool = True

    def __init__(self, config: Config) -> None:
        self.config: Config = config
        self.tracker: str = "LACALE"
        self.source_flag: str = "lacale"
        self.base_url: str = "https://la-cale.space"
        self.upload_url: str = "https://la-cale.space/api/external/upload"
        self.api_url: str = "https://la-cale.space/api/external"
        self.torrent_url: str = "https://la-cale.space/torrents/"
        tracker_cfg = self.config["TRACKERS"].get(self.tracker, {})
        self.passkey: str = str(tracker_cfg.get("passkey", "")).strip()
        self.tmdb_manager = TmdbManager(config)
        self.banned_groups: list[str] = ["k0RE"]

    def _get_passkey(self) -> Optional[str]:
        if not self.passkey:
            console.print("[red]LACALE: No passkey configured.[/red]")
            return None
        return self.passkey

    def _get_category(self, meta: Meta) -> tuple[str, str, str]:
        category = meta.get("category", "MOVIE").upper()
        type_val = meta.get("type", "").upper()

        CATEGORIES = {
            ("MOVIE", "BluRay"): ("cmjoyv2cd00027eryreyk39gz", "films", "films-bluray"),
            ("MOVIE", "REMUX"): ("cmjoyv2cd00027eryreyk39gz", "films", "films-bluray"),
            ("MOVIE", "ENCODE"): ("cmjoyv2cd00027eryreyk39gz", "films", "films-bluray"),
            ("MOVIE", "WEBDL"): ("cmjoyv2cd00027eryreyk39gz", "films", "films-webdl"),
            ("MOVIE", "WEBRIP"): ("cmjoyv2cd00027eryreyk39gz", "films", "films-webrip"),
            ("MOVIE", "HDTV"): ("cmjoyv2cd00027eryreyk39gz", "films", "films-hdtv"),
            ("MOVIE", "DVDRIP"): ("cmjoyv2cd00027eryreyk39gz", "films", "films-dvdrip"),
            ("MOVIE", "DVD"): ("cmjoyv2cd00027eryreyk39gz", "films", "films-dvd"),
            ("MOVIE", "HDDVD"): ("cmjoyv2cd00027eryreyk39gz", "films", "films-hddvd"),
            ("MOVIE", "DISC"): ("cmjoyv2cd00027eryreyk39gz", "films", "films-bluray"),
            ("MOVIE", ""): ("cmjoyv2cd00027eryreyk39gz", "films", "films-bluray"),
            ("TV", "BluRay"): ("cmjoyv2cd0002j6ry7k0e1tav", "series", "series-bluray"),
            ("TV", "REMUX"): ("cmjoyv2cd0002j6ry7k0e1tav", "series", "series-bluray"),
            ("TV", "ENCODE"): ("cmjoyv2cd0002j6ry7k0e1tav", "series", "series-bluray"),
            ("TV", "WEBDL"): ("cmjoyv2cd0002j6ry7k0e1tav", "series", "series-webdl"),
            ("TV", "WEBRIP"): ("cmjoyv2cd0002j6ry7k0e1tav", "series", "series-webrip"),
            ("TV", "HDTV"): ("cmjoyv2cd0002j6ry7k0e1tav", "series", "series-hdtv"),
            ("TV", "DVDRIP"): ("cmjoyv2cd0002j6ry7k0e1tav", "series", "series-dvdrip"),
            ("TV", "DVD"): ("cmjoyv2cd0002j6ry7k0e1tav", "series", "series-dvd"),
            ("TV", "DISC"): ("cmjoyv2cd0002j6ry7k0e1tav", "series", "series-bluray"),
            ("TV", ""): ("cmjoyv2cd0002j6ry7k0e1tav", "series", "series-webdl"),
        }

        key = (category, type_val)
        return CATEGORIES.get(key, CATEGORIES.get((category, ""), ("cmjoyv2cd00027eryreyk39gz", "films", "films-bluray")))

    def _format_name(self, raw_name: str) -> dict[str, str]:
        result = super()._format_name(raw_name)
        dot_name = result["name"]

        dot_name = re.sub(r"\.DD\.", ".AC3.", dot_name)
        dot_name = re.sub(r"\.TrueHD\.", ".TRUEHD.", dot_name, flags=re.IGNORECASE)
        dot_name = re.sub(r"\.TrueHD$", ".TRUEHD", dot_name, flags=re.IGNORECASE)
        dot_name = dot_name.replace(".DTS-HD.MA.", ".DTS.HD.MA.")
        dot_name = dot_name.replace(".DTS-HD.HRA.", ".DTS.HD.HRA.")
        dot_name = dot_name.replace(".DTS:X.", ".DTS.X.")
        dot_name = dot_name.replace(".DTSX.", ".DTS.X.")
        dot_name = re.sub(r"\.Atmos\.", ".ATMOS.", dot_name, flags=re.IGNORECASE)
        dot_name = re.sub(r"\.Atmos$", ".ATMOS", dot_name, flags=re.IGNORECASE)
        dot_name = re.sub(r"\.(DDP|AC3|EAC3|DTS|TRUEHD|FLAC|AAC|LPCM|DTS\.HD\.MA|DTS\.HD\.HRA|DTS\.X)\.(\d\.\d)\.ATMOS([.-])", r".\1.ATMOS.\2\3", dot_name, flags=re.IGNORECASE)
        dot_name = re.sub(r"\.ATMOS\.(DDP|AC3|EAC3|DTS|TRUEHD|FLAC|AAC|LPCM|DTS\.HD\.MA|DTS\.HD\.HRA|DTS\.X)\.(\d\.\d)([.-])", r".\1.ATMOS.\2\3", dot_name, flags=re.IGNORECASE)

        parts = dot_name.split(".")
        title_end = 0
        for j, part in enumerate(parts):
            if re.match(r"^\d{4}$", part) or re.match(r"^S\d{2}", part, re.IGNORECASE):
                title_end = j
                break
        else:
            title_end = len(parts)

        for k in range(title_end):
            if parts[k] == "x":
                continue
            parts[k] = parts[k].capitalize()

        result["name"] = ".".join(parts)
        return result

    async def _build_description(self, meta: Meta) -> str:
        parts: list[str] = []
        name = meta.get("uuid", meta.get("name", ""))
        parts.append(f"[b]{name}[/b]\n")

        overview = meta.get("overview", "")
        if overview:
            parts.append(f"\n{overview[:500]}")

        return "\n".join(parts)

    def _build_tags(self, meta: Meta, language_tag: str) -> str:
        return ""

    async def upload(self, meta: Meta, _disctype: str) -> bool:
        common = COMMON(config=self.config)
        await common.create_torrent_for_upload(meta, self.tracker, self.source_flag)

        name_result = await self.get_name(meta)
        title = name_result.get("name", "") if isinstance(name_result, dict) else str(name_result)

        passkey = self._get_passkey()
        if not passkey:
            console.print("[red]LACALE: No passkey configured.[/red]")
            meta["tracker_status"][self.tracker]["status_message"] = "No passkey configured"
            return False

        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        async with aiofiles.open(torrent_path, "rb") as f:
            torrent_bytes = await f.read()

        nfo_bytes = b""
        nfo_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/{meta['uuid']}.nfo"
        if os.path.exists(nfo_path):
            async with aiofiles.open(nfo_path, "rb") as f:
                nfo_bytes = await f.read()

        description = await self._build_description(meta)

        category_id, _, _ = self._get_category(meta)

        tmdb_id = str(meta.get("tmdb", ""))
        tmdb_type = "MOVIE" if meta.get("category", "").upper() != "TV" else "TV"

        cover_url = meta.get("poster", "")

        files: dict[str, tuple[str, bytes, str]] = {
            "file": (f"{title}.torrent", torrent_bytes, "application/x-bittorrent"),
        }

        if nfo_bytes:
            files["nfoFile"] = ("template.nfo", nfo_bytes, "text/plain")

        data: dict[str, Any] = {
            "title": title,
            "description": description,
            "categoryId": category_id,
        }

        if tmdb_id:
            data["tmdbId"] = tmdb_id
            data["tmdbType"] = tmdb_type

        if cover_url:
            data["coverUrl"] = cover_url

        upload_url = f"{self.upload_url}?passkey={passkey}"

        headers: dict[str, str] = {
            "Accept": "*/*",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/upload",
        }

        try:
            if not meta["debug"]:
                max_retries = 2
                retry_delay = 5
                timeout = 40.0

                for attempt in range(max_retries):
                    try:
                        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                            response = await client.post(
                                url=upload_url,
                                files=files,
                                data=data,
                                headers=headers,
                            )

                        if response.status_code in (200, 201):
                            result = response.json()
                            if result.get("success"):
                                torrent_id = result.get("id", "")
                                link = result.get("link", f"{self.torrent_url}{torrent_id}")
                                console.print(f"[green]LACALE: Upload successful! {link}[/green]")
                                meta["tracker_status"][self.tracker]["uploaded"] = True
                                meta["tracker_status"][self.tracker]["link"] = link
                                meta["tracker_status"][self.tracker]["torrent_id"] = torrent_id
                                return True
                            else:
                                console.print(f"[red]LACALE: Upload failed: {result}[/red]")
                                return False
                        elif response.status_code == 429:
                            console.print(f"[yellow]LACALE: Rate limited (attempt {attempt + 1}/{max_retries}). Retrying in {retry_delay}s...[/yellow]")
                            await asyncio.sleep(retry_delay)
                            continue
                        else:
                            detail = response.text[:500]
                            console.print(f"[red]LACALE: Upload failed (HTTP {response.status_code}): {detail}[/red]")
                            meta["tracker_status"][self.tracker]["status_message"] = f"HTTP {response.status_code}: {detail[:100]}"
                            return False

                    except httpx.TimeoutException:
                        if attempt < max_retries - 1:
                            console.print(f"[yellow]LACALE: Timeout (attempt {attempt + 1}/{max_retries}). Retrying...[/yellow]")
                            await asyncio.sleep(retry_delay)
                            continue
                        console.print("[red]LACALE: Upload timed out after all retries.[/red]")
                        meta["tracker_status"][self.tracker]["status_message"] = "Timeout"
                        return False
                    except Exception as e:
                        console.print(f"[red]LACALE: Upload error: {e}[/red]")
                        meta["tracker_status"][self.tracker]["status_message"] = str(e)[:100]
                        return False

                console.print("[red]LACALE: Upload failed after max retries.[/red]")
                return False

            else:
                console.print(f"[cyan]LACALE: Debug mode - would upload:[/cyan]")
                console.print(f"  Title: {title}")
                console.print(f"  Category: {category_id}")
                console.print(f"  TMDB: {tmdb_id} ({tmdb_type})")
                meta["tracker_status"][self.tracker]["uploaded"] = True
                return True

        except Exception as e:
            console.print(f"[red]LACALE: Unexpected error: {e}[/red]")
            meta["tracker_status"][self.tracker]["status_message"] = str(e)[:100]
            return False

    @staticmethod
    def _get_id() -> tuple[str, str]:
        return "LACALE", "La-Cale"