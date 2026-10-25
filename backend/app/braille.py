"""Uncontracted (Grade 1) English Braille. Each cell is a set of dot numbers 1-6:
dots 1,2,3 are the left column top to bottom, dots 4,5,6 the right column."""
from __future__ import annotations

LETTERS = {
    "a": "1", "b": "12", "c": "14", "d": "145", "e": "15", "f": "124", "g": "1245", "h": "125", "i": "24", "j": "245",
    "k": "13", "l": "123", "m": "134", "n": "1345", "o": "135", "p": "1234", "q": "12345", "r": "1235", "s": "234",
    "t": "2345", "u": "136", "v": "1236", "w": "2456", "x": "1346", "y": "13456", "z": "1356",
}
DIGITS = {"1": "a", "2": "b", "3": "c", "4": "d", "5": "e", "6": "f", "7": "g", "8": "h", "9": "i", "0": "j"}
PUNCT = {".": "256", ",": "2", ";": "23", ":": "25", "!": "235", "?": "236", "-": "36", "'": "3", "(": "2356", ")": "2356", "/": "34"}
NUMBER_SIGN = "3456"
CAPITAL_SIGN = "6"
SPACE = ""


class BrailleError(ValueError):
    pass


def encode(text: str, capital_sign: bool = False) -> list[set[int]]:
    """Text -> list of cells (each a set of dot numbers). An empty set is a blank cell (space)."""
    cells: list[set[int]] = []
    in_number = False
    for ch in text:
        if ch == " ":
            cells.append(set())
            in_number = False
        elif ch.isdigit() and ch in DIGITS:
            if not in_number:
                cells.append(set(int(c) for c in NUMBER_SIGN))
                in_number = True
            cells.append(set(int(c) for c in LETTERS[DIGITS[ch]]))
        elif ch.lower() in LETTERS:
            in_number = False
            if ch.isupper() and capital_sign:
                cells.append(set(int(c) for c in CAPITAL_SIGN))
            cells.append(set(int(c) for c in LETTERS[ch.lower()]))
        elif ch in PUNCT:
            in_number = False
            cells.append(set(int(c) for c in PUNCT[ch]))
        else:
            raise BrailleError(f"Cannot write '{ch}' in Braille. Use letters, digits, spaces and . , ; : ! ? - ' ( ) /")
    return cells


def dot_position(dot: int) -> tuple[int, int]:
    """Dot number -> (column 0/1, row 0/1/2 from the top)."""
    return (0, dot - 1) if dot <= 3 else (1, dot - 4)
