En la URL: https://www.rfetm.es/public/resultados/2025-2026/ hay acceso a todos los resultados de los campeonatos de España de tenis de mesa de las temporadas 2025 y 2026.

Hay multiples enlaces con este formato: https://www.rfetm.es/public/resultados/2025-2026/view.php?liga={categoria}==&grupo={grupo}&subgrupo=S&jornada=0&sexo={sexo}
Donde:
- {categoria} multiples valores como "MQ", "Mg"...
- {grupo} multiples valores como "1", "2", "3"...
- {sexo} multiples valores como "M", "F"...

Detras de cada enlaze hay una tabla con los resultados de los partidos, organizados por jornadas.
Cada fila de la tabla contiene información sobre un partido específico, y tiene un enlace tipo https://clubs.rfetm.es/ligas/partido/{id}}/imprimir/acta
que da acceso al acta del partido en formato PDF.

Parsea desde la URL inicial de https://www.rfetm.es/public/resultados/2025-2026/ todos los enlaces de resultados de partidos, y para cada partido, extrae el enlace al acta en PDF.
Organiza una estructura de carpetas en `/resources/actas/` siguiendo la estructura de temporada (eg. 2025-2026), categorías, grupos y sexo, y guarda cada acta en su correspondiente carpeta. 

# Restricciones del web scrapping
- La web de la RFETM tiene medidas de seguridad que pueden bloquear solicitudes automatizadas si se realizan demasiadas en un corto período de tiempo. Por lo tanto, es importante implementar retrasos entre las solicitudes y manejar posibles errores de conexión o bloqueos. No hay prisa en la descarga.
- Utiliza otros métodos de ofuscacion de orígenes de las solicitudes, como cambiar el User-Agent, para evitar ser bloqueado, y considera el uso de proxies si es necesario.