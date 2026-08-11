"""Free-text address parser. Verbatim from phase3/server.py:parse_address."""


def parse_address(q: str):
    """Very loose 'Street 12, 10435' parser. Returns (street, hnr, plz) or None.
    Tolerates:
      - stray commas inside tokens ('Kastanienallee 12, Prenzlauer Berg, 10435')
      - trailing 'Berlin' suffix ('Kastanienallee 12, 10435 Berlin')
      - borough/district injected between street and PLZ (silently dropped —
        the street+hnr+plz triple is what the geocoder needs)."""
    q = (q or "").strip()
    if not q:
        return None
    if "," in q:
        left, right = q.rsplit(",", 1)
        plz = "".join(ch for ch in right if ch.isdigit())[:5]
    else:
        parts = q.split()
        if len(parts) < 2: return None
        # Drop a trailing 'Berlin' before scanning for the PLZ.
        if parts[-1].lower() == "berlin" and len(parts) >= 3:
            parts = parts[:-1]
        plz = parts[-1] if parts[-1].isdigit() and len(parts[-1]) == 5 else ""
        left = " ".join(parts[:-1]) if plz else q
    # Tokenise, stripping trailing punctuation (commas, semicolons) that stick
    # to tokens when users write '59, Charlottenburg' etc.
    tokens = [t.strip(",;.") for t in left.strip().split() if t.strip(",;.")]
    hnr = ""
    for i in range(len(tokens) - 1, -1, -1):
        if any(ch.isdigit() for ch in tokens[i]):
            hnr = tokens[i]; street = " ".join(tokens[:i]); break
    else:
        return None
    if not street or not plz:
        return None
    return street, hnr, plz


if __name__ == "__main__":
    assert parse_address("Kastanienallee 12, 10435") == ("Kastanienallee", "12", "10435")
    assert parse_address("Kastanienallee 12 10435") == ("Kastanienallee", "12", "10435")
    assert parse_address("Kastanienallee 12, 10435 Berlin") == ("Kastanienallee", "12", "10435")
    # Borough injected between street and PLZ — expat-common pattern.
    assert parse_address("Sybelstrasse 59, Charlottenburg, 10629 Berlin") == ("Sybelstrasse", "59", "10629")
    assert parse_address("Sybelstrasse 59, Charlottenburg, 10629") == ("Sybelstrasse", "59", "10629")
    # Trailing 'Berlin' with no commas.
    assert parse_address("Kastanienallee 12 10435 Berlin") == ("Kastanienallee", "12", "10435")
    assert parse_address("   ") is None
    assert parse_address("") is None
    assert parse_address("Nostreet") is None
    print("addr.py selfcheck OK")
