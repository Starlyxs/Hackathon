# Hojas en papel

Califica hojas de examen impresas a partir de un PDF escaneado con el celular (o de la cámara de la laptop). El programa vive en la computadora del maestro: no hace falta internet para usarlo ni un celular por alumno.

## Contenido de la carpeta

```
Hojas en papel/
├── README.md        Esta guía
├── iniciar.bat      Abre el programa en Windows (doble clic)
├── iniciar.sh       Abre el programa en Mac o Linux
└── programa/        Todo lo demás: el código, los datos y las herramientas
    └── data/        Aquí quedan tus exámenes y notas
```

Para llevar el programa a otra computadora se copia **la carpeta completa**. No hace falta instalar nada a mano.

## 1. Instalar y abrir (la primera vez)

**Qué necesita la computadora:** Windows 10 u 11 de 64 bits (también sirve Mac o Linux), 4 GB de memoria, unos 500 MB libres y un navegador (Chrome, Edge o Firefox). **Internet solo la primera vez**, para descargar las librerías. Después funciona sin red.

### Windows

1. Copia la carpeta completa al escritorio o a Documentos.
2. Doble clic en **`iniciar.bat`**.
3. Espera. La primera vez tarda unos minutos y muestra texto en una ventana negra. Es normal; no la cierres.
4. Se abre el navegador con el programa. Si no se abre solo, escribe `http://127.0.0.1:8000` en la barra de direcciones.
5. Además, deja un icono **«Hojas en papel»** en el escritorio para la próxima vez.

**¿Y si la computadora no tiene Python?** No pasa nada: `iniciar.bat` lo detecta, descarga Python 3.11 de python.org, lo instala solo para ese usuario (no pide ser administrador) y sigue. Necesita internet y tarda un par de minutos más. Si no hay internet, el mensaje lo dice; en ese caso instala Python a mano desde <https://www.python.org/downloads/> (versión 3.11, 3.12 o 3.13, marcando **«Add python.exe to PATH»**) y vuelve a abrir `iniciar.bat`.

Windows puede mostrar «Windows protegió su PC». Pulsa **Más información** y luego **Ejecutar de todas formas**: pasa porque el archivo no tiene firma digital.

### Mac o Linux

1. Abre una terminal dentro de la carpeta.
2. Ejecuta `bash iniciar.sh`.
3. Necesita Python 3.11, 3.12 o 3.13. Si falta, el mensaje dice cómo instalarlo (en Ubuntu: `sudo apt install python3 python3-venv python3-pip`).

### Qué hace `iniciar` por dentro

1. Busca Python 3.11 a 3.13; si no hay, lo instala (solo Windows).
2. Crea un entorno privado en la carpeta de tu usuario (`.hojas-en-papel`). Está fuera de OneDrive a propósito, para que no se sincronice ni se rompa. Si copiaste la carpeta desde otra computadora, lo rehace solo.
3. Instala las librerías que falten (solo la primera vez, o si algo cambia).
4. Abre el programa en tu navegador.

## 2. Volver a abrir y cerrar

- **Abrir:** doble clic en el icono **«Hojas en papel»** del escritorio, o en `iniciar.bat`. Ya no usa internet ni tarda: abre en segundos.
- **Si ya estaba abierto**, `iniciar` solo vuelve a abrir el navegador.
- **Cerrar:** cierra la **ventana negra**. El programa funciona solo mientras esa ventana está abierta. Tus datos quedan guardados y no se pierden.
- Si cierras la pestaña del navegador por error, la ventana negra sigue viva: escribe `http://127.0.0.1:8000` en el navegador y listo.
- Si el puerto 8000 estuviera ocupado, el programa usa el 8001, 8002… y la ventana negra dice cuál.

## 3. Cómo se usa, paso a paso

La pantalla de **Inicio** dice qué sigue en cada momento. También trae un video corto con los pasos.

1. **Grupos.** Crea cada grupo con su lista de alumnos una sola vez. Los exámenes usan esa lista. Si eliminas un grupo, sus exámenes pasan a la papelera y se pueden restaurar.
2. **Exámenes.** Se crea en cinco pasos: grupo, materia, cuál examen es, cuántos puntos vale y las series del examen. En el tablero de bimestres y parciales, lo que ya se hizo sale en verde con ✓ y no se puede repetir.
   - **Series:** un examen se arma con series (Serie I, Serie II…). Cada serie es de opciones (A–D) o de respuesta escrita, puede llevar una imagen, tiene sus puntos y el programa los reparte entre sus preguntas (una serie de 10 puntos con 4 preguntas vale 2.5 cada una). La suma de las series no puede pasar de la nota del examen; si queda por debajo, la nota se calcula sobre lo repartido. Las series se acomodan una tras otra y solo se agrega una hoja cuando la anterior se llena, así no sobran hojas vacías.
   - Las preguntas se escriben dentro de cada serie: «Escribir pregunta» abre una ventana con una vista previa abajo. Las guardadas se reutilizan y se pueden borrar. Cada examen es de una materia. Las opciones A, B, C y D se arman solas, con números distintos para cada alumno.
   - Al terminar, **descarga el PDF** (una hoja por alumno, cada una con su QR) e imprímelo.
   - **Apagar examen:** un examen apagado ya no recibe hojas, pero conserva sus notas. Se vuelve a encender cuando quieras.
   - **Eliminar:** manda el examen a la papelera. Se puede deshacer o restaurar con sus notas. Solo «Borrar para siempre» lo quita de verdad.
3. **Calificar.** Los alumnos contestan con lápiz. El maestro escanea las hojas con el celular (Google Drive, Notas del iPhone o CamScanner), las junta en **un solo PDF** y lo sube en Calificar.
   - Cada página trae su propio QR, así que el programa sabe de qué alumno y de qué hoja es aunque vengan mezcladas, torcidas, al revés o con páginas en blanco.
   - Al terminar muestra cuántas hojas calificó, **a quién le falta una hoja** (por ejemplo «Beto: falta hoja 2 de 2»), quién no entregó nada y qué páginas no pudo leer.
   - Las hojas que ya tenían nota no se tocan (hay una casilla para recalificarlas). Si falta una hoja, se escanea y se sube aparte; se suma a la anterior.
   - Las hojas con preguntas escritas quedan en «Revisar lo escrito», con la imagen escaneada al lado; la revisión se puede dejar a medias y retomar después.
   - La cámara en vivo sigue disponible como opción.
   - **Revisar y corregir hojas:** la lista pone primero las hojas con respuestas sin marca o con dos marcas. «Revisar» muestra la hoja escaneada junto a lo que leyó el programa; si una burbuja se leyó mal, se cambia y la nota se recalcula. La corrección queda marcada.
   - **Borrar imágenes escaneadas** elimina las fotos de los alumnos cuando ya no se necesiten, y conserva las notas.
4. **Notas del año.** Una materia a la vez, con los cuatro bimestres juntos: zona (parciales y actividades), examen final y total de cada bimestre, más el promedio anual. Se filtra por bimestre y se descarga para Excel. **Boletines para imprimir:** una hoja por alumno con sus notas de cada materia y bimestre, el total del año, un texto breve y qué reforzar, con espacio para las firmas.
5. **Análisis (opcional).** Gráficos de barras fáciles de leer: resumen del grupo (promedio, aprobados, quién necesita apoyo), cuántos alumnos cayeron en cada rango de nota, la nota de cada alumno, el dominio por serie y por tema, los errores que se repiten (si el mismo error aparece en la mitad del grupo o más, lo señala) y la evolución entre exámenes de la misma materia. Cada alumno trae un texto con lo que le falta y una sugerencia, con botón para crear su **hoja de refuerzo**. «Imprimir informe» lo deja listo para papel o PDF.
   - **Tres alcances:** *Un examen*, *Una materia* (todo el año, con filtro opcional por bimestre) y *General* (todas las materias). En materia y general cuentan los parciales, finales y actividades; el diagnóstico no.

La nota real son los puntos sobre la nota total del examen. La nota relativa usa la misma escala, pero el mejor del examen se lleva la nota completa. El diagnóstico no suma a los bimestres.

## 4. Pasar el PDF del celular a la computadora

El programa corre solo en la computadora, así que el PDF escaneado tiene que llegar hasta ella. Estas formas funcionan sin instalar nada extra:

- **Cable USB:** conecta el celular y copia el PDF. Es la más segura y no necesita internet.
- **Quick Share (antes «Compartir cercano»):** en Android, con la app gratuita Quick Share para Windows de Google instalada en la computadora, el celular envía el archivo por Bluetooth y Wi-Fi, sin internet. En el celular: Compartir → Quick Share → elige la computadora.
- **Google Drive, correo o WhatsApp Web:** sube el PDF desde el celular y descárgalo en la computadora.

El programa no recibe archivos directo por Bluetooth: los navegadores no lo permiten. Una subida directa del celular por la red de la escuela necesitaría abrir el programa a otras máquinas, y se dejó fuera a propósito (ver más abajo).

## 5. Probar sin papel (prueba simulada)

En **Inicio**, el botón **«Cargar prueba simulada»** crea el grupo «Demo Sexto A» con 8 alumnos, exámenes de Matemática y Lenguaje ya calificados, y dos exámenes sin calificar con PDFs de ejemplo para descargar y subir en Calificar (en uno, a Beto le falta una hoja y Daniel no entregó, para ver cómo avisa el programa). Así se ven notas, análisis y boletines sin imprimir nada. **«Borrar la prueba simulada»** la quita completa sin tocar los datos reales.

## 6. Tus datos, copias de seguridad y cambio de computadora

- Todo se guarda **solo en esa computadora**, en `programa/data/`. Nada se manda a internet.
- Cada día, antes del primer cambio, se guarda una copia automática en `programa/data/copias/` (se conservan las últimas 14).
- En Inicio, **«Descargar copia de seguridad»** baja un .zip con todo. Guárdalo en un USB de vez en cuando.
- **Cambiar de computadora:** copia la carpeta completa, o instala el programa en la otra y pon el `store.json` de la copia dentro de `programa/data/`. Ciérralo antes de copiar.
- **OneDrive:** si la carpeta está dentro de OneDrive, Inicio muestra un aviso. La sincronización puede bloquear o duplicar el archivo de datos mientras el programa escribe. Lo ideal es dejar la carpeta en `C:\Hojas en papel` o en Documentos locales, y usar la copia de seguridad.
- Las hojas escaneadas quedan guardadas para poder revisar lo escrito. Se borran desde Calificar con «Borrar imágenes escaneadas».

## 7. Si algo falla

| Qué pasa | Qué hacer |
| --- | --- |
| Doble clic en `iniciar.bat` y la ventana se cierra sola | Abre una terminal en la carpeta y ejecuta `iniciar.bat` para ver el mensaje. |
| «No pude descargar Python» o «No se pudieron instalar las librerías» | Falta internet o hay un filtro en la red. Conéctate (el celular como punto de acceso sirve) y vuelve a abrir. Solo hace falta la primera vez. |
| «Windows protegió su PC» | Más información → Ejecutar de todas formas. |
| El antivirus o Windows bloquea Python o el programa | Pide a quien administra la computadora que permita la carpeta y `.hojas-en-papel`. |
| El navegador no se abre | Escribe `http://127.0.0.1:8000` (o el puerto que diga la ventana negra). |
| «La página no abre» | Revisa que la ventana negra siga abierta. Si la cerraste, vuelve a abrir el programa. |
| Algo quedó raro tras copiar la carpeta | Borra la carpeta `.hojas-en-papel` de tu usuario y vuelve a abrir; se rehace sola. Tus datos no se tocan. |
| Quiero dejar todo de cero | Cierra el programa y borra `programa/data/`. Haz antes una copia de seguridad. |
| Una hoja no se lee | Mira `/ayuda` dentro del programa: explica QR no encontrado, hoja en blanco o hoja faltante. |

## 8. ¿Y Docker?

No se usa a propósito. Docker sirve cuando alguien técnico administra servidores, pero aquí el usuario es un maestro con una laptop sencilla:

- Docker Desktop pesa más de 500 MB, pide mucha memoria (se nota en computadoras de 4 GB), necesita activar la virtualización y permisos de administrador, y tiene licencia de pago para organizaciones grandes.
- Obliga a aprender comandos y a acordarse de abrir Docker antes del programa.
- Este programa ya se instala solo con `iniciar.bat`, trabaja sin servidores y con pocas dependencias, así que Docker no le aporta nada a ese usuario.

Si en el futuro se pone en un servidor de la escuela, ahí sí tendría sentido, y el código no necesita cambios: es una aplicación web común. No se incluye un `Dockerfile` porque no se pudo probar aquí.

## Para quien desarrolla

- Código en `programa/app/`; el arranque es `programa/run.py`; `programa/preparar.py` revisa e instala las librerías.
- **Prueba automática**, sin imprimir ni escanear: lee QR, burbujas, PDF escaneado, corrección, boletines y la prueba simulada.
  - Windows (desde `programa`): `& "$env:USERPROFILE\.hojas-en-papel\venv\Scripts\python.exe" -m app.selfcheck`
  - Mac o Linux (desde `programa`): `~/.hojas-en-papel/venv/bin/python -m app.selfcheck`
- **Versiones:** `requirements.txt` fija un rango de cada librería (probado con Python 3.11, OpenCV 5.1, NumPy 2.4, FastAPI 0.165).
- **Ejecutable `.exe` (opcional):** `programa/dist/HojasEnPapel/HojasEnPapel.exe` se arma con PyInstaller y el archivo `programa/HojasEnPapel.spec`. En algunas computadoras Windows lo bloquea («directiva de Control de aplicaciones») porque no tiene firma digital, y no se ha podido probar en todas. **Lo recomendado es `iniciar.bat`.** El exe guarda sus datos en una carpeta `datos` al lado.
- **Video tutorial:** Inicio muestra `programa/app/static/tutorial.webm` (sin sonido, con los pasos escritos). Para rehacerlo cuando cambie la interfaz: `programa/herramientas/capturar_tutorial.py` toma las capturas con la escuela de ejemplo (necesita `pip install playwright` y Edge o Chrome) y `programa/herramientas/crear_tutorial.py` arma el video.
- **Qué quedó fuera a propósito:** subir desde el celular por la red local, cuentas de usuario y varias escuelas (necesitan un servidor), video con voz, y mover los datos fuera de OneDrive de forma automática.
