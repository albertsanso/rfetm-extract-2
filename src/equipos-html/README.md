# Descargador de equipos RFETM

`web-downloader-equipos-rfetm.py` descarga la página HTML que contiene la
información de equipos de una o varias temporadas desde:

```text
https://www.rfetm.es/public/resultados/<temporada>/view.php?listaeq=eq
```

El script pertenece a un pipeline independiente y no requiere instalar el
proyecto como paquete. Las dependencias se encuentran en `requirements.txt`.

## Requisitos

- Python 3.9 o posterior.
- Dependencias instaladas en el entorno virtual del proyecto. La principal
  dependencia de este script es `requests`.

Desde PowerShell, si todavía no existe el entorno virtual:

```powershell
cd C:\git\rfetm-extract-2
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Compilación y comprobación de sintaxis

Python no necesita una compilación previa para ejecutar el script. Se puede
comprobar la sintaxis y generar el bytecode con:

```powershell
cd C:\git\rfetm-extract-2
python -m py_compile .\src\equipos-html\web-downloader-equipos-rfetm.py
```

Para comprobar que la interfaz de argumentos está disponible:

```powershell
python .\src\equipos-html\web-downloader-equipos-rfetm.py --help
```

## Ejecución

La temporada inicial es obligatoria:

```powershell
python .\src\equipos-html\web-downloader-equipos-rfetm.py --start-season 2024-2025
```

Por defecto se descarga únicamente `2024-2025`. Para descargar un rango
completo, inclusive, indique la temporada final:

```powershell
python .\src\equipos-html\web-downloader-equipos-rfetm.py `
    --start-season 2024-2025 `
    --end-season 2019-2020
```

El ejemplo anterior recorre las temporadas en orden descendente. También se
admiten rangos ascendentes. Los nombres de opciones con guion bajo son alias
válidos: `--start_season`, `--end_season` y `--output_dir`.

## Argumentos

| Argumento | Obligatorio | Valor predeterminado | Descripción |
|---|---:|---|---|
| `--start-season` | Sí | — | Temporada inicial con formato `YYYY-YYYY`, por ejemplo `2024-2025`. |
| `--end-season` | No | La temporada inicial | Temporada final del rango, incluida. |
| `--output-dir` | No | `resources/equipos-html` en la raíz del repositorio | Directorio raíz donde se guardan los resultados. |
| `--overwrite` | No | Desactivado | Sobrescribe los archivos HTML existentes. Sin esta opción se omiten. |

También se pueden usar las variantes `--start_season`, `--end_season` y
`--output_dir`.

## Estructura de salida

Para cada temporada se crea un archivo con el mismo nombre que la temporada
directamente dentro del directorio de salida:

```text
resources/
└── equipos-html/
    ├── 2024-2025.html
    └── 2023-2024.html
```

El directorio de salida puede cambiarse, por ejemplo:

```powershell
python .\src\equipos-html\web-downloader-equipos-rfetm.py `
    --start-season 2024-2025 `
    --output-dir .\resources\equipos-html-prueba
```

## Comportamiento y códigos de salida

- Las temporadas deben tener el formato consecutivo `YYYY-YYYY`.
- Se esperan aproximadamente 2 segundos entre peticiones para respetar el
  servidor de la RFETM.
- El servidor puede devolver HTTP 500 con HTML válido; si la respuesta tiene
  cuerpo, se guarda igualmente.
- Se realizan reintentos para errores transitorios como `429`, `502`, `503` y
  `504`.
- El código de salida es `0` si todas las temporadas se procesan correctamente,
  `1` si alguna descarga falla y `2` si los argumentos contienen una temporada
  no válida.

No se recomienda ejecutar descargas masivas con `--overwrite` salvo que sea
necesario, ya que fuerza nuevas peticiones para archivos que ya existen.

## Conversión de equipos a JSON

`parser-equipos-rfetm.py` lee las tablas de equipos descargadas y genera un
archivo JSON por temporada con los campos `season`, `club_name`, `team_name` y
`category`. Por defecto procesa todos los archivos válidos de
`resources/equipos-html` y escribe en `resources/equipos-json`.

```powershell
python .\src\equipos-html\parser-equipos-rfetm.py
```

Para procesar una temporada concreta:

```powershell
python .\src\equipos-html\parser-equipos-rfetm.py `
    --season 2024-2025
```

Argumentos disponibles:

| Argumento | Valor predeterminado | Descripción |
|---|---|---|
| `--input-dir` (`--input_dir`) | `resources/equipos-html` | Directorio de HTML descargados. |
| `--output-file` (`--output_file`) | `resources/equipos-json/{season}.json` | Archivo de salida; admite `{season}`. |
| `--season` | Todas las temporadas | Limita la conversión a `YYYY-YYYY`. |
| `--overwrite` | Desactivado | Reemplaza JSON que ya exista. |
| `--verbose` | Desactivado | Activa mensajes de depuración. |

El parser intenta UTF-8 y usa ISO-8859-1 como alternativa para las páginas
antiguas. Sin `--overwrite`, los resultados existentes se conservan.

