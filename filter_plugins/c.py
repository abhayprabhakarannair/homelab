def c_string(value):
    """C/C++ string literal with the exact UTF-8 bytes of value.

    Printable ASCII is kept; everything else becomes a three-digit octal escape, which never absorbs a following
    character (unlike \\x) and is valid for any byte, including NUL-free control characters and non-BMP code points.
    """
    if not isinstance(value, str):
        raise TypeError(f"c_string expects str, got {type(value).__name__}")
    out = []
    for byte in value.encode():
        ch = chr(byte)
        if ch in '"\\':
            out.append("\\" + ch)
        elif ch == "?":
            out.append("\\?")
        elif 0x20 <= byte < 0x7F:
            out.append(ch)
        else:
            out.append(f"\\{byte:03o}")
    return '"' + "".join(out) + '"'


class FilterModule:
    def filters(self):
        return {"c_string": c_string}
