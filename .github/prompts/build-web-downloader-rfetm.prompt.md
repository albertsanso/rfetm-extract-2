# Summary
This prompt is designed to create a Python script that downloads web content from a list of URLs provided in a text file and saves them to local files.

# input parameters
The created python script should accept the following input parameters:
- `season`: The season for which the content needs to be downloaded, in the format `YYYY-YYYY` (e.g., `2023-2024`).

# Steps
Create s python script that performs the following features:
- From a base URL navigates throw a generated list of URLs and downloads the content of each URL.
- The Downloaded content need to be organized by Season / Category or competition / day / sex  in a folder structure in `resources/web-downloader/<season>/<category>/<day>/<sex>/`
- Base URL is `https://www.rfetm.es/public/resultados/<season>`. <season> format is `YYYY-YYYY` (e.g., `2023-2024`). Starting from 2024-2025 season to the past seasons until 2010-2011 or where URL exists.

In each season URL there is a set of URLs like: `https://www.rfetm.es/public/resultados/2024-2025/view.php?liga=MQ==&grupo=0&subgrupo=S&jornada=0&sexo=M`
**`liga`** params can be:
- `MQ==` for "super-divisio"
- `Mg==` for "divisio-honor"
- `Mw==` for "primera-divisio"
- `NA==` for "segona-divisio"

**`jornada`** can have values from 1 to 22

**`grupo`** can have numeric values, each category has different number of groups, make the inference from each season url `https://www.rfetm.es/public/resultados/<season>`

**`subgrupo`** is always 0

**`sexo`** can be `M` or `F`

