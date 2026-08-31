# Resumen
Construir un empaquetador que cree un ZIP con los ficheros JSON de las actas.

# Descripción
Crear el script Python `src/packager/package_actas.py`, que empaquete el
contenido de `resources/actas-json/` en `resources/actas-json.zip` por defecto.
El directorio raíz del repositorio debe calcularse a partir de la ubicación del
script, no depender del directorio de trabajo actual.

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
  "files": [
	{
	  "path": "2025-2026/divisio-honor/acta_123.json",
	  "size": 45230
	},
	{
	  "path": "2024-2025/super-divisio/acta_456.json",
	  "size": 1234
	}
  ]
}
```

Reglas del formato:

- `source` es siempre la cadena `"RFETM"`.
- `files` es una lista; contiene una entrada por cada JSON que se añade al
  ZIP y puede estar vacía si no se encuentra ningún JSON.
- Cada entrada de `files` es un objeto con exactamente `path` y `size`.
- `path` es una cadena con la ruta relativa al directorio de entrada, usando
  `/` como separador incluso en Windows. Debe coincidir con el nombre del
  fichero dentro del ZIP.
- `size` es un entero con el tamaño del fichero original en bytes, no el
  tamaño comprimido.
- Las entradas de `files` se ordenan alfabéticamente por `path`.
- El manifiesto se serializa como JSON UTF-8, con `ensure_ascii=False`, dos
  espacios de indentación y un salto de línea final.

## Parámetros de uso

El script debe aceptar estos parámetros opcionales:

- `--input-dir`: directorio que contiene los JSON. Por defecto,
  `resources/actas-json/`.
- `--output-file`: ruta del ZIP de salida. Si no se indica, se usa
  `resources/actas-json.zip`, o `resources/actas-json-<season>.zip` cuando se
  indica `--season`.
- `--force`: permite reemplazar el ZIP si ya existe. Sin esta opción, la
  existencia del fichero de salida debe producir un error.
- `--season`: limita la búsqueda a los JSON cuya primera carpeta relativa bajo
  `--input-dir` sea esa temporada, por ejemplo `2021-2022` o `2025-2026`.
  Un `--output-file` explícito tiene prioridad sobre el nombre automático.

El script debe comprobar que el directorio de entrada existe, crear los
directorios padre de la salida si es necesario y usar compresión
`ZIP_DEFLATED`.

```powershell
python src/packager/package_actas.py [--input-dir <input_dir>] [--output-file <output_file>] [--force] [--season <season>]
```