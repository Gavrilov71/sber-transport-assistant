"""Conservative check for concrete numeric claims against cited tool evidence."""
import re

URL = re.compile(r"https?://\S+", re.I)
PHONE = re.compile(r"(?<!\w)\+?\d[\d\s()\-]{7,}\d")
DATE = re.compile(r"(?<!\w)\d{1,2}[./]\d{1,2}[./]\d{2,4}(?!\w)")
MEASURE = re.compile(
    r"(?<!\w)(\d+(?:[.,]\d+)?)(?:\s*[-–—]\s*(\d+(?:[.,]\d+)?))?\s*"
    r"(минут\w*|час\w*|дн\w*|дней|руб\w*|₽|км|километр\w*|%|процент\w*)",
    re.I,
)
NUMBER = re.compile(r"(?<!\w)\d+(?:[.,]\d+)?(?!\w)")


def _unit(value: str) -> str:
    word = value.lower()
    for stem, canonical in (("минут", "minutes"), ("час", "hours"), ("дн", "days"),
                            ("дней", "days"), ("руб", "rubles"), ("₽", "rubles"),
                            ("км", "km"), ("километр", "km"), ("процент", "percent"),
                            ("%", "percent")):
        if word.startswith(stem):
            return canonical
    return word


def _facts(text: str) -> tuple[set[str], set[str], set[str], set[str]]:
    text = URL.sub(" ", text.replace("–", "-").replace("—", "-"))
    phones = {re.sub(r"\D", "", match.group()) for match in PHONE.finditer(text)}
    text = PHONE.sub(" ", text)
    dates = {match.group().replace("/", ".") for match in DATE.finditer(text)}
    text = DATE.sub(" ", text)
    measures = set()
    for match in MEASURE.finditer(text):
        numbers = match.group(1).replace(",", ".")
        if match.group(2):
            numbers += "-" + match.group(2).replace(",", ".")
        measures.add(f"{numbers}:{_unit(match.group(3))}")
    text = MEASURE.sub(" ", text)
    numbers = {match.group().replace(",", ".") for match in NUMBER.finditer(text)}
    return phones, dates, measures, numbers


def unsupported_concrete_facts(answer: str, evidence: str) -> list[str]:
    """Only accept exact phone/date/quantity evidence; unknown claims fail closed."""
    claims = _facts(answer)
    supported = _facts(evidence)
    return sorted(set().union(*(claim - proof for claim, proof in zip(claims, supported))))
