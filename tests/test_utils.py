import unittest

from toloka2MediaServer.utils import general
from toloka2MediaServer.utils import torrent_processor


class GeneralUtilsTests(unittest.TestCase):
    def test_get_numbers_extracts_digit_groups(self):
        self.assertEqual(general.get_numbers("S01E02 - 1080p"), ["01", "02", "1080"])

    def test_replace_second_part_in_path(self):
        self.assertEqual(
            general.replace_second_part_in_path("root/old/file.mkv", "new"),
            "root/new/file.mkv",
        )
        self.assertEqual(general.replace_second_part_in_path("single", "new"), "single")

    def test_get_folder_name_from_path(self):
        self.assertEqual(general.get_folder_name_from_path("folder/file.mkv"), "folder")
        self.assertEqual(general.get_folder_name_from_path("file.mkv"), "")

    def test_extract_torrent_details(self):
        name, codename = general.extract_torrent_details("foo/Bar Baz (2024)")
        self.assertEqual(name, "Bar Baz (2024)")
        self.assertEqual(codename, "BarBaz")


class TorrentProcessorUtilsTests(unittest.TestCase):
    def test_get_file_name_from_path(self):
        self.assertEqual(
            torrent_processor._get_file_name_from_path("folder/file.mkv"), "file.mkv"
        )
        self.assertEqual(
            torrent_processor._get_file_name_from_path(r"folder\\file.mkv"),
            "file.mkv",
        )
        self.assertEqual(
            torrent_processor._get_file_name_from_path("file.mkv"), "file.mkv"
        )

    def test_numbers_with_context(self):
        numbers = torrent_processor._numbers_with_context("S01E02")
        self.assertIn(("01", "S", "E0"), numbers)
        self.assertIn(("02", "1E", ""), numbers)


if __name__ == "__main__":
    unittest.main()
