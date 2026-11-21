"""Banco de reactivos de opción múltiple.

La lectura abierta y la letra manuscrita no entran en esta primera versión:
con la cámara de una laptop vieja la burbuja llena es fiable; el OCR de
párrafos escritos a lápiz no lo es. Comprensión lectora sí entra, en
preguntas cerradas.
"""

SKILLS = {
    "area": "área y perímetro",
    "fracciones": "fracciones",
    "valor_posicional": "valor posicional",
    "operaciones": "operaciones",
    "comprension": "comprensión lectora",
    "general": "ejercicio",
}

# Cuántas preguntas de cada habilidad entran en un diagnóstico.
FORM_PLAN = (
    ("area", 2),
    ("fracciones", 2),
    ("valor_posicional", 2),
    ("operaciones", 1),
    ("comprension", 1),
)

BANK = [
    {
        "skill": "area",
        "prompt": "Un rectángulo mide 5 cm de largo y 3 cm de ancho. ¿Cuál es su área?",
        "options": ["16 cm", "15 cm²", "8 cm²", "30 cm"],
        "answer": 1,
        "trap": 0,
        "trap_label": "confunde el área con el perímetro",
    },
    {
        "skill": "area",
        "prompt": "Un cuadrado tiene lados de 6 cm. ¿Cuál es su área?",
        "options": ["24 cm", "36 cm²", "12 cm²", "6 cm"],
        "answer": 1,
        "trap": 0,
        "trap_label": "confunde el área con el perímetro",
    },
    {
        "skill": "area",
        "prompt": "Un rectángulo mide 8 cm por 2 cm. ¿Cuál es su área?",
        "options": ["20 cm", "16 cm²", "10 cm²", "32 cm"],
        "answer": 1,
        "trap": 0,
        "trap_label": "confunde el área con el perímetro",
    },
    {
        "skill": "fracciones",
        "prompt": "¿Cuánto es 1/2 + 1/4?",
        "options": ["2/6", "3/4", "1/6", "1/8"],
        "answer": 1,
        "trap": 0,
        "trap_label": "suma numeradores y denominadores por separado",
    },
    {
        "skill": "fracciones",
        "prompt": "¿Cuánto es 1/3 + 1/3?",
        "options": ["2/6", "2/3", "1/6", "1/9"],
        "answer": 1,
        "trap": 0,
        "trap_label": "suma numeradores y denominadores por separado",
    },
    {
        "skill": "fracciones",
        "prompt": "¿Cuánto es 3/4 + 1/4?",
        "options": ["4/8", "1", "3/8", "1/4"],
        "answer": 1,
        "trap": 0,
        "trap_label": "suma numeradores y denominadores por separado",
    },
    {
        "skill": "valor_posicional",
        "prompt": "En el número 47, ¿cuánto vale el 4?",
        "options": ["4", "40", "47", "400"],
        "answer": 1,
        "trap": 0,
        "trap_label": "lee el dígito y no su valor de posición",
    },
    {
        "skill": "valor_posicional",
        "prompt": "En el número 305, ¿cuánto vale el 3?",
        "options": ["3", "300", "30", "305"],
        "answer": 1,
        "trap": 0,
        "trap_label": "lee el dígito y no su valor de posición",
    },
    {
        "skill": "valor_posicional",
        "prompt": "En el número 82, ¿cuánto vale el 8?",
        "options": ["8", "80", "82", "800"],
        "answer": 1,
        "trap": 0,
        "trap_label": "lee el dígito y no su valor de posición",
    },
    {
        "skill": "operaciones",
        "prompt": "Luis tenía 15 pesos y gastó 7. ¿Cuánto le queda?",
        "options": ["8", "22", "9", "7"],
        "answer": 0,
        "trap": 1,
        "trap_label": "suma cuando el problema pide restar",
    },
    {
        "skill": "operaciones",
        "prompt": "Había 12 aves y se fueron 4. ¿Cuántas quedan?",
        "options": ["8", "16", "9", "4"],
        "answer": 0,
        "trap": 1,
        "trap_label": "suma cuando el problema pide restar",
    },
    {
        "skill": "comprension",
        "prompt": "Lee: «El gato duerme en la silla.» ¿Quién duerme?",
        "options": ["la silla", "el gato", "el niño", "nadie"],
        "answer": 1,
        "trap": 0,
        "trap_label": "contesta con el lugar y no con quien hace la acción",
    },
    {
        "skill": "comprension",
        "prompt": "Lee: «Lucía riega las plantas cada mañana.» ¿Qué hace Lucía?",
        "options": ["juega", "riega las plantas", "duerme", "come"],
        "answer": 1,
        "trap": 0,
        "trap_label": "elige una acción que el texto no dice",
    },
]


def build_questions(rng):
    picked = []
    for skill, count in FORM_PLAN:
        pool = [dict(item) for item in BANK if item["skill"] == skill]
        if len(pool) < count:
            raise RuntimeError(f"Faltan reactivos de {skill}")
        picked.extend(rng.sample(pool, count))
    return picked
