# Summary

El script `convert-html-actas-to-json.py` es un script que convierte archivos HTML de actas a formato JSON.

Existen casos en que el parseo no es correcto y el json generado no es válido.

# Problemas conocidos

## Jugadores de dobles sin numero de licencia - PENDING

En los fuentes de origen HTML, los jugadores de dobles no tienen número de licencia.

### Descripcion del problema

Por ejemplo el siguiente JSON es el nodo generado para los jugadores de dobles:
```json
  "dobles": {
    "local": [
      "RIESTRA POCIÑO, MARIA",
      "LO , TSZ KWAN"
    ],
    "visitante": [
      "SANCHEZ SOUSA, LUCIA",
      "DE ARMAS PEREZ, THALIA"
    ]
  },
```

### Ejemplos de Actas afectadas

`acta_11_581.json`
`acta_2017649_20212246.json`

Iterate JSON files and check if the "dobles" field has players without license numbers in order to get the complete list if affected files.

### Solución propuesta

Se necesita extraer el número de licencia de los jugadores de dobles para que el JSON generado sea válido.
En la acta original (HTML) los jugadores de dobles tienen un número de licencia asociado, pero este no se está capturando correctamente en el JSON generado.
```text
RIESTRA POCIÑO, MARIA
LO , TSZ KWAN
```

License id can be extracte from the HTML next to the text `Lic:`. For instance `RIESTRA POCIÑO, MARIA` has `Lic: 28785`
and `LO , TSZ KWAN` has  `Lic: 44485`

### Output resultante esperado

EL output deseado es que el JSON generado tenga el número de licencia asociado a cada jugador de dobles, por ejemplo:
```json
  "dobles": {
    "local": [
      {
        "nombre": "RIESTRA POCIÑO, MARIA",
        "licencia": 28785
      },
      {
        "nombre": "LO , TSZ KWAN",
        "licencia": 44485
      }
    ],
    "visitante": [
      {
        "nombre": "SANCHEZ SOUSA, LUCIA",
        "licencia": 12345
      },
      {
        "nombre": "DE ARMAS PEREZ, THALIA",
        "licencia": 67890
      }
    ]
  },
```

- Modificar script de python `convert-html-actas-to-json.py` para que capture correctamente los números de licencia de los jugadores de dobles y genere un JSON válido.
