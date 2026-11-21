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

La pantalla de **Inicio** dice qué sigue en cada momento. Los pasos son:

1. **Grupos.** Crea cada grupo con su lista de alumnos una sola vez. Los exámenes usan esa lista. Si eliminas un grupo, sus exámenes pasan a la papelera y se pueden restaurar.
2. **Exámenes.** Se crea en cinco pasos: grupo, materia, cuál examen es, cuántos puntos vale y las series del examen. En el tablero de bimestres y parciales, lo que ya se hizo sale en verde con ✓ y no se puede repetir.
   - **Series:** un examen se arma con series (Serie I, Serie II…). Cada serie es de opciones (A–D) o de respuesta escrita, puede llevar una imagen, tiene sus puntos y el programa los reparte entre sus preguntas (una serie de 10 puntos con 4 preguntas vale 2.5 cada una). La suma de las series no puede pasar de la nota del examen; si queda por debajo, la nota se calcula sobre lo repartido. Las series se acomodan una tras otra y solo se agrega una hoja cuando la anterior se llena, así no sobran hojas vacías. Una hoja con opciones y preguntas escritas se califica en un paso: la cámara lee las burbujas y tú marcas lo escrito.
   - Las preguntas se escriben dentro de cada serie: «Escribir pregunta» abre una ventana con una vista previa abajo. Las guardadas se reutilizan y se pueden borrar. Para rehacer uno, primero se elimina. Cada examen es de una materia. Todas las hojas salen en un solo PDF.
   - **Apagar examen:** un examen apagado ya no recibe hojas en la cámara, pero conserva sus notas. Se vuelve a encender cuando quieras.
   - **Eliminar:** manda el examen a la papelera. Se puede deshacer o restaurar con sus notas. Solo «Borrar para siempre» lo quita de verdad.
3. **Calificar.** Elige el examen, enciende la cámara y pasa las hojas. El programa lee el QR solo y suena un aviso con cada hoja. Si una hoja es de otro examen o el examen está apagado, lo avisa. Las notas caen en un cuadro tipo Excel, por materia, que se filtra por bimestre y se descarga para Excel. También se puede subir una foto.
4. **Notas del año.** Una materia a la vez, con los cuatro bimestres juntos: zona (parciales y actividades), examen final y total de cada bimestre, más el promedio anual.
5. **Análisis (opcional).** Qué falló el grupo y hojas de refuerzo para quien lo necesita.

La nota real son los puntos sobre la nota total del examen. La nota relativa usa la misma escala, pero el mejor del examen se lleva la nota completa. El diagnóstico no suma a los bimestres.

Los datos quedan solo en esta computadora. Cada día, antes del primer cambio, se guarda una copia en `data/copias/` (se conservan las últimas 14).
