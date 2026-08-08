Genera un script python que:
- Recorre la carpeta `/resources/actas/` y genera una estructura equivalente en `/resources/actas-json/` donde 
cada acta en PDF se convierte a un archivo JSON usando el script `parser-acta-pdf-2025-2026.py`. 
- El nombre del archivo JSON debe coincidir con el nombre del archivo PDF correspondiente, pero con la extensión `.json`. 
Asegúrate de mantener la misma estructura de carpetas en `/resources/actas-json/` que en `/resources/actas/`.

El script python generado tiene el nombre `convert-actas-to-json-2025-2026.py` y debe incluir manejo de errores para archivos PDF
que no puedan ser convertidos, registrando estos errores en un archivo de log llamado `conversion_errors.log`.
Además, el script debe imprimir un resumen al final indicando cuántos archivos fueron convertidos exitosamente y cuántos fallaron.
