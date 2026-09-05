# Resumen
Construir un empaquetador que cree un ZIP con los ficheros JSON de información
de equipos.

# Descripción
Crear el script Python `src/packager/package_teams.py`, que empaquete el
contenido de `resources/equipos-json/` en `resources/equipos-json.zip` por
defecto. El directorio raíz del repositorio debe calcularse a partir de la
ubicación del script, no depender del directorio de trabajo actual.

El ZIP debe contener:

- Todos los ficheros `*.json` encontrados recursivamente bajo el directorio de
  entrada, conservando sus rutas relativas.
- Un fichero `manifest.json` en la raíz del ZIP. El manifiesto describe los
  JSON incluidos, pero no se incluye a sí mismo en `files`.

## Formato de `manifest.json`

El manifiesto debe tener exactamente esta estructura:

```json
{
  "source": "RFETM",
  "asset_type": "TEAMS",
  "seasons": [
    "2024-2025",
    "2025-2026"
  ],
  "files": [
    "2025-2026.json",
    "otra-carpeta/2024-2025.json"
  ]
}
```

Reglas del formato:

- `source` es siempre la cadena `"RFETM"`.
- `asset_type` es siempre la cadena `"TEAMS"`.
- `seasons` es una lista ordenada alfabéticamente de las temporadas `YYYY-YYYY`
  presentes en las rutas o nombres de los JSON incluidos. Puede estar vacía si
  no hay temporadas.
- `files` es una lista de cadenas; contiene una ruta por cada JSON que se añade
  al ZIP y puede estar vacía si no se encuentra ningún JSON.
- Cada cadena de `files` es la ruta relativa al directorio de entrada, usando
  `/` como separador incluso en Windows. Debe coincidir con el nombre del
  fichero dentro del ZIP.
- Las entradas de `files` se ordenan alfabéticamente por ruta.
- El manifiesto se serializa como JSON UTF-8, con `ensure_ascii=False`, dos
  espacios de indentación y un salto de línea final.

## Parámetros de uso

El script debe aceptar estos parámetros opcionales:

- `--input-dir`: directorio que contiene los JSON. Por defecto,
  `resources/equipos-json/`.
- `--output-file`: ruta del ZIP de salida. Si no se indica, se usa
  `resources/equipos-json.zip`, o `resources/equipos-json-<seasons>.zip` cuando
  se indica `--season`, usando las temporadas normalizadas y separadas por comas.
- `--force`: permite reemplazar el ZIP si ya existe. Sin esta opción, la
  existencia del fichero de salida debe producir un error.
- `--season`: limita la búsqueda a los JSON cuya primera carpeta relativa bajo
  `--input-dir` sea una de las temporadas indicadas o, cuando el JSON está
  directamente bajo `--input-dir`, cuyo nombre sea `<season>.json`. Acepta una
  temporada o varias separadas por comas, por ejemplo
  `2023-2024,2024-2025`; se ignoran espacios alrededor de cada valor, se
  eliminan duplicados y cada valor debe tener formato `YYYY-YYYY`. Un
  `--output-file` explícito tiene prioridad sobre el nombre automático.

El script debe comprobar que el directorio de entrada existe, crear los
directorios padre de la salida si es necesario y usar compresión
`ZIP_DEFLATED`.

```powershell
python src/packager/package_teams.py [--input-dir <input_dir>] [--output-file <output_file>] [--force] [--season <season>]
```