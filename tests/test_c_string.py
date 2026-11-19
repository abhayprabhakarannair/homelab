import pytest
from c import FilterModule, c_string


@pytest.mark.parametrize(
    ("value", "literal"),
    [
        ("", '""'),
        ("plain", '"plain"'),
        ('a"b', r'"a\"b"'),
        ("a\\b", r'"a\\b"'),
        ("??=", r'"\?\?="'),
        ("é", r'"\303\251"'),
        ("😀", r'"\360\237\230\200"'),
        ("\t\n", r'"\011\012"'),
        ("\x7f", r'"\177"'),
        ("\x01" + "7", r'"\0017"'),
    ],
)
def test_literal(value, literal):
    assert c_string(value) == literal


def test_rejects_non_strings():
    with pytest.raises(TypeError):
        c_string(42)


def test_registered_as_filter():
    assert FilterModule().filters()["c_string"] is c_string
