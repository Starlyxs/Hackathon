# Nexam

Nexam califica exámenes impresos. El maestro crea el examen, lo imprime con un QR por alumno, escanea las hojas con el celular en un solo PDF y lo sube. El programa lee las respuestas, pone las notas y muestra qué le falta a cada alumno y al grupo.

Funciona en la computadora del maestro, sin internet y sin celulares para los alumnos.

## Qué hace

- Crea exámenes por materia, con series de opciones (A–D) o de respuesta escrita, y reparte los puntos.
- Imprime una hoja por alumno, con números distintos en cada una y un QR propio.
- Lee el PDF escaneado: sabe de quién es cada hoja aunque vengan mezcladas, torcidas o al revés.
- Avisa a quién le falta una hoja y quién no entregó.
- Deja corregir a mano una burbuja mal leída y revisar lo escrito viendo la hoja escaneada.
- Junta las notas de los cuatro bimestres y las descarga para Excel.
- Muestra gráficos del grupo, de cada materia y de todo el año, con un texto para cada alumno y su hoja de refuerzo.
- Imprime boletines por alumno.

## Instalar y abrir

Necesita Windows 10 u 11 (también sirve Mac o Linux), un navegador, 4 GB de memoria y unos 500 MB libres. **Internet solo la primera vez.**

**Windows**

1. Copia la carpeta completa a la computadora.
2. Doble clic en **`iniciar.bat`**. La primera vez tarda unos minutos; no cierres la ventana negra.
3. Se abre el navegador con Nexam. Si no, escribe `http://127.0.0.1:8000`.

Si la computadora **no tiene Python**, `iniciar.bat` lo descarga e instala solo (necesita internet). Si no hay internet, instálalo desde <https://www.python.org/downloads/> (versión 3.11, 3.12 o 3.13, marcando «Add python.exe to PATH») y abre `iniciar.bat` otra vez.

Si Windows dice «protegió su PC», pulsa **Más información** y **Ejecutar de todas formas**.

**Mac o Linux:** en una terminal dentro de la carpeta, `bash iniciar.sh` (necesita Python 3.11 a 3.13).

## Volver a abrir y cerrar

- **Abrir:** el icono **Nexam** del escritorio, o `iniciar.bat`. Abre en segundos y sin internet.
- **Cerrar:** cierra la ventana negra. Los datos quedan guardados.
- Si cierras solo la pestaña, escribe `http://127.0.0.1:8000` en el navegador.

## Cómo se usa

1. **Grupos:** crea cada grupo con sus alumnos una sola vez.
2. **Exámenes:** elige grupo, materia y tipo de examen, arma las series y descarga el PDF para imprimir. Cada materia trae sus propios temas, y en las preguntas de opciones puedes escribir tus respuestas falsas o dejar que el programa las invente.
3. **Calificar:** escanea las hojas con el celular (Google Drive, Notas del iPhone o CamScanner), junta todo en un PDF y súbelo. Para pasar el PDF a la computadora sirve el cable USB, Quick Share, Google Drive o WhatsApp Web.
4. **Notas:** tabla por materia y bimestre, descargable para Excel, y boletines para imprimir.
5. **Análisis:** resultados del grupo y de cada alumno, por examen, por materia o en general.

## Probar sin papel

En **Inicio**, «Cargar prueba simulada» crea un grupo de ejemplo con exámenes calificados y PDFs para subir, y así se ve todo sin imprimir. «Borrar la prueba simulada» lo quita.

## Datos

Todo se guarda solo en esa computadora, en `programa/data/`, con una copia automática diaria. En Inicio puedes descargar una copia de seguridad. Para pasar el programa a otra computadora, copia la carpeta completa.

Si la carpeta está dentro de OneDrive, mejor muévela a `C:\Nexam`: la sincronización puede dañar el archivo de datos.

## Si algo falla

- **La ventana se cierra sola:** abre una terminal en la carpeta, ejecuta `iniciar.bat` y lee el mensaje.
- **No descarga Python o las librerías:** falta internet. Conéctate y vuelve a abrir; solo se necesita la primera vez.
- **El navegador no abre la página:** revisa que la ventana negra siga abierta.
- **Una hoja no se lee:** la página `/ayuda` dentro del programa explica los casos comunes.
