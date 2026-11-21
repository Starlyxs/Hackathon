# Hojas en papel

Corrección de diagnósticos impresos con la cámara de la laptop del maestro. El programa vive en esa computadora: no hace falta internet ni un celular por alumno.

## Descargar y ejecutar

La forma más parecida a un programa instalado es la carpeta `dist\HojasEnPapel`. Ahí está `HojasEnPapel.exe`, con el logo y con Python ya adentro. Se copia **toda** la carpeta a la otra computadora y se abre el exe. Los exámenes quedan en una carpeta `datos` al lado del exe, solo en esa máquina.

Windows puede bloquear ese exe porque no tiene firma digital. Si aparece “una directiva de Control de aplicaciones bloqueó este archivo”, usa el arranque con código:

1. Copia la carpeta del proyecto.
2. Doble clic en `iniciar.bat`. Si falta Python, lo descarga e instala solo.
3. En Mac o Linux: `bash iniciar.sh` (ahí sí hace falta Python 3.11).

La primera vez con `iniciar.bat` usa internet. Después el programa abre `http://127.0.0.1:8000` y trabaja sin red.

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

## Cómo se usa, paso a paso

1. **Preguntas.** Escribe las preguntas por materia.
2. **Exámenes.** Aquí se crean. Eliges grupo, bimestre (1 a 4), si es parcial, examen final, actividad o diagnóstico, y la nota total (los puntos que vale). Un mismo examen no se puede crear dos veces: por ejemplo, el Parcial 1 del Bimestre 2 de un grupo y una materia. Si hubo un error, se elimina en «Mis exámenes» y se crea otra vez. Todas las hojas salen en un solo PDF.
3. **Calificar.** Pasa cada hoja frente a la cámara. Las notas caen en un cuadro tipo Excel, con una columna por examen. Se puede filtrar por bimestre y descargar para Excel.
4. **Notas del año.** Los cuatro bimestres juntos: zona (parciales y actividades), examen final y total de cada bimestre, más el promedio anual.

La nota real son los puntos sobre la nota total del examen. La nota relativa usa la misma escala, pero el mejor del examen se lleva la nota completa. El diagnóstico no suma a los bimestres.
