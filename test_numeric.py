from processing.normalizer import _clean_numeric, _BABEL_AVAILABLE
import math

print("Babel disponible:", _BABEL_AVAILABLE)

tests = [
    ("1 234,56",    1234.56,  "espace + virgule fr_MA"),
    ("1.234,56",    1234.56,  "point milliers + virgule decimale EU"),
    ("1,234.56",    1234.56,  "virgule milliers + point decimale EN"),
    ("(1 500,00)",  -1500.0,  "negatif comptable parentheses"),
    ("12,5",        12.5,     "simple virgule decimale"),
    ("-850.75",     -850.75,  "negatif point decimal"),
    ("1 000 000",   1000000,  "million espace"),
    ("",            float("nan"), "cellule vide"),
    ("N/A",         float("nan"), "N/A"),
]

ok = fail = 0
for raw, expected, label in tests:
    got = _clean_numeric(raw)
    if math.isnan(expected):
        passed = math.isnan(got)
    else:
        passed = not math.isnan(got) and abs(got - expected) < 0.01
    sym = "OK" if passed else "FAIL"
    if passed: ok += 1
    else: fail += 1
    print(f"  [{sym}] {label}: '{raw}' -> {got}  (attendu: {expected})")

print(f"\nResultats: {ok}/{ok+fail} passes")
