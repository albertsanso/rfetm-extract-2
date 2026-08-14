"""
convert-actas-to-json-2025-2026.py
Recorre /resources/actas/ y convierte cada PDF a JSON usando parse_acta()
del parser principal, generando la misma estructura en /resources/actas-json/.
"""

import json
import logging
import os
import sys
from pathlib import Path

# Añadir el directorio src al path para poder importar el parser
SRC_DIR = Path(__file__).parent
sys.path.insert(0, str(SRC_DIR))

# Importar la función de parseo del parser principal
# El nombre del módulo usa guiones, así que usamos importlib
import importlib.util

parser_path = SRC_DIR / "parser-acta-pdf-2025-2026.py"
spec = importlib.util.spec_from_file_location("parser_best", parser_path)
parser_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser_module)
parse_acta = parser_module.parse_acta

# ── Rutas base ──
BASE_DIR = SRC_DIR.parent.parent
ACTAS_DIR = BASE_DIR / "resources" / "actas"
JSON_DIR = BASE_DIR / "resources" / "actas-json"
LOG_FILE = BASE_DIR / "conversion_errors.log"

# ── Configurar logging ──
logging.basicConfig(
    filename=str(LOG_FILE),
    filemode="w",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8",
)

def convert_all():
    converted = 0
    failed = 0

    if not ACTAS_DIR.exists():
        print(f"[ERROR] No se encontró la carpeta de actas: {ACTAS_DIR}")
        sys.exit(1)

    pdf_files = list(ACTAS_DIR.rglob("*.pdf"))
    total = len(pdf_files)
    print(f"Encontrados {total} archivos PDF en '{ACTAS_DIR}'")
    print(f"Destino JSON: '{JSON_DIR}'")
    print(f"Log de errores: '{LOG_FILE}'")
    print("-" * 60)

    for pdf_path in sorted(pdf_files):
        # Calcular ruta relativa respecto a ACTAS_DIR
        rel_path = pdf_path.relative_to(ACTAS_DIR)

        # Ruta de destino JSON con misma estructura de carpetas
        json_rel = rel_path.with_suffix(".json")
        json_path = JSON_DIR / json_rel

        # Crear carpeta destino si no existe
        json_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            acta = parse_acta(str(pdf_path))
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(acta, f, ensure_ascii=False, indent=2)
            print(f"  [OK]  {rel_path}")
            converted += 1
        except Exception as e:
            error_msg = f"{pdf_path}: {e}"
            logging.error(error_msg)
            print(f"  [ERR] {rel_path} -> {e}")
            failed += 1

    print("-" * 60)
    print(f"Resumen: {converted} convertidos correctamente, {failed} con error.")
    if failed:
        print(f"Revisa '{LOG_FILE}' para ver los detalles de los errores.")

if __name__ == "__main__":
    convert_all()

