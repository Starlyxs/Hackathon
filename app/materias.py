"""Materias del nivel primario en Guatemala.

En muchas escuelas pequeñas una sola persona da Comunicación y Lenguaje,
Matemática, Medio Social y Natural y el resto. El banco se parte por materia
para que el diagnóstico no mezcle todo si el maestro no quiere.
"""

DEFAULT_MATERIAS = (
    "Comunicación y Lenguaje",
    "Matemática",
    "Medio Social y Natural",
    "Ciencias Naturales y Tecnología",
    "Ciencias Sociales",
    "Expresión Artística",
    "Formación Ciudadana",
)


def ensure_materias(db):
    if not db.get("materias"):
        db["materias"] = list(DEFAULT_MATERIAS)
    for row in db.get("authored", []):
        row.setdefault("kind", "cerrada")
        row.setdefault("criterion", "")
        if not row.get("materia"):
            row["materia"] = (
                "Comunicación y Lenguaje" if row.get("skill") == "comprension" else "Matemática"
            )
        if row["materia"] not in db["materias"]:
            db["materias"].append(row["materia"])
