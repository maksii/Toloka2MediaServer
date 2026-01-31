import configparser
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from toloka2MediaServer.__main__ import main


def _make_configs():
    app_config = configparser.ConfigParser()
    app_config["Python"] = {"logging": "INFO"}
    titles_config = configparser.ConfigParser()
    application_config = SimpleNamespace(
        default_download_dir="/downloads",
        default_meta="WEB",
        wait_time=0,
    )
    return app_config, titles_config, application_config


class CliMainTests(unittest.TestCase):
    @patch("toloka2MediaServer.__main__.get_numbers", return_value=["01"])
    @patch("toloka2MediaServer.__main__.dynamic_client_init", return_value="client")
    @patch("toloka2MediaServer.__main__.get_toloka_client", return_value="toloka")
    @patch("toloka2MediaServer.__main__.setup_logging")
    @patch("toloka2MediaServer.__main__.load_configurations")
    @patch("toloka2MediaServer.__main__.get_parser")
    def test_main_num_path_exits(
        self,
        mock_get_parser,
        mock_load_configurations,
        mock_setup_logging,
        _get_toloka_client,
        _dynamic_client_init,
        _get_numbers,
    ):
        mock_load_configurations.return_value = _make_configs()
        mock_get_parser.return_value = SimpleNamespace(
            parse_args=lambda: SimpleNamespace(
                num="S01E01",
                url=None,
                add=None,
                codename=None,
            )
        )
        mock_setup_logging.return_value = SimpleNamespace(
            info=lambda *_args, **_kwargs: None,
            debug=lambda *_args, **_kwargs: None,
        )

        with patch("builtins.print") as mock_print:
            with self.assertRaises(SystemExit):
                main()

        mock_print.assert_called_once_with(["01"])

    @patch("toloka2MediaServer.__main__.add_release_by_url")
    @patch("toloka2MediaServer.__main__.dynamic_client_init", return_value="client")
    @patch("toloka2MediaServer.__main__.get_toloka_client", return_value="toloka")
    @patch("toloka2MediaServer.__main__.setup_logging")
    @patch("toloka2MediaServer.__main__.load_configurations")
    @patch("toloka2MediaServer.__main__.get_parser")
    def test_main_add_by_url_path(
        self,
        mock_get_parser,
        mock_load_configurations,
        mock_setup_logging,
        _get_toloka_client,
        _dynamic_client_init,
        mock_add_release_by_url,
    ):
        mock_load_configurations.return_value = _make_configs()
        mock_get_parser.return_value = SimpleNamespace(
            parse_args=lambda: SimpleNamespace(
                num=None,
                url="https://example.com/t123",
                add=None,
                codename=None,
                season="01",
                index=1,
                correction=0,
                title="Title",
                path=None,
            )
        )
        mock_setup_logging.return_value = SimpleNamespace(
            info=lambda *_args, **_kwargs: None,
            debug=lambda *_args, **_kwargs: None,
        )

        with self.assertRaises(SystemExit):
            main()

        mock_add_release_by_url.assert_called_once()

    @patch("toloka2MediaServer.__main__.add_release_by_name")
    @patch("toloka2MediaServer.__main__.dynamic_client_init", return_value="client")
    @patch("toloka2MediaServer.__main__.get_toloka_client", return_value="toloka")
    @patch("toloka2MediaServer.__main__.setup_logging")
    @patch("toloka2MediaServer.__main__.load_configurations")
    @patch("toloka2MediaServer.__main__.get_parser")
    def test_main_add_by_name_path(
        self,
        mock_get_parser,
        mock_load_configurations,
        mock_setup_logging,
        _get_toloka_client,
        _dynamic_client_init,
        mock_add_release_by_name,
    ):
        mock_load_configurations.return_value = _make_configs()
        mock_get_parser.return_value = SimpleNamespace(
            parse_args=lambda: SimpleNamespace(
                num=None,
                url=None,
                add="Show",
                codename=None,
            )
        )
        mock_setup_logging.return_value = SimpleNamespace(
            info=lambda *_args, **_kwargs: None,
            debug=lambda *_args, **_kwargs: None,
        )

        with self.assertRaises(SystemExit):
            main()

        mock_add_release_by_name.assert_called_once()

    @patch("toloka2MediaServer.__main__.update_release_by_name")
    @patch("toloka2MediaServer.__main__.dynamic_client_init", return_value="client")
    @patch("toloka2MediaServer.__main__.get_toloka_client", return_value="toloka")
    @patch("toloka2MediaServer.__main__.setup_logging")
    @patch("toloka2MediaServer.__main__.load_configurations")
    @patch("toloka2MediaServer.__main__.get_parser")
    def test_main_update_by_code_path(
        self,
        mock_get_parser,
        mock_load_configurations,
        mock_setup_logging,
        _get_toloka_client,
        _dynamic_client_init,
        mock_update_release_by_name,
    ):
        mock_load_configurations.return_value = _make_configs()
        mock_get_parser.return_value = SimpleNamespace(
            parse_args=lambda: SimpleNamespace(
                num=None,
                url=None,
                add=None,
                codename="Show",
            )
        )
        mock_setup_logging.return_value = SimpleNamespace(
            info=lambda *_args, **_kwargs: None,
            debug=lambda *_args, **_kwargs: None,
        )

        with self.assertRaises(SystemExit):
            main()

        mock_update_release_by_name.assert_called_once()

    @patch("toloka2MediaServer.__main__.update_releases")
    @patch("toloka2MediaServer.__main__.dynamic_client_init", return_value="client")
    @patch("toloka2MediaServer.__main__.get_toloka_client", return_value="toloka")
    @patch("toloka2MediaServer.__main__.setup_logging")
    @patch("toloka2MediaServer.__main__.load_configurations")
    @patch("toloka2MediaServer.__main__.get_parser")
    def test_main_update_all_path(
        self,
        mock_get_parser,
        mock_load_configurations,
        mock_setup_logging,
        _get_toloka_client,
        _dynamic_client_init,
        mock_update_releases,
    ):
        mock_load_configurations.return_value = _make_configs()
        mock_get_parser.return_value = SimpleNamespace(
            parse_args=lambda: SimpleNamespace(
                num=None,
                url=None,
                add=None,
                codename=None,
            )
        )
        mock_setup_logging.return_value = SimpleNamespace(
            info=lambda *_args, **_kwargs: None,
            debug=lambda *_args, **_kwargs: None,
        )

        with self.assertRaises(SystemExit):
            main()

        mock_update_releases.assert_called_once()


if __name__ == "__main__":
    unittest.main()
