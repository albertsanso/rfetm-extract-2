# Summary

El script `parser-acta-pdf-2025-2026.py` es un script que convierte archivos PDF de actas a formato JSON. 

Existen casos en que el parseo no es correcto y el json generado no es válido. 

# Problemas conocidos

## Nombres de equipos - FIXED -> SKIP

### Descripcion del problema

En el fichero PDF, las secciones de "Equipo local" y "Equipo visitante" no se capturan correctamente.
Esto provoca que el nodo "equipos" del JSON generado tenga valores nulos para los campos "nombre" de ambos equipos.

```json
{
  "equipos": {
    "local": {
      "nombre": null,
      ...
    },
    "visitante": {
      "nombre": null,
      ...
    }
  }
}
```

El campo "nombre" es obligatorio y no puede ser nulo. Esto provoca que el JSON generado no sea válido y que falle la conversión.

### Ejemplos de Actas afectadas

`acta_27960.json`
`acta_28013.json`

Iterate on JSON files and check if the "nombre" field is null for both "local" and "visitante" teams in order to get the complete list if affected files.

### Solución propuesta

- Investigar si el salto de línea en la sección "Local de juego" puede ser tenido en cuenta para que las secciones de "Equipo local" y "Equipo visitante" se capturen correctamente.
- Investigar otras posible causas de que los nombres de los equipos no se capturen correctamente y proponer soluciones para corregir el problema.
- Si no es posible capturar los nombres de los equipos, se podría considerar la opción de rellenar estos campos con un valor por defecto (por ejemplo, "Desconocido") para evitar que el JSON generado sea inválido. Sin embargo, esta solución debería ser evaluada cuidadosamente para no comprometer la integridad de los datos.

### Output resultante esperado

- Modificar script de python `parser-acta-pdf-2025-2026.py` para que capture correctamente los nombres de los equipos y genere un JSON válido.
- Si no es posible capturar los nombres de los equipos, rellenar los campos "nombre" con un valor por defecto (por ejemplo, "Desconocido") para evitar que el JSON generado sea inválido.

## Jugadores de dobles sin numero de licencia - FIXED -> SKIP

En el fichero PDF, los jugadores de dobles no tienen número de licencia.

### Descripcion del problema

Por ejemplo el siguiente JSON es el nodo generado para los jugadores de dobles:
```json
  "dobles": {
    "local": [
      "SANZ GARCIA, CELIA",
      "PIÑÓN PITA, VALERIA"
    ],
    "visitante": [
      "TUBIO MARCO, MARIA LUISA",
      "CRESPO RIAL, MARTA"
    ]
  },
```

### Solución propuesta

Se necesita extraer el número de licencia de los jugadores de dobles para que el JSON generado sea válido.
En la acta original (PDF) los jugadores de dobles tienen un número de licencia asociado, pero este no se está capturando correctamente en el JSON generado.
```text
SANZ GARCIA, CELIA (35875)
PIÑÓN PITA, VALERIA (39326)
```

### Output resultante esperado

EL output deseado es que el JSON generado tenga el número de licencia asociado a cada jugador de dobles, por ejemplo:
```json
  "dobles": {
    "local": [
      {
        "nombre": "SANZ GARCIA, CELIA",
        "licencia": 35875
      },
      {
        "nombre": "PIÑÓN PITA, VALERIA",
        "licencia": 39326
      }
    ],
    "visitante": [
      {
        "nombre": "TUBIO MARCO, MARIA LUISA",
        "licencia": 12345
      },
      {
        "nombre": "CRESPO RIAL, MARTA",
        "licencia": 67890
      }
    ]
  },
```

- Modificar script de python `parser-acta-pdf-2025-2026.py` para que capture correctamente los números de licencia de los jugadores de dobles y genere un JSON válido.
