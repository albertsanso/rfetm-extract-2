# Summary

This prompt is designed to create a Python script that parses the downloaded HTML content from the RFETM website and extracts relevant information about the teams only. 
The extracted information will be saved in a JSON structured format for further analysis.

# Description

The script will read the downloaded HTML files from the specified folder structure and extract information about the teams participating in the competitions. 
The extracted data will include team names, club name, categories.

# Goal

The output JSON files will be segregated by season and will contain an array of objects, each representing a team with its associated information.
Each JSON file will be named according to the season (e.g., `2023-2024.json`, `2022-2023.json`, etc.) and will be stored in the specified output directory following the structure `/resources/equipos-json/{season}.json`.

The proposed JSON structure is like:
```json
[
    {
    "season": "2025-2026",
    "club_name": "CLUB TENNIS TAULA OLOT",
    "team_name": "C.T.T. OLOT - CAPDEVILA PERMAR",
    "category": "SUM"
    },
    {
    "season": "2023-2024",
    "club_name": "A.D. SCHOOL ZARAGOZA TENIS DE MESA",
    "team_name": "A.D. SCHOOL ZARAGOZA TENIS DE MESA",
    "category": ""
    },
    {
    "season": "2023-2024",
    "club_name": "A.D. SCHOOL ZARAGOZA TENIS DE MESA",
    "team_name": "SCHOOL ZARAGOZA",
    "category": "DHM-2"
    },
    {
    "season": "2023-2024",
    "club_name": "A.D. SCHOOL ZARAGOZA TENIS DE MESA",
    "team_name": "SCHOOL ZARAGOZA",
    "category": "PDM-4"
    }
    ...
]
```

The information will be extracted from an HTML table where:
- The first column contains the team name. The header is labelled with "Equipo" or "EQUIPO".
- The second column contains the club name. The header is labelled with "Club" or "CLUB".
- The third column contains the category. The header is labelled with "Liga" or "LIGA".

# Input Parameters

The created python script should accept the following input parameters:
- `input_dir`: The directory where the downloaded HTML files are stored. If not provided, it should default to `/resources/equipos-html/`.
- `output_file`: The file path where the extracted JSON data will be saved. If not provided, it should default to `/resources/equipos-json/{season}.json`.
- `overwrite`: A boolean flag indicating whether to overwrite the existing JSON file. If not provided, it should default to `False`.
    
    