import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from toloka2MediaServer.clients.qbittorrent import QbittorrentClient
from toloka2MediaServer.clients.transmission import TransmissionClient


class FakeTorrent:
    def __init__(self, torrent_hash, name="torrent", state="downloading"):
        self.hash = torrent_hash
        self.name = name
        self.state = state


class FakeFile:
    def __init__(self, name):
        self.name = name


class FakeQbitApi:
    def __init__(self):
        self._torrents = {}
        self._files = {}
        self._renamed_files = []
        self._renamed_folders = []
        self._renamed_torrents = []
        self._resumed = []
        self._deleted = []

    def torrents_info(self, torrent_hashes=None, **_kwargs):
        if torrent_hashes:
            torrent = self._torrents.get(torrent_hashes)
            return [torrent] if torrent else []
        return list(self._torrents.values())

    def torrents_add(self, torrent_files, category, tags, is_paused, download_path):
        return None

    def torrents_files(self, torrent_hash):
        return self._files.get(torrent_hash, [])

    def torrents_rename_file(self, torrent_hash, old_path, new_path):
        self._renamed_files.append((torrent_hash, old_path, new_path))
        files = self._files.get(torrent_hash, [])
        for file in files:
            if file.name == old_path:
                file.name = new_path

    def torrents_rename_folder(self, torrent_hash, old_path, new_path):
        self._renamed_folders.append((torrent_hash, old_path, new_path))
        files = self._files.get(torrent_hash, [])
        for file in files:
            if file.name.startswith(f"{old_path}/"):
                file.name = file.name.replace(f"{old_path}/", f"{new_path}/", 1)

    def torrents_rename(self, torrent_hash, new_torrent_name):
        self._renamed_torrents.append((torrent_hash, new_torrent_name))
        torrent = self._torrents.get(torrent_hash)
        if torrent:
            torrent.name = new_torrent_name

    def torrents_resume(self, torrent_hashes):
        self._resumed.append(torrent_hashes)
        torrent = self._torrents.get(torrent_hashes)
        if torrent:
            torrent.state = "downloading"

    def torrents_delete(self, delete_files, torrent_hashes):
        self._deleted.append((delete_files, torrent_hashes))
        self._torrents.pop(torrent_hashes, None)


class QbittorrentClientTests(unittest.TestCase):
    def setUp(self):
        with patch.object(QbittorrentClient, "_connect"):
            self.client = QbittorrentClient(
                SimpleNamespace(
                    logger=None,
                    app_config={},
                    application_config=SimpleNamespace(client="qbittorrent"),
                )
            )
        self.client.api_client = FakeQbitApi()
        self.client.retry_config.max_attempts = 1
        self.client.retry_config.verification_delay = 0

    def test_add_torrent_returns_hash_when_added(self):
        self.client.api_client._torrents.clear()
        self.client.api_client._torrents["hash123"] = FakeTorrent("hash123")

        with patch.object(
            self.client, "_calculate_torrent_hash", return_value="hash123"
        ):
            with patch.object(self.client, "_get_torrent") as mock_get:
                mock_get.side_effect = [
                    None,
                    FakeTorrent("hash123"),
                ]
                result = self.client.add_torrent(
                    torrents=b"data",
                    category="cat",
                    tags=["tag"],
                    is_paused=True,
                    download_dir="/downloads",
                )

        self.assertEqual(result, "hash123")

    def test_rename_file_updates_paths(self):
        torrent_hash = "hash123"
        self.client.api_client._torrents[torrent_hash] = FakeTorrent(torrent_hash)
        self.client.api_client._files[torrent_hash] = [FakeFile("old/file.mkv")]

        result = self.client.rename_file(torrent_hash, "old/file.mkv", "new/file.mkv")

        self.assertTrue(result)
        self.assertEqual(
            self.client.api_client._files[torrent_hash][0].name, "new/file.mkv"
        )

    def test_rename_folder_updates_paths(self):
        torrent_hash = "hash123"
        self.client.api_client._torrents[torrent_hash] = FakeTorrent(torrent_hash)
        self.client.api_client._files[torrent_hash] = [FakeFile("old/file.mkv")]

        result = self.client.rename_folder(torrent_hash, "old", "new")

        self.assertTrue(result)
        self.assertEqual(
            self.client.api_client._files[torrent_hash][0].name, "new/file.mkv"
        )

    def test_resume_torrent_verifies_active_state(self):
        torrent_hash = "hash123"
        self.client.api_client._torrents[torrent_hash] = FakeTorrent(
            torrent_hash, state="pausedDL"
        )

        result = self.client.resume_torrent(torrent_hash)

        self.assertTrue(result)
        self.assertEqual(
            self.client.api_client._torrents[torrent_hash].state, "downloading"
        )


class TransmissionClientTests(unittest.TestCase):
    def setUp(self):
        self.logger = MagicMock()
        self.config = SimpleNamespace(
            app_config={
                "transmission": {
                    "host": "localhost",
                    "port": 9091,
                    "username": "user",
                    "password": "pass",
                    "rpc": "/transmission/rpc",
                    "protocol": "http",
                    "category": "cat",
                    "tag": "tag",
                }
            },
            application_config=SimpleNamespace(client="transmission"),
            logger=self.logger,
        )

    @patch("toloka2MediaServer.clients.transmission.Client")
    def test_transmission_actions(self, mock_client):
        api = mock_client.return_value
        api.add_torrent.return_value = SimpleNamespace(id="10")
        api.get_torrent.return_value = "torrent-info"
        api.get_files.return_value = "files"
        api.rename_torrent_path.return_value = True
        api.start_torrent.return_value = True
        api.remove_torrent.return_value = True
        api.verify_torrent.return_value = True

        client = TransmissionClient(self.config)

        self.assertEqual(
            client.add_torrent(b"data", "cat", "tag", True, "/downloads"), "10"
        )
        self.assertEqual(
            client.get_torrent_info(None, None, None, None, False, "hash"),
            "torrent-info",
        )
        self.assertEqual(client.get_files("hash"), "files")
        self.assertTrue(client.rename_file("hash", "old", "new"))
        self.assertTrue(client.rename_folder("hash", "old", "new"))
        self.assertTrue(client.rename_torrent("hash", "name"))
        self.assertTrue(client.resume_torrent("hash"))
        self.assertTrue(client.delete_torrent(True, "hash"))
        self.assertTrue(client.recheck_torrent("hash"))
