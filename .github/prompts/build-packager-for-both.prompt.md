# Construir el empaquetador conjunto de actas y equipos

Implementa un nuevo script independiente llamado `src/packager/packager-both.py` que empaquete en un único archivo ZIP los datos JSON de actas y de equipos del repositorio RFETM.

Antes de editar, lee `AGENTS.md`, `src/packager/package_actas.py`, `src/packager/package_teams.py` y `src/packager/README.md`. Reutiliza sus convenciones y lógica siempre que sea posible, pero no modifiques los dos empaquetadores existentes ni regeneres los datos de `resources/`.

## Objetivo

El script debe combinar estas dos fuentes en una sola distribución:

- `resources/actas-json/`: JSON de actas, con estructura de temporadas, categorías, grupos/sexos y actas.
- `resources/equipos-json/`: JSON de equipos, que puede contener archivos `<temporada>.json` directamente en la raíz o carpetas por temporada.

El ZIP resultante debe conservar ambas estructuras y evitar colisiones de nombres usando estos prefijos obligatorios dentro del archivo:

```text
actas-json/<ruta-relativa-al-directorio-de-actas>
equipos-json/<ruta-relativa-al-directorio-de-equipos>
manifest.json
```

Nunca mezcles los JSON de ambas fuentes directamente en la raíz del ZIP ni cambies sus rutas relativas internas.

## Interfaz de línea de comandos

Implementa `argparse` con estas opciones:

- `--actas-input-dir`: directorio de entrada de actas. Por defecto, `REPO_ROOT / "resources" / "actas-json"`.
- `--equipos-input-dir`: directorio de entrada de equipos. Por defecto, `REPO_ROOT / "resources" / "equipos-json"`.
- `--output-file`: archivo ZIP de salida. Por defecto, `REPO_ROOT / "resources" / "actas-equipos-json.zip"`.
- `--force`: permite reemplazar el ZIP si ya existe; sin esta opción, termina con un error claro y no sobrescribe datos.
- `--season`: una o varias temporadas separadas por comas, por ejemplo `2023-2024,2024-2025`. Valida cada valor con `^\d{4}-\d{4}$`, elimina espacios laterales, rechaza elementos vacíos y elimina duplicados conservando el orden.

Si se especifica `--season` y no se especifica `--output-file`, genera automáticamente `actas-equipos-json-<temporadas>.zip`, usando la lista normalizada separada por comas. Un `--output-file` explícito siempre tiene prioridad.

Usa `Path(__file__).resolve().parent.parent.parent` para calcular la raíz del repositorio, igual que los empaquetadores existentes.

## Selección de archivos

- Incluye únicamente archivos `.json` regulares de cada directorio de entrada, encontrados recursivamente y ordenados por su ruta relativa POSIX.
- Para actas, `--season` filtra por el primer componente de la ruta relativa, que es el directorio de temporada.
- Para equipos, `--season` debe admitir tanto una carpeta de temporada como un archivo de raíz llamado `<temporada>.json`; la comparación del archivo debe hacerse con `Path(nombre).stem`.
- Sin `--season`, incluye todos los JSON de ambas fuentes.
- Si una ruta de entrada no existe o no es un directorio, lanza un error claro antes de crear el ZIP.
- Si el filtro no encuentra archivos de una de las fuentes, no inventes archivos ni abortes por ese motivo: el manifiesto debe reflejar una lista vacía para esa fuente. La ausencia del directorio de entrada sí es un error.

## Manifiesto

Escribe exactamente un `manifest.json` en la raíz del ZIP, codificado en UTF-8, con `ensure_ascii=False`, indentación de dos espacios y salto de línea final. Debe tener esta forma conceptual:

```json
{
	"source": "RFETM",
	"seasons": [
		"2025-2026"
	],
	"assets": {
		"ACTAS": {
			"files": ["actas-json/...", "..."]
		},
		"TEAMS": {
			"files": ["equipos-json/...", "..."]
		}
	}
}
```

Requisitos del manifiesto:

- `seasons` es la unión ordenada alfabéticamente de las temporadas detectadas en ambas fuentes.
- Cada lista `files` contiene las rutas que realmente aparecen dentro del ZIP, incluidos sus prefijos `actas-json/` o `equipos-json/`.
- Las listas de cada sección y la unión de temporadas deben ser deterministas.
- Detecta temporadas en cualquier componente de la ruta usando el mismo patrón de temporada y `Path(part).stem`, para soportar tanto directorios como archivos `<temporada>.json`.

## Implementación

- Extrae funciones pequeñas y testeables para: parsear temporadas, encontrar archivos de actas, encontrar archivos de equipos, detectar temporadas, construir el manifiesto y escribir el ZIP.
- Evita duplicar innecesariamente la lógica común de los scripts existentes.
- Usa `zipfile.ZipFile(..., compression=zipfile.ZIP_DEFLATED)`.
- Crea el directorio padre de `--output-file` si no existe.
- Escribe los archivos con `archive.write(path, arcname=...)`, siempre con rutas POSIX relativas y el prefijo correspondiente.
- `main()` debe imprimir en español el número de archivos de actas, el número de archivos de equipos y la ruta del ZIP generado.
- Mantén el código, docstrings, comentarios y mensajes en español. No añadas dependencias externas; el script debe funcionar con la biblioteca estándar de Python.
- Conserva el estilo y la compatibilidad de Python de los empaquetadores existentes (`from __future__ import annotations`, `Path`, anotaciones de tipos y `argparse`).

## Verificación requerida

Después de implementar el script:

1. Ejecuta `python src/packager/packager-both.py --help`.
2. Ejecuta una prueba con un directorio temporal pequeño que contenga un JSON bajo una carpeta de temporada de actas, un archivo `<temporada>.json` en la raíz de equipos, otro JSON bajo una carpeta de temporada de equipos y al menos una temporada no seleccionada.
3. Abre el ZIP generado y verifica que contiene los dos prefijos, conserva las rutas relativas, incluye `manifest.json` y que el manifiesto coincide con los archivos presentes.
4. Verifica que repetir la ejecución sin `--force` falla sin sobrescribir y que repetirla con `--force` funciona.
5. Verifica que una temporada inválida produce un error de `argparse` y que las rutas se ordenan de forma determinista.
6. No alteres `package_actas.py`, `package_teams.py` ni los archivos JSON comprometidos del repositorio.

El resultado final debe ser un script ejecutable y autocontenido, no una modificación de los empaquetadores individuales.

