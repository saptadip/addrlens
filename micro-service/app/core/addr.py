"""Free-text address parser. Verbatim from phase3/server.py:parse_address."""


def parse_address(q: str):
    """Very loose 'Street 12, 10435' parser. Returns (street, hnr, plz) or None."""
    q = (q or "").strip()
    if not q:
        return None
    if "," in q:
        left, right = q.rsplit(",", 1)
        plz = "".join(ch for ch in right if ch.isdigit())[:5]
    else:
        parts = q.split()
        if len(parts) < 2: return None
        plz = parts[-1] if parts[-1].isdigit() and len(parts[-1]) == 5 else ""
        left = " ".join(parts[:-1]) if plz else q
    tokens = left.strip().split()
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
    assert parse_address("   ") is None
    assert parse_address("") is None
    assert parse_address("Nostreet") is None
    print("addr.py selfcheck OK")
