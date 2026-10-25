import pytest
from app.braille import BrailleError, encode


def test_letters():
    assert encode("a") == [{1}] and encode("c") == [{1, 4}] and encode("z") == [{1, 3, 5, 6}]


def test_numbers_get_one_number_sign():
    cells = encode("12")
    assert cells[0] == {3, 4, 5, 6} and cells[1] == {1} and cells[2] == {1, 2} and len(cells) == 3


def test_number_sign_repeats_after_space():
    assert len(encode("1 2")) == 5


def test_capital_sign_optional():
    assert len(encode("Ab")) == 2 and len(encode("Ab", capital_sign=True)) == 3


def test_punctuation_and_errors():
    assert encode("!") == [{2, 3, 5}]
    with pytest.raises(BrailleError):
        encode("é")
