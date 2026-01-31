from pathlib import Path

from setuptools import find_packages, setup


def _read_version():
    version_file = Path(__file__).parent / "toloka2MediaServer" / "version.py"
    with open(version_file, encoding="utf-8") as f:
        for line in f:
            if line.startswith("__version__"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("__version__ not found in version.py")


setup(
    name="toloka2MediaServer",
    version=_read_version(),
    description="Addon to facilitate locating and adding TV series/anime torrents from Toloka/Hurtom with standardized naming for Sonarr/Plex/Jellyfin integration.",
    url="https://github.com/maksii/toloka2MediaServer",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "toloka2MediaServer": ["data/*"],
    },
    entry_points={
        "console_scripts": [
            "toloka2MediaServer=toloka2MediaServer.main:main",
        ],
    },
    install_requires=[
        "transmission_rpc",
        "qbittorrent-api",
        "requests",
        "toloka2python @ git+https://github.com/maksii/toloka2python",
    ],
)
