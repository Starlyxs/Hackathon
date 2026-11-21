# Hojas en papel

Corrección de diagnósticos impresos con la cámara de la laptop del maestro. El programa vive en esa computadora: no hace falta internet ni un celular por alumno.

## Descargar y ejecutar

Hace falta Python 3.11 o más nuevo. En Windows, durante la instalación, marca **Add python.exe to PATH**. Se descarga en [python.org/downloads](https://www.python.org/downloads/).

1. Descarga esta carpeta (ZIP o `git clone`) y descomprímela.
2. Ábrela y ejecuta el arranque:
   - Windows: doble clic en `iniciar.bat`
   - Mac o Linux: en la terminal, `bash iniciar.sh`
3. La primera vez descarga las librerías, así que esa vez sí necesita internet. El navegador abre `http://127.0.0.1:8000`.

No copies la carpeta `.venv` de una computadora a otra. El script la crea en la máquina donde se ejecuta. Las hojas y las preguntas quedan en `data/` de esa misma laptop.

Para comprobar la cámara simulada, sin imprimir:

```powershell
.\.venv\Scripts\python -m app.selfcheck
```

En Mac o Linux el comando es `.venv/bin/python -m app.selfcheck`.

## Qué hace

- El maestro escribe preguntas por materia y el programa arma las opciones A, B, C y D, con números distintos para cada alumno.
- Imprime la hoja con un QR por alumno.
- La cámara lee las burbujas, califica y señala si el mismo error se repite en la mitad del grupo o más.
- En las preguntas abiertas, el alumno escribe con lápiz. La cámara identifica la hoja y el maestro marca si logró la idea.
- Genera una hoja de refuerzo para quien falló.
