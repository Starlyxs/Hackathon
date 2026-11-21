# Hojas en papel

Corrección de diagnósticos impresos con la cámara de la laptop del maestro. El programa vive en esa computadora: no hace falta internet, ni un celular por alumno, ni subir las hojas a un servidor.

## Por qué no es un APK ni un sitio en Astro

El motor es Python y OpenCV. Un APK obligaría a reescribirlo para Android, y el celular del encargo solo hace de cámara sobre un soporte. Astro arma páginas estáticas: no abre la webcam, no corre OpenCV y no trabaja sin red. La interfaz es una página local que el navegador abre en `http://127.0.0.1:8000`.

## Arranque

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m app.selfcheck
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`selfcheck` genera hojas, les toma una foto simulada (perspectiva, escritorio y JPEG) y comprueba que el lector recupere al alumno, la calificación y el patrón de grupo.

## Qué hace hoy

- Imprime un diagnóstico de opción múltiple, el mismo para el grupo, con un QR por alumno.
- Alinea la hoja con los cuadros negros de las esquinas, lee el QR y las burbujas.
- Si un mismo error aparece en la mitad del grupo o más, lo dice en una frase.
- Genera una hoja de refuerzo con reactivos de las habilidades que ese alumno falló.

La letra manuscrita queda fuera de esta versión. Con una webcam modesta, la burbuja llena se lee con fiabilidad; un párrafo escrito a lápiz, no.
