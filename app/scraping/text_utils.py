"""Text helpers for scraped Facebook posts: phone numbers and location matching."""

import re
from typing import Optional

# Loose phone pattern: optional country code, then 2-4 groups of digits.
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,4}\d{2,4}")
WHATSAPP_RE = re.compile(r"(?:wa\.me|whatsapp\.com/send\?phone=)[^\s\"']*", re.I)

# Lines Facebook injects into every result card.
NOISE_LINES = {"Facebook", "Indicador de estado online", "Activo", "Contenido de IA"}
SYMBOL_LINE_RE = re.compile(r"^[\s·•|.,:;\-–—]+$")

DATE_RE = re.compile(
    r"^(hace\s|lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo|\d{1,2}\s+de\s)",
    re.I,
)
AUTHOR_NOISE = {"Unirte", "Seguir", "Unirse", "Ver más", "Responder", "Compartir"}

# Excluded when picking a bare profile URL out of a result card.
PROFILE_EXCLUDE_RE = re.compile(
    r"facebook\.com/(search|marketplace|watch|gaming|groups|pages|events|photos?|reels"
    r"|menu|home|login|help|settings|privacy|terms|ads|business|story\.php|permalink\.php|video)",
    re.I,
)


def clean_lines(raw: str) -> list[str]:
    """Split innerText into meaningful lines (drops FB chrome and separators)."""
    cleaned: list[str] = []
    for raw_line in (raw or "").split("\n"):
        line = raw_line.strip()
        if line and line not in NOISE_LINES and not SYMBOL_LINE_RE.match(line):
            cleaned.append(line)
    return cleaned


def extract_phones(text: str) -> list[str]:
    """
    Extract phone numbers from a post, filtering out reaction counters.

    Facebook renders counters on separate lines ("337\\n22\\n16"), which the
    loose pattern would otherwise stitch together into a fake number.
    """
    if not text:
        return []

    found: list[str] = []
    for match in PHONE_RE.findall(text):
        if "\n" in match:
            continue
        digits = re.sub(r"\D", "", match)
        if not 7 <= len(digits) <= 15:
            continue

        has_plus = "+" in match
        has_paren = "(" in match
        separators = len(re.sub(r"^\+", "", match).translate(str.maketrans("", "", "0123456789")))
        contiguous = separators == 0

        # "+51 999...", "(073) 444...", "999 888 777", or a bare 9-11 digit block.
        valid = (
            has_plus
            or has_paren
            or separators >= 2
            or (contiguous and 9 <= len(digits) <= 11)
            or (separators == 1 and len(digits) >= 9)
        )
        if not valid:
            continue

        number = ("+" + digits) if has_plus else digits
        if number not in found:
            found.append(number)
    return found


def extract_whatsapp(text: str) -> list[str]:
    if not text:
        return []
    return list(dict.fromkeys(WHATSAPP_RE.findall(text)))


def match_location(text: str, city: str, localities: list[str]) -> Optional[str]:
    """Return the locality token found in the text, or None."""
    haystack = text or ""
    for token in [city, *localities]:
        if token and re.search(rf"\b{re.escape(token)}\b", haystack, re.I):
            return token
    return None


def pick_author(lines: list[str]) -> Optional[str]:
    """Author is the line right above the timestamp in a search result card."""
    for index, line in enumerate(lines):
        if DATE_RE.match(line):
            for candidate in lines[max(0, index - 3) : index][::-1]:
                if candidate not in AUTHOR_NOISE and len(candidate) <= 70:
                    return candidate
            return None
    return None
