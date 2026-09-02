"""Rechnen und Umrechnen -- mit Code, nicht mit Sprachgefühl.

WARUM DAS UEBERHAUPT EIN WERKZEUG IST

Ein Sprachmodell rechnet plausibel, nicht richtig. Bei "was sind 19
Prozent auf 1240,50" kommt fast immer etwas Passendes heraus, und dieses
"fast" ist das Problem: Bei einem Angebot merkt es niemand, und der
Fehler steht dann auf einem Papier, das ein Kunde bekommt.

Deshalb rechnet hier der Rechner. Das Modell entscheidet nur, WAS
gerechnet werden soll.

WARUM KEINE BIBLIOTHEK

pint kann Einheiten umrechnen und viel mehr, sympy sowieso. Beide
bringen aber einen englischen Parser mit ("2 kilowatt to btu/hour"), und
gesprochen kommt hier Deutsches an. Die Umrechnungen, die im
SHK-Alltag wirklich vorkommen, passen in eine Tabelle -- der Rest waere
Gewicht ohne Nutzen.

WARUM KEIN eval()

eval("2+3") ist bequem und eval("__import__('os').system('rm -rf /')")
ist derselbe Aufruf. Der Ausdruck kommt hier aus einer
Spracherkennung, also aus etwas, das jeder im Raum beeinflussen kann.
Gerechnet wird deshalb ueber den Syntaxbaum, und darin ist nur erlaubt,
was ausdruecklich dasteht: Zahlen, vier Grundrechenarten, Potenz,
Klammern, Vorzeichen. Kein Name, kein Aufruf, kein Attribut.
"""
import ast
import math
import operator
import re

from claude_agent_sdk import tool

# Was im Syntaxbaum vorkommen darf. Alles andere fliegt raus.
_RECHENARTEN = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}
_VORZEICHEN = {ast.UAdd: operator.pos, ast.USub: operator.neg}

# Ein Potenzieren wie 9**9**9 blockiert den Prozess auf Minuten. Der
# Deckel ist grosszuegig fuer alles, was ein Mensch fragt, und eng genug,
# dass nichts stehenbleibt.
_POTENZ_MAX = 1000


def _knoten(k):
    if isinstance(k, ast.Constant):
        if isinstance(k.value, bool) or not isinstance(k.value, (int, float)):
            raise ValueError("Nur Zahlen.")
        return k.value
    if isinstance(k, ast.BinOp):
        art = _RECHENARTEN.get(type(k.op))
        if art is None:
            raise ValueError("Diese Rechenart kenne ich nicht.")
        links, rechts = _knoten(k.left), _knoten(k.right)
        if art is operator.pow and (abs(rechts) > _POTENZ_MAX
                                    or abs(links) > _POTENZ_MAX):
            raise ValueError("Diese Potenz ist zu groß.")
        return art(links, rechts)
    if isinstance(k, ast.UnaryOp):
        art = _VORZEICHEN.get(type(k.op))
        if art is None:
            raise ValueError("Dieses Vorzeichen kenne ich nicht.")
        return art(_knoten(k.operand))
    raise ValueError("Darin steht etwas, das ich nicht ausrechnen darf.")


def ausrechnen(ausdruck: str) -> tuple:
    """Einen Rechenausdruck auswerten. Rueckgabe: (Zahl, Fehlertext)."""
    roh = " ".join(str(ausdruck or "").split())
    if not roh:
        return None, "Da war nichts zu rechnen."

    # Gesprochenes und deutsches Schreiben in etwas verwandeln, das
    # Python versteht. Reihenfolge zaehlt: Erst die Tausenderpunkte weg,
    # dann das Komma zum Punkt -- andersherum wird aus "1.240,50" ein
    # Unfall.
    t = roh.lower()
    for wort, zeichen in (("mal", "*"), ("geteilt durch", "/"),
                          ("durch", "/"), ("plus", "+"), ("minus", "-"),
                          ("hoch", "**"), ("x", "*"), ("·", "*"),
                          ("×", "*"), ("÷", "/"), ("^", "**"), (",-", "")):
        t = t.replace(wort, zeichen)
    t = re.sub(r"(\d)\.(?=\d{3}\b)", r"\1", t)     # 1.240 -> 1240
    t = t.replace(",", ".")
    t = t.replace("€", "").replace("eur", "").strip()

    if not re.fullmatch(r"[0-9+\-*/%(). ]*", t):
        return None, f"Mit {roh!r} kann ich nicht rechnen."
    try:
        baum = ast.parse(t, mode="eval")
        wert = _knoten(baum.body)
    except ZeroDivisionError:
        return None, "Durch null teilen geht nicht."
    except (SyntaxError, ValueError, TypeError, OverflowError) as e:
        return None, f"Mit {roh!r} kann ich nicht rechnen. ({e})"
    if isinstance(wert, float) and (math.isnan(wert) or math.isinf(wert)):
        return None, "Das ergibt keine Zahl."
    return wert, ""


# --- Einheiten -----------------------------------------------------------
#
# Bewusst knapp gehalten und auf das ausgerichtet, was in einem
# SHK-Alltag wirklich gesagt wird. Alles wird ueber eine Grundeinheit je
# Familie gerechnet; die Zahl ist, wie viele Grundeinheiten eine Einheit
# ist.
_EINHEITEN = {
    "laenge": ("m", {
        "mm": 0.001, "millimeter": 0.001, "cm": 0.01, "zentimeter": 0.01,
        "dm": 0.1, "m": 1.0, "meter": 1.0, "km": 1000.0, "kilometer": 1000.0,
        "zoll": 0.0254, "inch": 0.0254, "in": 0.0254, "fuss": 0.3048,
    }),
    "flaeche": ("m2", {
        "mm2": 1e-6, "cm2": 1e-4, "m2": 1.0, "quadratmeter": 1.0,
        "qm": 1.0, "ha": 10000.0, "hektar": 10000.0, "km2": 1e6,
    }),
    "volumen": ("l", {
        "ml": 0.001, "milliliter": 0.001, "l": 1.0, "liter": 1.0,
        "m3": 1000.0, "kubikmeter": 1000.0, "cbm": 1000.0,
        "cm3": 0.001, "dm3": 1.0,
    }),
    "masse": ("kg", {
        "mg": 1e-6, "g": 0.001, "gramm": 0.001, "kg": 1.0,
        "kilogramm": 1.0, "kilo": 1.0, "t": 1000.0, "tonne": 1000.0,
    }),
    "leistung": ("w", {
        "w": 1.0, "watt": 1.0, "kw": 1000.0, "kilowatt": 1000.0,
        "mw": 1e6, "megawatt": 1e6, "ps": 735.49875,
        # Im Heizungsbau steht BTU/h auf Geraeten aus dem
        # angelsaechsischen Raum und auf Klimageraeten.
        "btu": 0.29307107, "btuh": 0.29307107, "btu/h": 0.29307107,
    }),
    "energie": ("kwh", {
        "wh": 0.001, "kwh": 1.0, "kilowattstunde": 1.0, "mwh": 1000.0,
        "j": 2.7777778e-7, "kj": 2.7777778e-4, "mj": 0.2777778,
    }),
    "druck": ("bar", {
        "pa": 1e-5, "hpa": 1e-3, "kpa": 0.01, "mbar": 0.001,
        "bar": 1.0, "atm": 1.01325, "psi": 0.0689476,
        "mws": 0.0980665, "mwas": 0.0980665,     # Meter Wassersaeule
    }),
    "zeit": ("min", {
        "s": 1 / 60, "sekunde": 1 / 60, "sek": 1 / 60, "min": 1.0,
        "minute": 1.0, "h": 60.0, "stunde": 60.0, "std": 60.0,
        "tag": 1440.0, "d": 1440.0, "woche": 10080.0,
    }),
    "durchfluss": ("l/min", {
        "l/min": 1.0, "l/h": 1 / 60, "l/s": 60.0,
        "m3/h": 1000 / 60, "m3/min": 1000.0,
    }),
}

# Temperatur geht nicht ueber einen Faktor -- Null liegt woanders.
_TEMPERATUR = {"c", "celsius", "f", "fahrenheit", "k", "kelvin"}


def _norm(e: str) -> str:
    e = " ".join(str(e or "").lower().split())
    e = (e.replace("²", "2").replace("³", "3").replace("°", "")
         .replace("grad", "").strip())
    return e.replace(" ", "")


def _temperatur(wert: float, von: str, nach: str):
    grad = {"c": "c", "celsius": "c", "f": "f", "fahrenheit": "f",
            "k": "k", "kelvin": "k"}
    v, n = grad[von], grad[nach]
    celsius = {"c": lambda x: x,
               "f": lambda x: (x - 32) * 5 / 9,
               "k": lambda x: x - 273.15}[v](wert)
    return {"c": lambda x: x,
            "f": lambda x: x * 9 / 5 + 32,
            "k": lambda x: x + 273.15}[n](celsius)


def umrechnen(wert: float, von: str, nach: str) -> tuple:
    """Rueckgabe: (Zahl, Fehlertext)."""
    v, n = _norm(von), _norm(nach)
    if not v or not n:
        return None, "Ich brauche beide Einheiten."
    if v in _TEMPERATUR and n in _TEMPERATUR:
        return _temperatur(wert, v, n), ""
    for familie, (_, tabelle) in _EINHEITEN.items():
        if v in tabelle and n in tabelle:
            return wert * tabelle[v] / tabelle[n], ""
    # Beide bekannt, aber verschiedene Familien -- das ist ein anderer
    # Fehler als "kenne ich nicht", und der Unterschied hilft beim
    # Nachfragen.
    bekannt = {e for _, (_, t) in _EINHEITEN.items() for e in t}
    if v in bekannt and n in bekannt:
        return None, (f"{von} und {nach} lassen sich nicht ineinander "
                      "umrechnen — das sind verschiedene Größen.")
    unbekannt = von if v not in bekannt else nach
    return None, f"Die Einheit {unbekannt!r} kenne ich nicht."


def _sagbar(zahl: float) -> str:
    """Eine Zahl so schreiben, wie man sie vorliest.

    Kein Exponent und keine fuenfzehn Nachkommastellen: Beides ist
    gesprochen unbrauchbar. Und deutsches Komma, weil es vorgelesen wird.
    """
    if isinstance(zahl, int) or (isinstance(zahl, float)
                                 and zahl == int(zahl)
                                 and abs(zahl) < 1e15):
        return f"{int(zahl):,}".replace(",", ".")
    gerundet = round(zahl, 4)
    text = f"{gerundet:,.4f}".rstrip("0").rstrip(".")
    ganz, _, rest = text.partition(".")
    ganz = ganz.replace(",", ".")
    return f"{ganz},{rest}" if rest else ganz


def werkzeuge(protokoll=None, leuchten=None) -> list:
    def blinken():
        if leuchten:
            leuchten("Rechnen")

    @tool(
        "rechnen",
        "Rechnet einen Ausdruck aus — genau, nicht geschätzt. Benutze das "
        "IMMER, wenn eine Zahl herauskommen soll, die zählt: Preise, "
        "Mehrwertsteuer, Skonto, Mengen, Rohrlängen. Rechne nie selbst im "
        "Kopf. Prozent geht mit dem Prozentzeichen (1240.50*0.19), deutsche "
        "Kommas und Tausenderpunkte versteht es.",
        {
            "type": "object",
            "properties": {
                "ausdruck": {
                    "type": "string",
                    "description": "Der Rechenausdruck, z. B. "
                                   "'1240,50 * 1,19' oder '(3.5 + 2) / 4'.",
                },
                "wofuer": {
                    "type": "string",
                    "description": "Optional: wofür gerechnet wird, kurz — "
                                   "wird mit ausgegeben.",
                },
            },
            "required": ["ausdruck"],
        },
    )
    async def rechnen(args):
        wert, fehler = ausrechnen(args.get("ausdruck"))
        if wert is None:
            return {"content": [{"type": "text", "text": fehler}],
                    "is_error": True}
        blinken()
        wofuer = " ".join(str(args.get("wofuer") or "").split())
        text = _sagbar(wert) + (f" ({wofuer})" if wofuer else "")
        if protokoll is not None:
            protokoll.merken(f"rechnen: {args.get('ausdruck')} = {text}")
        return {"content": [{"type": "text", "text": text}]}

    @tool(
        "umrechnen",
        "Rechnet eine Einheit in eine andere um — Länge, Fläche, Volumen, "
        "Masse, Leistung (auch BTU), Energie, Druck (auch Meter "
        "Wassersäule), Temperatur, Zeit, Durchfluss. Für 'wie viel kW sind "
        "24000 BTU', 'wie viel Liter hat ein Kubikmeter', 'zwei Zoll in "
        "Millimeter'.",
        {
            "type": "object",
            "properties": {
                "wert": {"type": "number", "description": "Die Zahl."},
                "von": {"type": "string",
                        "description": "Ausgangseinheit, z. B. 'btu', 'kw', "
                                       "'zoll', 'm3', 'bar', 'C'."},
                "nach": {"type": "string",
                         "description": "Zieleinheit, z. B. 'kw', 'mm', "
                                        "'liter', 'psi', 'F'."},
            },
            "required": ["wert", "von", "nach"],
        },
    )
    async def umrechnen_wz(args):
        try:
            wert = float(args.get("wert"))
        except (TypeError, ValueError):
            return {"content": [{"type": "text", "text":
                    "Das ist keine Zahl."}], "is_error": True}
        ergebnis, fehler = umrechnen(wert, args.get("von"), args.get("nach"))
        if ergebnis is None:
            return {"content": [{"type": "text", "text": fehler}],
                    "is_error": True}
        blinken()
        return {"content": [{"type": "text", "text":
                f"{_sagbar(ergebnis)} {args.get('nach')}"}]}

    return [rechnen, umrechnen_wz]
