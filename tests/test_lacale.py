import re
from typing import Any
from unittest.mock import patch

import pytest

from src.trackers.LACALE import LACALE


def _config(extra_tracker: dict[str, Any] | None = None) -> dict[str, Any]:
    tracker_cfg: dict[str, Any] = {
        'passkey': 'test-passkey-123',
        'announce_url': 'https://la-cale.space/announce/FAKE_PASSKEY',
    }
    if extra_tracker:
        tracker_cfg.update(extra_tracker)
    return {
        'TRACKERS': {'LACALE': tracker_cfg},
        'DEFAULT': {'tmdb_api': 'fake-tmdb-key-for-tests'},
    }


def _meta_base(**overrides: Any) -> dict[str, Any]:
    m: dict[str, Any] = {
        'category': 'MOVIE',
        'type': 'WEBDL',
        'title': 'Le Prénom',
        'year': '2012',
        'resolution': '1080p',
        'source': 'WEB',
        'audio': 'AC3',
        'video_encode': 'x264',
        'service': '',
        'tag': '-Troxy',
        'edition': '',
        'repack': '',
        '3D': '',
        'uhd': '',
        'hdr': '',
        'webdv': '',
        'part': '',
        'season': '',
        'episode': '',
        'is_disc': None,
        'search_year': '',
        'manual_year': None,
        'manual_date': None,
        'no_season': False,
        'no_year': False,
        'no_aka': False,
        'debug': False,
        'tv_pack': 0,
        'path': '',
        'name': '',
        'uuid': 'test-uuid',
        'base_dir': '/tmp',
        'overview': 'Un dîner entre amis tourne mal.',
        'poster': 'https://image.tmdb.org/poster.jpg',
        'tmdb': 1234,
        'imdb_id': 1234567,
        'original_language': 'fr',
        'image_list': [],
        'bdinfo': None,
        'mediainfo': {
            'media': {
                'track': []
            }
        },
        'tracker_status': {'LACALE': {}},
        'has_encode_settings': False,
    }
    m.update(overrides)
    return m


def _audio_track(lang: str = 'fr', **kw: Any) -> dict[str, Any]:
    t: dict[str, Any] = {'@type': 'Audio', 'Language': lang}
    t.update(kw)
    return t


class TestLACALEInit:
    def test_init_with_passkey(self):
        cfg = _config()
        tracker = LACALE(cfg)
        assert tracker.tracker == "LACALE"
        assert tracker.source_flag == "lacale"
        assert tracker.passkey == "test-passkey-123"
        assert tracker.base_url == "https://la-cale.space"
        assert tracker.upload_url == "https://la-cale.space/api/external/upload"

    def test_source_flag_is_lacale(self):
        tracker = LACALE(_config())
        assert tracker.source_flag == "lacale"


class TestLACALECategory:
    def test_category_movie_webdl(self):
        tracker = LACALE(_config())
        cat_id, cat_slug, sub_slug = tracker._get_category(_meta_base(type='WEBDL'))
        assert cat_id == "cmjoyv2cd00027eryreyk39gz"
        assert cat_slug == "films"
        assert sub_slug == "films-webdl"

    def test_category_movie_bluray(self):
        tracker = LACALE(_config())
        cat_id, cat_slug, sub_slug = tracker._get_category(_meta_base(type='BluRay'))
        assert cat_id == "cmjoyv2cd00027eryreyk39gz"
        assert cat_slug == "films"
        assert sub_slug == "films-bluray"

    def test_category_movie_encode(self):
        tracker = LACALE(_config())
        cat_id, cat_slug, sub_slug = tracker._get_category(_meta_base(type='ENCODE'))
        assert cat_id == "cmjoyv2cd00027eryreyk39gz"
        assert cat_slug == "films"
        assert sub_slug == "films-bluray"

    def test_category_tv_webdl(self):
        tracker = LACALE(_config())
        meta = _meta_base(category='TV', type='WEBDL')
        cat_id, cat_slug, sub_slug = tracker._get_category(meta)
        assert cat_id == "cmjoyv2cd0002j6ry7k0e1tav"
        assert cat_slug == "series"
        assert sub_slug == "series-webdl"

    def test_category_default_movie(self):
        tracker = LACALE(_config())
        cat_id, cat_slug, sub_slug = tracker._get_category(_meta_base(type=''))
        assert cat_slug == "films"


class TestLACALEFormatName:
    def test_format_name_title_casing(self):
        tracker = LACALE(_config())
        raw = "Le Prénom 2012 VFF 1080p WEB x264 AC3-TAG"
        result = tracker._format_name(raw)
        name = result['name']
        assert 'Le' in name or 'Prénom' in name

    def test_format_name_dd_to_ac3(self):
        tracker = LACALE(_config())
        raw = "Test 2024 1080p WEB DD 5.1 x264"
        result = tracker._format_name(raw)
        assert '.AC3.' in result['name'] or result['name'].endswith('.AC3')

    def test_format_name_dts_hd_ma(self):
        tracker = LACALE(_config())
        raw = "Test 2024 1080p BluRay DTS-HD MA 5.1 x264"
        result = tracker._format_name(raw)
        assert '.DTS.HD.MA.' in result['name']

    def test_format_name_atmos_ordering(self):
        tracker = LACALE(_config())
        raw = "Test 2024 1080p WEB DDP.5.1.ATMOS x265"
        result = tracker._format_name(raw)
        assert '.DDP.ATMOS.5.1.' in result['name']


class TestLACALEPasskey:
    def test_get_passkey_valid(self):
        tracker = LACALE(_config())
        pk = tracker._get_passkey()
        assert pk == "test-passkey-123"


class TestLACALEGetId:
    def test_get_id(self):
        tracker_id, name = LACALE._get_id()
        assert tracker_id == "LACALE"
        assert name == "La-Cale"


class TestLACALEInheritance:
    def test_inherits_from_french_tracker_mixin(self):
        from src.trackers.FRENCH import FrenchTrackerMixin
        assert issubclass(LACALE, FrenchTrackerMixin)

    def test_has_build_audio_string(self):
        tracker = LACALE(_config())
        assert hasattr(tracker, '_build_audio_string')
        assert callable(getattr(tracker, '_build_audio_string'))

    def test_has_get_french_title(self):
        tracker = LACALE(_config())
        assert hasattr(tracker, '_get_french_title')
        assert callable(getattr(tracker, '_get_french_title'))


class TestLACALEConfig:
    def test_web_label_is_web(self):
        tracker = LACALE(_config())
        assert tracker.WEB_LABEL == "WEB"

    def test_include_service_in_name_false(self):
        tracker = LACALE(_config())
        assert tracker.INCLUDE_SERVICE_IN_NAME is False

    def test_uhd_only_for_remux_disc_true(self):
        tracker = LACALE(_config())
        assert tracker.UHD_ONLY_FOR_REMUX_DISC is True

    def test_prefer_original_title_true(self):
        tracker = LACALE(_config())
        assert tracker.PREFER_ORIGINAL_TITLE is True