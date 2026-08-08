# Summary
Create a python script that parses downloaded HTML files in **/resources/web-downloader/** folder and extracts 
relevant information about table tennis matches into JSON structured files.

The script should be able to handle multiple HTML files and extract the following information for each match like
the JSON files in **/resources/actas-json/2025-2026/** folder.

There is an existing scrapper calles **scraper_actas_mq_2024_2025.py** that extracts the data from the RFETM website and saves it in JSON format. 
The goal is to take the reference of the existing scrapper **scraper_actas_mq_2024_2025.py** and create a new parser called 
**/src/actas-html/convert-html-actas-to-json.py** that reads the downloaded HTML files and outputs structured JSON files under the 
**/resources/actas-json/2025-2026/** folder keeping the same folder structure like **/resources/actas-json/<season>/<category>/<day>/<sex>/acta_<match_id>.json**.




