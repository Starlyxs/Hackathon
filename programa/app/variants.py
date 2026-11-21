"""Arma una versión distinta de la pregunta para cada alumno y tres respuestas falsas.

El maestro solo escribe el enunciado y la respuesta correcta. Si esa respuesta
sale de los números del enunciado (suma, resta, multiplicación, área,
perímetro, fracción o valor de posición), cada alumno recibe otras cifras y
la clave se recalcula. Si no se puede recalcular sin inventar, el enunciado
se queda igual y cambian la letra correcta y las opciones falsas.
"""

import random
import re

from app.bank import SKILLS

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_FRACTION_SUM = re.compile(r"(\d+)\s*/\s*(\d+)\s*\+\s*(\d+)\s*/\s*(\d+)")
_ANSWER_NUMBER = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*(.*?)\s*$")
_ANSWER_FRACTION = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*(.*?)\s*$")
_WORD = re.compile(r"[A-Za-zÁÉÍÓÚÜáéíóúüÑñ]+")

_STOP = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al",
    "y", "o", "que", "qué", "cual", "cuál", "cuanto", "cuánto", "es", "son",
    "por", "para", "con", "sin", "su", "sus", "se", "en", "cm", "cm2",
    "número", "numero", "vale", "cuánto", "como", "más", "mas", "menos",
}

_SKILL_OF = {
    "area": "area",
    "perimetro": "area",
    "suma": "operaciones",
    "resta": "operaciones",
    "producto": "operaciones",
    "division": "operaciones",
    "doble": "operaciones",
    "mitad": "operaciones",
    "fraccion": "fracciones",
    "posicion": "valor_posicional",
}

NOTE_VARIED = "Cada alumno recibe otros números y la respuesta correcta se vuelve a calcular."
NOTE_SAME = (
    "No cambié las cifras: la respuesta no sale de operar los números del enunciado. "
    "Sí cambian la letra correcta y las respuestas falsas."
)
NOTE_TEXT = (
    "La respuesta es una frase: el enunciado queda igual, cambian la letra correcta "
    "y las respuestas falsas salen de otras palabras del texto."
)


def vary_question(source, rng, used=None):
    used = used if used is not None else set()
    last = None
    for _ in range(30):
        question, note = _once(source, rng)
        signature = question["prompt"] + "|" + "|".join(question["options"])
        if signature not in used:
            used.add(signature)
            question["note"] = note
            return question
        last = question
        last["note"] = note
    return last


def parse_answer(answer):
    fraction = _ANSWER_FRACTION.match(answer.strip())
    if fraction and int(fraction.group(2)) != 0:
        return {
            "kind": "fraction",
            "value": int(fraction.group(1)) / int(fraction.group(2)),
            "unit": fraction.group(3).strip(),
        }
    number = _ANSWER_NUMBER.match(answer.strip())
    if number:
        return {
            "kind": "number",
            "value": _to_float(number.group(1)),
            "unit": number.group(2).strip(),
        }
    return {"kind": "text", "text": answer.strip()}


def _once(source, rng):
    prompt = " ".join(source["prompt"].split())
    answer = source["answer"].strip()
    skill = source.get("skill") or "general"
    if skill not in SKILLS and skill != "general":
        skill = "general"
    parsed = parse_answer(answer)
    if parsed["kind"] == "text":
        return _text_question(prompt, parsed["text"], skill, rng), NOTE_TEXT
    built = _numeric_question(prompt, parsed, skill, rng)
    if built is None:
        return _fixed_question(prompt, parsed, skill, rng), NOTE_SAME
    return built, NOTE_VARIED


def _numeric_question(prompt, parsed, skill, rng):
    fraction = _fraction_question(prompt, parsed, skill, rng)
    if fraction is not None:
        return fraction
    numbers = [_to_float(token) for token in _NUMBER.findall(prompt)]
    if not numbers or any(abs(n - round(n)) > 1e-6 for n in numbers):
        return None
    numbers = [int(round(n)) for n in numbers]
    hinted = _hint(prompt, skill)
    place = _place_question(prompt, numbers, parsed, skill, rng, hinted)
    if place is not None:
        return place
    if len(numbers) == 1:
        return _one_number_question(prompt, numbers[0], parsed, skill, rng, hinted)
    if len(numbers) >= 2:
        return _two_number_question(prompt, numbers[0], numbers[1], parsed, skill, rng, hinted)
    return None


def _fraction_question(prompt, parsed, skill, rng):
    match = _FRACTION_SUM.search(prompt)
    if match is None:
        return None
    a, b, c, d = (int(match.group(i)) for i in range(1, 5))
    if b == 0 or d == 0:
        return None
    value = a / b + c / d
    if abs(value - parsed["value"]) > 1e-6:
        return None
    trap_value = (a + c) / (b + d) if (b + d) else None
    for _ in range(40):
        nb, nd = rng.choice((2, 3, 4, 5, 6, 8)), rng.choice((2, 3, 4, 5, 6, 8))
        na = rng.randint(1, nb - 1)
        nc = rng.randint(1, nd - 1)
        if (na, nb, nc, nd) == (a, b, c, d):
            continue
        new_prompt = prompt[: match.start()] + f"{na}/{nb} + {nc}/{nd}" + prompt[match.end() :]
        correct = na / nb + nc / nd
        trap = (na + nc) / (nb + nd)
        return _pack(
            new_prompt,
            parsed,
            correct,
            trap,
            "suma numeradores y denominadores por separado",
            "fracciones" if skill == "general" else skill,
            rng,
            as_fraction=True,
        )
    return None


def _place_question(prompt, numbers, parsed, skill, rng, hinted):
    if hinted not in (None, "posicion"):
        return None
    found = None
    for big in numbers:
        if big < 10:
            continue
        text = str(big)
        for digit in numbers:
            if digit < 0 or digit > 9 or str(digit) not in text:
                continue
            spots = [i for i, char in enumerate(text) if char == str(digit)]
            if len(spots) != 1:
                continue
            place = 10 ** (len(text) - 1 - spots[0])
            if abs(digit * place - parsed["value"]) < 1e-6:
                found = (big, digit, len(text))
                break
        if found:
            break
    if found is None:
        return None
    width = found[2]
    for _ in range(40):
        low = 10 ** (width - 1)
        high = min(10**width - 1, 999)
        new_big = rng.randint(low, high)
        digits = [int(char) for char in str(new_big)]
        unique = [d for d in digits if d != 0 and digits.count(d) == 1]
        if not unique:
            continue
        new_digit = rng.choice(unique)
        if (new_big, new_digit) == found[:2]:
            continue
        spot = str(new_big).index(str(new_digit))
        place = 10 ** (width - 1 - spot)
        new_prompt = _replace_specific(prompt, [(found[0], new_big), (found[1], new_digit)])
        return _pack(
            new_prompt,
            parsed,
            new_digit * place,
            new_digit,
            "lee el dígito y no su valor de posición",
            "valor_posicional" if skill == "general" else skill,
            rng,
            extras=[new_big, new_digit * 100],
        )
    return None


def _one_number_question(prompt, number, parsed, skill, rng, hinted):
    options = []
    if abs(number * 2 - parsed["value"]) < 1e-6:
        options.append(("doble", number, number, "contesta con el número del problema y no con el doble"))
    if number % 2 == 0 and abs(number / 2 - parsed["value"]) < 1e-6:
        options.append(("mitad", number, number, "contesta con el número del problema y no con la mitad"))
    if hinted:
        options = [item for item in options if item[0] == hinted] or options
    if len(options) != 1:
        return None
    name, _, trap, label = options[0]
    for _ in range(20):
        new_n = rng.randint(2, 12)
        if new_n == number:
            continue
        correct = new_n * 2 if name == "doble" else new_n / 2
        return _pack(
            _replace_numbers(prompt, [new_n]),
            parsed,
            correct,
            trap and new_n,
            label,
            _SKILL_OF[name] if skill == "general" else skill,
            rng,
        )
    return None


def _two_number_question(prompt, first, second, parsed, skill, rng, hinted):
    catalog = _catalog(first, second)
    matches = [item for item in catalog if item["value"] is not None and abs(item["value"] - parsed["value"]) < 1e-6]
    if hinted:
        hinted_matches = [item for item in matches if item["name"] == hinted]
        if hinted_matches:
            matches = hinted_matches
    else:
        names = {item["name"] for item in matches}
        if "area" in names and "producto" in names:
            matches = [item for item in matches if item["name"] != "area"]
    if len(matches) != 1:
        return None
    chosen = matches[0]
    for _ in range(40):
        pair = _new_pair(chosen["name"], first, second, rng)
        if pair is None:
            continue
        x, y, correct, trap = pair
        return _pack(
            _replace_numbers(prompt, [x, y]),
            parsed,
            correct,
            trap,
            chosen["label"],
            _SKILL_OF[chosen["name"]] if skill == "general" else skill,
            rng,
            extras=[x, y, x + y, abs(x - y)],
        )
    return None


def _catalog(first, second):
    product = first * second
    total = first + second
    difference = first - second if first >= second else None
    perimeter = 2 * (first + second)
    quotient = first / second if second else None
    return [
        {"name": "area", "value": product, "label": "confunde el área con el perímetro"},
        {"name": "perimetro", "value": perimeter, "label": "confunde el perímetro con el área"},
        {"name": "producto", "value": product, "label": "suma cuando el problema pide multiplicar"},
        {"name": "suma", "value": total, "label": "multiplica cuando el problema pide sumar"},
        {
            "name": "resta",
            "value": difference,
            "label": "suma cuando el problema pide restar",
        },
        {
            "name": "division",
            "value": quotient if quotient is not None and abs(quotient - round(quotient)) < 1e-6 else None,
            "label": "resta cuando el problema pide dividir",
        },
    ]


def _new_pair(name, first, second, rng):
    if name == "resta":
        y = rng.randint(2, 9)
        x = y + rng.randint(2, 12)
        if (x, y) == (first, second):
            return None
        return x, y, x - y, x + y
    if name == "division":
        y = rng.randint(2, 9)
        quotient = rng.randint(2, 12)
        x = y * quotient
        if (x, y) == (first, second):
            return None
        return x, y, quotient, x - y
    x = rng.randint(2, 12)
    y = rng.randint(2, 12)
    if (x, y) == (first, second):
        return None
    if name == "perimetro":
        return x, y, 2 * (x + y), x * y
    if name in ("area", "producto"):
        trap = 2 * (x + y) if name == "area" else x + y
        return x, y, x * y, trap
    if name == "suma":
        return x, y, x + y, x * y
    return None


def _fixed_question(prompt, parsed, skill, rng):
    correct = parsed["value"]
    return _pack(prompt, parsed, correct, None, None, skill, rng, extras=[correct + 1, correct - 1, correct * 2])


def _text_question(prompt, answer, skill, rng):
    words = []
    seen = set()
    for word in _WORD.findall(prompt):
        key = word.casefold()
        if key in _STOP or key == answer.casefold() or len(word) < 3 or key in seen:
            continue
        seen.add(key)
        words.append(word)
    fillers = ["nadie", "otra cosa", "no se dice", "todos"]
    wrong = words[:3]
    for filler in fillers:
        if len(wrong) >= 3:
            break
        if filler.casefold() != answer.casefold():
            wrong.append(filler)
    while len(wrong) < 3:
        wrong.append(f"opción {len(wrong) + 1}")
    return _finish(prompt, answer, wrong[:3], None, None, skill, rng)


def _pack(prompt, parsed, correct, trap, label, skill, rng, extras=None, as_fraction=False):
    correct_text = _format(correct, parsed, as_fraction)
    trap_text = None if trap is None else _format(trap, parsed, as_fraction)
    wrong_values = []
    if trap is not None:
        wrong_values.append(trap)
    for extra in extras or []:
        wrong_values.append(extra)
    step = 1
    while len(wrong_values) < 8 and step < 12:
        wrong_values.append(correct + step)
        wrong_values.append(max(0, correct - step))
        step += 1
    wrong_text = []
    for value in wrong_values:
        if value is None or (isinstance(value, (int, float)) and value < 0):
            continue
        text = _format(value, parsed, as_fraction)
        if text == correct_text or text in wrong_text:
            continue
        wrong_text.append(text)
        if len(wrong_text) == 3:
            break
    while len(wrong_text) < 3:
        spare = f"{int(correct) + len(wrong_text) + 3}"
        if spare not in wrong_text and spare != correct_text:
            wrong_text.append(spare)
    trap_text = trap_text if trap_text in wrong_text else None
    return _finish(prompt, correct_text, wrong_text[:3], trap_text, label, skill, rng)


def _finish(prompt, correct_text, wrong_text, trap_text, label, skill, rng):
    options = [correct_text, *wrong_text[:3]]
    rng.shuffle(options)
    trap_index = options.index(trap_text) if trap_text in options else None
    return {
        "prompt": prompt,
        "options": options,
        "answer": options.index(correct_text),
        "trap": trap_index,
        "trap_label": label if trap_index is not None else None,
        "skill": skill if skill in SKILLS else "general",
    }


def _format(value, parsed, as_fraction):
    if as_fraction:
        text = _format_fraction(value)
    else:
        whole = round(value)
        text = str(int(whole)) if abs(value - whole) < 1e-6 else f"{value:.2f}".rstrip("0").rstrip(".")
    unit = parsed.get("unit") or ""
    if unit:
        return f"{text} {unit}"
    return text


def _format_fraction(value):
    den = 48
    num = round(value * den)
    if abs(value - num / den) > 1e-6:
        whole = round(value)
        if abs(value - whole) < 1e-6:
            return str(int(whole))
        return f"{value:.2f}".rstrip("0").rstrip(".")
    common = _gcd(abs(num), den)
    num //= common
    den //= common
    if den == 1:
        return str(num)
    return f"{num}/{den}"


def _hint(prompt, skill):
    text = prompt.casefold()
    if skill == "valor_posicional" or "vale el" in text or "valor de posición" in text or "valor posicional" in text:
        return "posicion"
    if skill == "fracciones" or _FRACTION_SUM.search(prompt):
        return "fraccion"
    if skill == "area" or "área" in text or "area" in text:
        return "area"
    if "perímetro" in text or "perimetro" in text:
        return "perimetro"
    if any(word in text for word in ("repart", "divid")):
        return "division"
    if any(word in text for word in ("doble", "duplic")):
        return "doble"
    if "mitad" in text:
        return "mitad"
    if any(word in text for word in ("resta", "menos", "gastó", "gasto", "quedan", "se fueron", "quedó", "quedo")):
        return "resta"
    if any(word in text for word in ("multiplic", "por cada", "veces")):
        return "producto"
    if any(word in text for word in ("suma", " más ", " mas ", "+")):
        return "suma"
    return None


def _replace_specific(prompt, pairs):
    pending = list(pairs)

    def swap(match):
        value = int(round(_to_float(match.group())))
        for index, (old, new) in enumerate(pending):
            if value == old:
                pending.pop(index)
                return str(int(new))
        return match.group()

    return _NUMBER.sub(swap, prompt)


def _replace_numbers(prompt, values):
    pieces = []
    cursor = 0
    for index, match in enumerate(_NUMBER.finditer(prompt)):
        pieces.append(prompt[cursor : match.start()])
        if index < len(values):
            pieces.append(str(int(values[index])))
        else:
            pieces.append(match.group())
        cursor = match.end()
    pieces.append(prompt[cursor:])
    return "".join(pieces)


def _to_float(token):
    return float(token.replace(",", "."))


def _gcd(a, b):
    while b:
        a, b = b, a % b
    return a or 1


def preview_variants(prompt, answer, skill, count=3):
    rng = random.Random(f"{prompt}|{answer}|{skill}")
    used = set()
    rows = []
    names = ("Ana", "Luis", "María", "Pedro", "Sofía")
    for name in names[:count]:
        question = vary_question(
            {"prompt": prompt, "answer": answer, "skill": skill},
            random.Random(rng.randrange(1, 10**9)),
            used,
        )
        rows.append(
            {
                "student_name": name,
                "prompt": question["prompt"],
                "options": question["options"],
                "answer": question["answer"],
                "note": question["note"],
            }
        )
    return rows
