# Toloka2MediaServer [![CI](https://github.com/maksii/Toloka2MediaServer/actions/workflows/ci.yml/badge.svg)](https://github.com/maksii/Toloka2MediaServer/actions/workflows/ci.yml) [![GPLv3 License](https://img.shields.io/badge/License-GPL%20v3-yellow.svg)](https://opensource.org/licenses/)

<p align="center">
<img src="https://img.shields.io/github/languages/code-size/maksii/Toloka2MediaServer?style=for-the-badge"/>
<img src="https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black"/>
<img src="https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54"/>
<img src="https://img.shields.io/badge/Visual%20Studio%20Code-0078d7.svg?style=for-the-badge&logo=visual-studio-code&logoColor=white"/></p>

## English Section
The primary goal of this project is to address naming issues for Ukrainian localization studios that create regional naming conventions for shows/anime. Additionally, Toloka follows the rule that ongoing series/anime should be in a single release. As a result of these actions, none of the modern *arr suites or media servers are capable of parsing files and automating the download process effectively.

This project is specifically tailored to use the Toloka torrent tracker and the [toloka2python](https://github.com/maksii/toloka2python) library to establish connections, find torrents, and gather additional metadata. The original project by CakesTwix appears abandoned as he moved to codeberg with no recent updates; this project uses the maintained [maksii/toloka2python](https://github.com/maksii/toloka2python) fork. 

The scripts in this project make direct API calls to the torrent clients like Transmission and qBittorrent to adjust the torrent name, folder name, and file name according to the following naming convention:
- Torrent/Folder: `SeriesName Season [Quality] [Language] [Subs] [ReleaseGroup]`
- File: `SeriesName SeasonEpisode [Quality] [Language] [Subs]-ReleaseGroup.extension`

Any future documentation will be provided in Ukrainian. Please use a translator if needed or create new issues if you require further assistance.

## Installation

**Prerequisites**

- **Python 3.11+**
- A [Toloka](https://toloka.to) account
- **qBittorrent** or **Transmission** (configured and running, Transmission not tested)

**Steps**

1. Clone the repository:
   ```bash
   git clone https://github.com/maksii/Toloka2MediaServer.git
   cd Toloka2MediaServer
   ```

2. (Recommended) Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Linux/macOS:
   source .venv/bin/activate
   # Windows:
   .venv\Scripts\activate
   ```

3. Install dependencies and the package:
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```
   The `toloka2python` library is installed from GitHub as listed in `requirements.txt`. After this, the `toloka2MediaServer` command is available (or use `python -m toloka2MediaServer`).

4. Create the config directory and add your config files:
   ```bash
   mkdir data
   ```
   Add `data/app.ini` (Toloka, torrent client, and app settings) and optionally `data/titles.ini` (see [Конфиги](#конфиги) for examples).

5. Run the application:
   ```bash
   toloka2MediaServer --help
   # or
   python -m toloka2MediaServer --help
   ```

## Authors

- **[@CakesTwix](https://github.com/CakesTwix)** — original author
- **[@maksii](https://github.com/maksii)** — current maintainer

## Contributing

As I use this for my own projects, I know this might not be the perfect approach for all the projects out there. If you have any ideas, just open an issue and tell me what you think.

If you'd like to contribute, please fork the repository and make changes as you'd like. Pull requests are warmly welcome.

## UA Section
Консольна утиліта для докачування нових серій аніме з Toloka.
Для скачування торрент-файлів використовується бібліотека [toloka2python](https://github.com/maksii/toloka2python).


Наразі можна качати торренти, де одна директорія (Один сезон), в якому знаходяться серії

```
The Girl I Like Forgot Her Glasses (S1)
├── Episode S1E01.mkv
├── Episode S1E02.mkv
├── Episode S1E03.mkv
├── Episode S1E04.mkv
├── Episode S1E05.mkv
├── Episode S1E06.mkv
├── Episode S1E07.mkv
└── Episode S1E08.mkv
```

## Вміст
- [Встановлення](https://github.com/maksii/Toloka2MediaServer?tab=readme-ov-file#installation)
- [Огляд Інтерфейсу Користувача](https://github.com/maksii/Toloka2MediaServer?tab=readme-ov-file#огляд-інтерфейсу-користувача)
  - [Інтерфейс Командного Рядка](https://github.com/maksii/Toloka2MediaServer?tab=readme-ov-file#інтерфейс-командного-рядка-cli) (CLI)
  - [Огляд роботи](https://github.com/maksii/Toloka2MediaServer?tab=readme-ov-file#огляд-роботи)
- [Crontab](https://github.com/maksii/Toloka2MediaServer?tab=readme-ov-file#crontab-every-day-at-800)
- [Конфиги](https://github.com/maksii/Toloka2MediaServer?tab=readme-ov-file#конфиги)
- [Автори](https://github.com/maksii/Toloka2MediaServer?tab=readme-ov-file#автори)
- [Ліцензія](https://github.com/maksii/Toloka2MediaServer?tab=readme-ov-file#ліцензія)

## Огляд Інтерфейсу Користувача

### Інтерфейс Командного Рядка (CLI)

Застосунок надає інтерфейс командного рядка (CLI) для користувачів, які віддають перевагу безпосередньому взаємодії з програмним забезпеченням через їхній термінал. Нижче наведено приклад виконання звичайної команди та її виводу.

#### Приклад Команди

Ось як запустити приклад команди:

```bash
python -m toloka2MediaServer -a "Kimetsu no Yaiba: Hashira Geiko-hen"
```

#### Вивід

```
0 : Вбивця демонів: навчання Хашіра (Сезон 4, 03 з XX) / Kimetsu no Yaiba: Hashira Geiko-hen (2024) WEBDLRip 1080p H.265 Ukr/Jap | sub Ukr - t678861
Enter the index of the desired torrent: 0
Default:KimetsunoYaibaHashiraGeikohen. Enter the codename:
Enter the season number: 5
Default: /media/HDD/Jellyfin/Anime:. Enter the download directory path.
Default: Kimetsu no Yaiba: Hashira Geiko-hen (2024). Enter the directory name for the downloaded files:
Enter the release group name, or it will default to the torrent's author:
Default: [WEBRip-1080p][UK+JA][Ukr Sub]. Enter additional metadata tags:
```

**Скріншот:**

![CLI Скріншот](assets/cli.png)

## Огляд роботи

**Перед змінами:**  
![Web UI Скріншот](assets/files-before.png) 
**Після змін:**  
![Web UI Скріншот](assets/files-after.png)

**Перед змінами:**  
![Web UI Скріншот](assets/Info-before.png) 
**Після змін:**  
![Web UI Скріншот](assets/Info-after.png)

### Використання/Приклади
Цей блок містить приклади використання команд для `toloka2MediaServer`. Коментарі надають пояснення щодо деяких параметрів та їх використання.
* **Допомога**
	```bash
	python -m toloka2MediaServer --help
	```
* **Додати новий торрент вручну**
	```bash
	python -m toloka2MediaServer -a "Назва торрента роздачі"
	```
* **Додати новий торрент автоматично**
	```bash
	python -m toloka2MediaServer --add --url https://toloka.to/t675888 --season 02 --index 2 --correction 0 --title "Tsukimichi -Moonlit Fantasy-"
	```
* **Додати новий торрент автоматично (partial season)**
	```bash
	python -m toloka2MediaServer --add --url https://toloka.to/t675888 --season 02 --index 2 --correction 0 --title "Tsukimichi -Moonlit Fantasy-" --partial
	```
	> Використовуйте `--partial` для часткових релізів сезону, коли реліз містить не всі епізоди сезону
* **Додати новий торрент з кастомним шляхом завантаження**
	```bash
	python -m toloka2MediaServer --add --url https://toloka.to/t675888 --season 02 --index 2 --correction 0 --title "Tsukimichi -Moonlit Fantasy-" --path "/custom/download/path"
	```
	> Використовуйте `--path` для вказання кастомної директорії завантаження замість значення за замовчуванням
* **Оновити всі торренти**
	```bash
	python -m toloka2MediaServer
	```
* **Завантажити нові серії, якщо торрент оновився**
	```bash
	python -m toloka2MediaServer -c CODENAME
	```
	> Коднейм береться з файлу titles.ini, про нього буде вказано пізніше
* **Примусово завантажити торрент (ігноруючи перевірку наявності)**
	```bash
	python -m toloka2MediaServer -c CODENAME --force
	```
	> Використовуйте `--force` для примусового завантаження незалежно від наявності торренту
* **Отримати список чисел із рядка**
	```bash
	python -m toloka2MediaServer -n "text1 123"
	```
	> Це необхідно для перейменування файлів у торренті для визначення номера серії у Jellyfin або Plex. В конфігурації потрібно вказати, в якому індексі знаходиться номер серії.

> **Примітка:** У торренті береться відразу Директорія/Файл.mkv, наприклад:
Horimiya - Piece [WEBDL 1080p HEVC]/Horimiya - Piece - 01 (WEBDL 1080p HEVC AAC) Ukr DVO SUB.mkv

## Crontab (Every day at 8:00)
```bash
crontab -e
```
> 0 8 * * * cd /path/to/toloka2MediaServer/ && python3 -m toloka2MediaServer

## Конфиги

> **Примітка:** Файли конфігурації повинні бути розташовані у папці `data/` в корені проекту: `data/app.ini` та `data/titles.ini`

* ### app.ini
```ini
[Python]
# NOTSET
# DEBUG
# INFO
# WARNING
# ERROR
# CRITICAL
logging = INFO

[transmission]
username = Імя користувача
password = Пароль
port = 9091
host = localhost
protocol = http
rpc = /transmission/rpc
category = sonarr
tag = tolokaAnime

[qbittorrent]
username = Імя користувача
password = Пароль
port = 8080
host = 192.168.40.22
protocol = http
tag = toloka
category = sonarr

[Toloka]
username = Імя користувача
password = Пароль
client = qbittorrent або transmission
default_download_dir = /media/HDD/Jellyfin/Anime
default_meta = [WEBRip-1080p][UK+JA][Ukr Sub]
wait_time = 10
client_wait_time = 2
enable_dot_spacing_in_file_name = True
```
* ### titles.ini
```ini
[ArknightsTouin]
episode_index = 2
season_number = 02
ext_name = .mkv
torrent_name = "Arknights: Touin Kiro (2022)"
download_dir = /media/HDD/Jellyfin/Anime
publish_date = 24-05-23 21:32
release_group = InariDuB
meta = [WEBRip-1080p][UK+JA][Ukr Sub]
hash = 97e3023362ebb41263f3266ac3a72cc56eda0885
adjusted_episode_number = -8
guid = t678205
is_partial_season = False

[Tsukimichi]
episode_index = 2
season_number = 02
ext_name = .mkv
torrent_name = "Tsukimichi -Moonlit Fantasy- (2021)"
download_dir = /media/HDD/Jellyfin/Anime
publish_date = 24-05-28 17:16
release_group = FanVoxUA
meta = [WEBRip-1080p][UK][Ukr Sub]
hash = 8bcb2b32b4885e6c4a03f909486a03f26a4c9a62
adjusted_episode_number = 0
guid = t675888
is_partial_season = False
```
	
### Конфігурація епізодів аніме
<small>

| Властивість            | ArknightsTouin                                      | Tsukimichi                                     | Визначення                                                           |
|------------------------|-----------------------------------------------------|------------------------------------------------|----------------------------------------------------------------------|
| episode_index         | 2                                                   | 2                                              | Індекс, що вказує номер епізоду(звідки брати номер епізоду)                                      |
| season_number          | 02                                                  | 02                                             | Номер сезону                                            |
| ext_name               | .mkv                                                | .mkv                                           | (застаріле) Формат файлу - визначається автоматично з файлу         |
| torrent_name           | "Arknights: Touin Kiro (2022)"                     | "Tsukimichi -Moonlit Fantasy- (2021)"          | Базове ім'я для генерації назви торрента, тек та файлів             |
| download_dir           |                                                     | /media/HDD/Jellyfin/Anime                      | Директорія для завантаження медіа (використовується в Transmission) |
| publish_date            | 2024-05-23                                          | 2024-05-21                                     | Системне значення для визначення оновлень торренту                   |
| release_group          | InariDuB                                            | FanVoxUA                                       | Реліз група або автор роздачі                                       |
| meta                   | [WEBRip-1080p][UK+JA][Ukr Sub]                     | [WEBRip-1080p][UK][Ukr Sub]                     | Додаткові метадані, які будуть додані у назву                         |
| hash                   | 97e...0885          | 8bc...a62 | Системне значення - ID торрент файлу для майбутнього пошуку           |
| adjusted_episode_number | -8                                             | 0                                              | Коригування номера епізоду сезону для абсолютного або азіатського неймінгу |
| guid                   | t678205                                           | t675888                                      | Системне значення для ідентифікації конкретного аніме у списку        |
| is_partial_season      | False                                             | False                                        | Чи є реліз частковим сезоном (не всі епізоди)                        |

</small>

## Автори

- [@CakesTwix](https://github.com/CakesTwix) — оригінальний автор проекту
- [@maksii](https://github.com/maksii) — поточний підтримник (maintainer)



## Ліцензія

- [GPL-v3](https://choosealicense.com/licenses/gpl-3.0/)
