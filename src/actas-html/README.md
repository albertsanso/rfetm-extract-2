# Downloading actas in HTML format

HTML content related to actas will be stored in the `/resources/web-downloader/<season>/<league>/<day>/<sex>/grupo_<group>.html` folder. 
The script `web_downloader_rfetm.py` is used to download the HTML content from the RFETM website.

```commandline
  python web_downloader_rfetm.py --season 2024-2025
  python web_downloader_rfetm.py --season 2023-2024 --force
  python web_downloader_rfetm.py --season 2024-2025 --all-seasons
```