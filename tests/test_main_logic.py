import configparser
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from toloka2MediaServer.main_logic import (
    add_release_by_url,
    add_torrent,
    update_release_by_name,
)
from toloka2MediaServer.models.application import Application
from toloka2MediaServer.models.operation_result import OperationResult, ResponseCode


class FakeToloka:
    def __init__(self, torrent):
        self.toloka_url = "https://example.com"
        self._torrent = torrent

    def get_torrent(self, url):
        return self._torrent

    def download_torrent(self, url):
        return b"torrent-bytes"


class FakeTorrent:
    def __init__(self, name, url="t123", author="author"):
        self.name = name
        self.url = url
        self.torrent_url = "t123.torrent"
        self.date = "2024-01-02"
        self.author = author


class FakeClient:
    def __init__(self):
        self.end_session_calls = 0
        self.added = []

    def end_session(self):
        self.end_session_calls += 1

    def add_torrent(self, torrents, category, tags, is_paused, download_dir):
        self.added.append(
            {
                "torrents": torrents,
                "category": category,
                "tags": tags,
                "is_paused": is_paused,
                "download_dir": download_dir,
            }
        )


class MainLogicTests(unittest.TestCase):
    def setUp(self):
        self.titles_config = configparser.ConfigParser()
        self.app_config = Application(default_download_dir="/downloads", default_meta="WEB")
        self.logger = SimpleNamespace(info=lambda *_args, **_kwargs: None, debug=lambda *_args, **_kwargs: None)

    @patch("toloka2MediaServer.main_logic.add")
    def test_add_release_by_url_uses_custom_code_name_and_path(self, mock_add):
        torrent = FakeTorrent("folder/Show Name (2024)")
        mock_add.return_value = OperationResult(response_code=ResponseCode.SUCCESS)
        self.titles_config["Show"] = {}
        args = SimpleNamespace(
            index=1,
            correction=0,
            url="https://example.com/t123",
            season="2",
            path="/custom",
            title="Custom Name",
            release_group=None,
            meta=None,
            code_name="Show",
            partial=True,
        )
        config = SimpleNamespace(
            args=args,
            toloka=FakeToloka(torrent),
            titles_config=self.titles_config,
            application_config=self.app_config,
            logger=self.logger,
            operation_result=OperationResult(),
        )

        result = add_release_by_url(config)

        self.assertEqual(result.response_code, ResponseCode.SUCCESS)
        passed_title = mock_add.call_args[0][1]
        self.assertEqual(passed_title.code_name, "ShowS02")
        self.assertEqual(passed_title.download_dir, "/custom")
        self.assertTrue(passed_title.is_partial_season)

    @patch("toloka2MediaServer.main_logic.add")
    def test_add_release_by_url_uses_suggested_defaults(self, mock_add):
        torrent = FakeTorrent("folder/Show Name (2024)")
        mock_add.return_value = OperationResult(response_code=ResponseCode.SUCCESS)
        args = SimpleNamespace(
            index=1,
            correction=0,
            url="https://example.com/t123",
            season="1",
            path=None,
            title="",
            release_group="RG",
            meta="WEB",
        )
        config = SimpleNamespace(
            args=args,
            toloka=FakeToloka(torrent),
            titles_config=self.titles_config,
            application_config=self.app_config,
            logger=self.logger,
            operation_result=OperationResult(),
        )

        result = add_release_by_url(config)

        self.assertEqual(result.response_code, ResponseCode.SUCCESS)
        passed_title = mock_add.call_args[0][1]
        self.assertEqual(passed_title.download_dir, "/downloads")
        self.assertEqual(passed_title.release_group, "RG")
        self.assertEqual(passed_title.meta, "WEB")

    @patch("toloka2MediaServer.main_logic.update_release")
    def test_update_release_by_name_calls_end_session(self, mock_update_release):
        mock_update_release.return_value = OperationResult(response_code=ResponseCode.SUCCESS)
        config = SimpleNamespace(
            client=FakeClient(),
            operation_result=OperationResult(),
        )

        result = update_release_by_name(config)

        self.assertEqual(result.response_code, ResponseCode.SUCCESS)
        self.assertEqual(config.client.end_session_calls, 1)

    def test_add_torrent_uses_args(self):
        torrent = FakeTorrent("folder/Show Name (2024)")
        config = SimpleNamespace(
            args=SimpleNamespace(url="t123", category="cat", tags="tag", path="/dl"),
            toloka=FakeToloka(torrent),
            client=FakeClient(),
            operation_result=OperationResult(),
        )

        result = add_torrent(config)

        self.assertEqual(result.response, b"torrent-bytes")
        self.assertEqual(
            config.client.added[0],
            {
                "torrents": b"torrent-bytes",
                "category": "cat",
                "tags": "tag",
                "is_paused": False,
                "download_dir": "/dl",
            },
        )

    def test_add_torrent_no_args(self):
        config = SimpleNamespace(
            args=None,
            toloka=FakeToloka(FakeTorrent("folder/Show Name (2024)")),
            client=FakeClient(),
            operation_result=OperationResult(),
        )

        result = add_torrent(config)

        self.assertEqual(result.response, "No args provided")


if __name__ == "__main__":
    unittest.main()
