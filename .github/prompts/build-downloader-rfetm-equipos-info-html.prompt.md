# Summary

Download the HTML content of the pages that contain information about the RFETM teams.

# Description

The RFETM (Real Federación Española de Tenis de Mesa) website contains pages with information about the teams participating in various competitions. 
This prompt is designed to build a python script to download the HTML content of those pages for further analysis or processing.

The teams information is segregated by seasons, and each season has its own page. The script should be able to navigate through the seasons and download the HTML content of each team's page.

# Goal

Build a python script in `/src/equipos-html/web-downloader-equipos-rfetm.py` that will:
- Download the HTML content of the RFETM teams pages for all available seasons.
- The HTML content for each season is just the HTML of the page that lists the teams for that season.
- The URL structure for the seasons is as follows: `https://www.rfetm.es/public/resultados/{season}/view.php?listaeq=eq`, where `{season}` is a placeholder for the season identifier (e.g., `2023-2024`, `2022-2023`, etc.).
- The folder to store the downloaded HTML files should be in the root repository folder `/resources/equipos-html/{season}.html`, and the files should be named according to the season (e.g., `2023-2024.html`, `2022-2023.html`, etc.).

# Input Parameters
The created python script should accept the following input parameters:
- `start_season`: The starting season for which the content needs to be downloaded, in the format `YYYY-YYYY` (e.g., `2023-2024`).
- `end_season`: The ending season for which the content needs to be downloaded, in the format `YYYY-YYYY` (e.g., `2010-2011`). The script should download content for all seasons from `start_season` to `end_season`, inclusive. If not provided, it should default to the {start_season} value.
- `output_dir`: The directory where the downloaded HTML files will be saved. If not provided, it should default to `/resources/equipos-html/`.
- `overwrite`: A boolean flag indicating whether to overwrite existing files. If not provided, it should default to `False`.
