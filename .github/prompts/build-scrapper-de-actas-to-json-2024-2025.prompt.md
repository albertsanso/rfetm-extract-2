Crea un script python para extraer la informacion a un formato JSON desde la pagina
https://www.rfetm.es/public/resultados/2024-2025/view.php?liga=MQ==&grupo=0&subgrupo=S&jornada=1&sexo=M. 
La pagina contiene las actas para la jornada 1, para la categoria MQ (super division) masculina. 
Analiza las actas en detalle, identifica secciones, fechas, liga, categoria, lugar, equipos visitante/local, árbitro,
jugadores locales/visitantes, relaciona letras ABC/XYZ con jugadores, cruzes, resultados de cada set, resultados acumulados, resultado final, etc.
Convierte el diseño de la pagina a una estructura JSON similar a las que existen en `/resources/json/actas-json/`.

Tambien puedes tomar como referencia los scripts existentes en `/resources/src/parser-best-2025-2026.py` para ver como se hace el scrapping de otras actas desde un PDF.

El script generado debe llamarse `scraper_actas_mq_2024_2025.py`.