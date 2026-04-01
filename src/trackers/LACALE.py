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
    """La-Cale tracker - French private tracker.
    
    API Status: Beta - Upload endpoint may require specific permissions.
    Auth: X-Api-Key header (recommended) or ?apikey= query param
    Docs: https://la-cale.space/api/external/docs
    """
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
            ("TV", "BluRay"): ("cmjoyv2dg00067ery8m6c3q8h", "series", "series-bluray"),
            ("TV", "REMUX"): ("cmjoyv2dg00067ery8m6c3q8h", "series", "series-bluray"),
            ("TV", "ENCODE"): ("cmjoyv2dg00067ery8m6c3q8h", "series", "series-bluray"),
            ("TV", "WEBDL"): ("cmjoyv2dg00067ery8m6c3q8h", "series", "series-webdl"),
            ("TV", "WEBRIP"): ("cmjoyv2dg00067ery8m6c3q8h", "series", "series-webrip"),
            ("TV", "HDTV"): ("cmjoyv2dg00067ery8m6c3q8h", "series", "series-hdtv"),
            ("TV", "DVDRIP"): ("cmjoyv2dg00067ery8m6c3q8h", "series", "series-dvdrip"),
            ("TV", "DVD"): ("cmjoyv2dg00067ery8m6c3q8h", "series", "series-dvd"),
            ("TV", "DISC"): ("cmjoyv2dg00067ery8m6c3q8h", "series", "series-bluray"),
            ("TV", ""): ("cmjoyv2dg00067ery8m6c3q8h", "series", "series-webdl"),
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
        """Build tag slugs for La-Cale based on Releasarr's mapping."""
        tags: list[str] = []

        # Quality / Resolution
        res = meta.get("resolution", "")
        quality_map = {
            "2160": "2160p-4k",
            "1080": "1080p-full-hd",
            "720": "720p-hd",
            "480": "sd",
        }
        for key, val in quality_map.items():
            if key in res:
                tags.append(val)
                break

        # Source
        type_val = meta.get("type", "").upper()
        source = meta.get("source", "")

        source_map = {
            "REMUX": "remux",
            "BluRay": "bluray",
            "DISC": "full-disc",
            "WEBDL": "web-dl",
            "WEBRIP": "webrip",
            "DVDRIP": "dvdrip",
            "HDTV": "tv",
        }

        if type_val == "REMUX":
            tags.append("remux")
        if source in ("BluRay",) or type_val == "DISC":
            tags.append("bluray")
        if type_val == "WEBDL":
            tags.append("web-dl")
        elif type_val == "WEBRIP":
            tags.append("webrip")
        elif type_val == "HDTV":
            tags.append("tv")
        elif type_val == "DVDRIP":
            tags.append("dvdrip")

        # HDR / DV
        hdr = meta.get("hdr", "")
        if "HDR10+" in hdr or "HDR10Plus" in hdr:
            tags.append("hdr10")
        elif "DV" in hdr or meta.get("dv"):
            tags.append("dolby-vision")
        elif "HDR" in hdr:
            tags.append("hdr")

        # Video codec
        codec = meta.get("video_codec", "") or meta.get("video_encode", "")
        codec_upper = codec.upper().replace(".", "").replace("-", "")
        if "AV1" in codec_upper:
            tags.append("av1")
        elif "X265" in codec_upper or "H265" in codec_upper or "HEVC" in codec_upper:
            tags.append("hevc-h265-x265")
        elif "X264" in codec_upper or "H264" in codec_upper or "AVC" in codec_upper:
            tags.append("avc-h264-x264")

        # Audio codec
        audio = meta.get("audio", "")
        audio_upper = audio.upper().replace(".", "").replace("-", "")
        if "AAC" in audio_upper:
            tags.append("aac")
        elif "AC3" in audio_upper:
            tags.append("ac3")
        elif "EAC3" in audio_upper:
            tags.append("e-ac3")
        elif "DTS-HD.MA" in audio_upper or "DTSHDMA" in audio_upper:
            tags.append("dts-hd-ma")
        elif "DTS-HD.HRA" in audio_upper:
            tags.append("dts-hd-hr")
        elif "DTS-X" in audio_upper or "DTSX" in audio_upper:
            tags.append("dts-x")
        elif "TRUEHD" in audio_upper:
            tags.append("truehd")
        elif "FLAC" in audio_upper:
            tags.append("flac")

        # Atmos
        if "ATMOS" in audio_upper:
            tags.append("truehd-atmos")

        # Container
        container = meta.get("container", "").upper()
        container_map = {"MKV": "mkv", "MP4": "mp4", "AVI": "avi", "ISO": "iso"}
        if container in container_map:
            tags.append(container_map[container])

        # Language tag
        if language_tag:
            lang_map = {
                "MULTI": "multi",
                "VFF": "french",
                "VFQ": "vfq",
                "VF2": "vf2",
                "VOF": "vff",
                "VOSTFR": "vostfr",
                "VO": "english",
                "FRENCH": "french",
                "ENGLISH": "english",
            }
            # Normalize MULTI.X to just MULTI
            primary_lang = language_tag.split(".")[0]
            if primary_lang in lang_map:
                tags.append(lang_map[primary_lang])

        return ",".join(tags)

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

        language_tag = meta.get("release_language", "")
        tags = self._build_tags(meta, language_tag)

        files: dict[str, tuple[str, bytes, str]] = {
            "file": (f"{title}.torrent", torrent_bytes, "application/x-bittorrent"),
        }

        if nfo_bytes:
            files["nfoFile"] = ("template.nfo", nfo_bytes, "text/plain")

        data: dict[str, Any] = {
            "title": title,
            "description": description,
            "categoryId": category_id,
            "tags": tags,
        }

        if tmdb_id:
            data["tmdbId"] = tmdb_id
            data["tmdbType"] = tmdb_type

        if cover_url:
            data["coverUrl"] = cover_url

        upload_url = f"{self.upload_url}"

        headers: dict[str, str] = {
            "Accept": "*/*",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/upload",
            "X-Api-Key": passkey,
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