import logging
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from toloka2MediaServer.models.application import Application
from toloka2MediaServer.models.operation_result import OperationResult, ResponseCode
from toloka2MediaServer.models.title import Title
from toloka2MediaServer.utils import torrent_processor


class FakeFile:
    def __init__(self, name):
        self.name = name


class FakeTorrent:
    def __init__(self, name, url, torrent_url, date, author="author"):
        self.name = name
        self.url = url
        self.torrent_url = torrent_url
        self.date = date
        self.author = author


class FakeTorrentInfo:
    def __init__(self, torrent_hash):
        self.hash = torrent_hash


class FakeQbitClient:
    def __init__(self, files):
        self._files = files
        self._added_hash = None
        self._renamed_files = []
        self._renamed_folders = []
        self._renamed_torrents = []
        self._resumed = []
        self._deleted = []
        self._recheck_calls = []
        self._end_session_called = 0
        self.tags = "tag"
        self.category = "cat"
        self.recheck_success = True

    @property
    def renamed_files(self):
        return self._renamed_files

    @property
    def renamed_folders(self):
        return self._renamed_folders

    @property
    def renamed_torrents(self):
        return self._renamed_torrents

    @property
    def deleted(self):
        return self._deleted

    @property
    def recheck_calls(self):
        return self._recheck_calls

    def add_torrent(self, torrents, category, tags, is_paused, download_dir):
        self._added_hash = "hash123"
        return self._added_hash

    def get_torrent_info(
        self, status_filter, category, tags, sort, reverse, torrent_hash
    ):
        if torrent_hash != self._added_hash:
            return []
        return [FakeTorrentInfo(torrent_hash)]

    def get_files(self, torrent_hash):
        return self._files

    def rename_file(self, torrent_hash, old_path, new_path):
        self._renamed_files.append((old_path, new_path))

    def rename_folder(self, torrent_hash, old_path, new_path):
        self._renamed_folders.append((old_path, new_path))

    def rename_torrent(self, torrent_hash, new_torrent_name):
        self._renamed_torrents.append(new_torrent_name)

    def resume_torrent(self, torrent_hashes):
        self._resumed.append(torrent_hashes)
        return True

    def delete_torrent(self, delete_files, torrent_hashes):
        self._deleted.append((delete_files, torrent_hashes))
        return True

    def recheck_torrent(self, torrent_hashes):
        self._recheck_calls.append(torrent_hashes)

    def recheck_and_resume_async(self, torrent_hash, on_complete):
        if self.recheck_success:
            return True, "Recheck scheduled"
        return False, "Recheck failed"

    def end_session(self, torrent_hashes=None):
        self._end_session_called += 1


class FakeTransmissionTorrentInfo:
    def __init__(self, hash_string, files):
        self.hash_string = hash_string
        self._files = files

    def get_files(self):
        return self._files


class FakeTransmissionClient:
    def __init__(self, files):
        self._files = files
        self._renamed_files = []
        self._renamed_folders = []
        self._renamed_torrents = []
        self._resumed = []
        self._rechecked = []
        self._deleted = []
        self.tags = "tag"
        self.category = "cat"

    @property
    def renamed_files(self):
        return self._renamed_files

    @property
    def renamed_folders(self):
        return self._renamed_folders

    @property
    def renamed_torrents(self):
        return self._renamed_torrents

    @property
    def rechecked(self):
        return self._rechecked

    def add_torrent(self, torrents, category, tags, is_paused, download_dir):
        return "transmission-id"

    def get_torrent_info(
        self, status_filter, category, tags, sort, reverse, torrent_hash
    ):
        return FakeTransmissionTorrentInfo("transmission-hash", self._files)

    def get_files(self, torrent_hash):
        return self._files

    def rename_file(self, torrent_hash, old_path, new_path):
        self._renamed_files.append((old_path, new_path))

    def rename_folder(self, torrent_hash, old_path, new_path):
        self._renamed_folders.append((old_path, new_path))

    def rename_torrent(self, torrent_hash, new_torrent_name):
        self._renamed_torrents.append(new_torrent_name)

    def resume_torrent(self, torrent_hashes):
        self._resumed.append(torrent_hashes)
        return True

    def delete_torrent(self, delete_files, torrent_hashes):
        self._deleted.append((delete_files, torrent_hashes))
        return True

    def recheck_torrent(self, torrent_hashes):
        self._rechecked.append(torrent_hashes)
        return True

    def end_session(self, torrent_hashes=None):
        return None


class FakeToloka:
    def __init__(self, torrent):
        self.torrent = torrent
        self.toloka_url = "https://example.com"

    def get_torrent(self, url):
        return self.torrent

    def download_torrent(self, url):
        return b"torrent-bytes"


class IntegrationFlowTests(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("tests")
        self.files = [FakeFile("My Show S01/My Show S01E01.mkv")]
        self.client = FakeQbitClient(self.files)
        self.torrent = FakeTorrent(
            name="My Show S01E01",
            url="t123",
            torrent_url="t123.torrent",
            date="2024-01-02",
        )
        self.toloka = FakeToloka(self.torrent)
        self.app_config = Application(
            client="qbittorrent",
            client_wait_time=0,
            enable_dot_spacing_in_file_name=True,
        )
        self.args = SimpleNamespace(force=False)
        self.config = SimpleNamespace(
            toloka=self.toloka,
            client=self.client,
            application_config=self.app_config,
            args=self.args,
            logger=self.logger,
            operation_result=OperationResult(),
        )

    @patch.object(torrent_processor, "update_config")
    @patch.object(torrent_processor.time, "sleep", return_value=None)
    def test_add_new_item_success(self, _sleep, mock_update_config):
        title = Title(
            code_name="MyShow",
            episode_index=0,
            season_number="01",
            torrent_name="My Show",
            download_dir="/downloads",
            release_group="RG",
            meta="WEB",
        )

        result = torrent_processor.add(self.config, title, self.torrent)

        self.assertEqual(result.response_code, ResponseCode.SUCCESS)
        self.assertEqual(
            self.client.renamed_files[0][1],
            "My Show S01/My.Show.S01E01.WEBRG.mkv",
        )
        self.assertEqual(
            self.client.renamed_folders[0],
            ("My Show S01", "My.Show.S01.WEB[RG]"),
        )
        self.assertIn("My.Show.S01.WEB[RG]", self.client.renamed_torrents)
        mock_update_config.assert_called_once()

    @patch.object(torrent_processor, "update_config")
    @patch.object(torrent_processor.time, "sleep", return_value=None)
    def test_update_existing_item_success(self, _sleep, mock_update_config):
        title = Title(
            code_name="MyShow",
            episode_index=0,
            season_number="01",
            torrent_name="My Show",
            download_dir="/downloads",
            release_group="RG",
            meta="WEB",
            publish_date="2024-01-01",
            hash="oldhash",
            guid="t123",
        )

        result = torrent_processor.update(self.config, title)

        self.assertEqual(result.response_code, ResponseCode.SUCCESS)
        self.assertTrue(self.client.deleted)
        mock_update_config.assert_called_once()

    def test_update_existing_item_same_date_no_update(self):
        title = Title(
            code_name="MyShow",
            episode_index=0,
            season_number="01",
            torrent_name="My Show",
            download_dir="/downloads",
            release_group="RG",
            meta="WEB",
            publish_date="2024-01-02",
            hash="oldhash",
            guid="t123",
        )

        result = torrent_processor.update(self.config, title)

        self.assertEqual(result.response_code, ResponseCode.SUCCESS)
        self.assertFalse(self.client.deleted)
        self.assertTrue(
            any("Update not required" in log for log in result.operation_logs)
        )

    @patch.object(torrent_processor, "update_config")
    @patch.object(torrent_processor.time, "sleep", return_value=None)
    def test_update_existing_item_recheck_failure(self, _sleep, mock_update_config):
        title = Title(
            code_name="MyShow",
            episode_index=0,
            season_number="01",
            torrent_name="My Show",
            download_dir="/downloads",
            release_group="RG",
            meta="WEB",
            publish_date="2024-01-01",
            hash="oldhash",
            guid="t123",
        )
        self.client.recheck_success = False

        result = torrent_processor.update(self.config, title)

        self.assertEqual(result.response_code, ResponseCode.FAILURE)
        self.assertTrue(
            any("Failed to start recheck" in log for log in result.operation_logs)
        )
        mock_update_config.assert_not_called()

    @patch.object(torrent_processor, "update_config")
    @patch.object(torrent_processor.time, "sleep", return_value=None)
    def test_add_new_item_transmission(self, _sleep, mock_update_config):
        files = [FakeFile("Show S01/Show S01E01.mkv")]
        client = FakeTransmissionClient(files)
        config = SimpleNamespace(
            toloka=self.toloka,
            client=client,
            application_config=Application(
                client="transmission",
                client_wait_time=0,
                enable_dot_spacing_in_file_name=False,
            ),
            args=self.args,
            logger=self.logger,
            operation_result=OperationResult(),
        )
        title = Title(
            code_name="Show",
            episode_index=0,
            season_number="01",
            torrent_name="Show",
            download_dir="/downloads",
            release_group="RG",
            meta="WEB",
        )

        result = torrent_processor.add(config, title, self.torrent)

        self.assertEqual(result.response_code, ResponseCode.SUCCESS)
        self.assertEqual(
            client.renamed_files[0][1],
            "Show S01E01 WEB-RG.mkv",
        )
        self.assertIn("Show S01 WEB[RG]", client.renamed_torrents)
        mock_update_config.assert_called_once()


if __name__ == "__main__":
    unittest.main()
