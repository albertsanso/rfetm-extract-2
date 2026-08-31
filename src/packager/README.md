# Empaquetador de equipos

`package_teams.py` crea `equipos-json.zip` en `resources/`. Incluye
todos los archivos `.json` de `resources/equipos-json/`, conservando sus rutas
relativas, y añade `manifest.json` con la ruta y el tamaño en bytes de cada
archivo incluido.

Desde la raíz del repositorio:

```powershell
python src/packager/package_teams.py
```

También se pueden indicar un directorio de entrada y un archivo de salida, o
reemplazar un ZIP existente con `--force`:

```powershell
python src/packager/package_teams.py --input-dir resources/equipos-json --output-file equipos-json.zip --force
```

Para empaquetar únicamente una temporada, el valor corresponde a la primera
carpeta bajo el directorio de entrada. Si no se indica `--output-file`, el ZIP
se llamará `equipos-json-<season>.zip`:

```powershell
python src/packager/package_teams.py --season 2025-2026 --force
```

Un `--output-file` explícito tiene prioridad sobre el nombre automático:

```powershell
python src/packager/package_teams.py --season 2025-2026 --output-file salida.zip --force
```

## Empaquetador de actas

`package_actas.py` crea `actas-json.zip` en `resources/`. Incluye todos los
archivos `.json` de `resources/actas-json/`, conserva sus rutas relativas y
añade `manifest.json` con la ruta y el tamaño en bytes de cada archivo.

```powershell
python src/packager/package_actas.py
```

Para indicar otras rutas o reemplazar un ZIP existente:

```powershell
python src/packager/package_actas.py --input-dir resources/actas-json --output-file actas-json.zip --force
```

También se puede empaquetar únicamente una temporada. El valor corresponde a
la primera carpeta bajo el directorio de entrada. Si no se indica
`--output-file`, el ZIP se llamará `actas-json-<season>.zip`:

```powershell
python src/packager/package_actas.py --season 2025-2026 --force
```

Cuando se especifica `--output-file`, ese nombre tiene prioridad:

```powershell
python src/packager/package_actas.py --season 2025-2026 --output-file salida.zip --force
```

