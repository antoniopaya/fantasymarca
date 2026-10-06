"""Emparejamiento aproximado de nombres abreviados ("Fermín L.", "Javi Hdez.") contra el catálogo de Marca."""

import difflib
import re
import unicodedata

# Abreviaturas de apellido habituales en el Excel/PDF de la liga que el catálogo escribe completas.
SURNAME_ABBREVIATIONS = {
    "fdez": "fernandez",
    "glez": "gonzalez",
    "hdez": "hernandez",
    "mtnez": "martinez",
    "rguez": "rodriguez",
}


def normalize_tokens(name: str) -> list[str]:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    ascii_name = ascii_name.lower().replace("-", " ")
    ascii_name = re.sub(r"[^a-z0-9. ]", "", ascii_name)
    tokens = []
    for tok in ascii_name.split():
        tok = tok.rstrip(".")
        tokens.append(SURNAME_ABBREVIATIONS.get(tok, tok))
    return tokens


def token_score(e_tokens: list[str], c_tokens: list[str]) -> float:
    total_weight = total_score = 0.0
    for tok in e_tokens:
        weight = 1.0 if len(tok) > 1 else 0.4  # una inicial sola pesa menos que un nombre completo
        if len(tok) == 1:
            best = 1.0 if any(c.startswith(tok) for c in c_tokens) else 0.0
        else:
            best = max((difflib.SequenceMatcher(None, tok, c).ratio() for c in c_tokens), default=0.0)
        total_score += weight * best
        total_weight += weight
    return total_score / total_weight if total_weight else 0.0
