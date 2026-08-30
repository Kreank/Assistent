#!/usr/bin/env python3
"""Prueft DRAHT.md gegen den Code -- und meldet jede Abweichung.

WARUM ES DAS GIBT

Es gab kurzzeitig zwei Papiere ueber dasselbe Protokoll, im Abstand von
Minuten geschrieben. Nach fuenf Minuten fehlten im zweiten schon drei
Felder: `spalten` bei der Kachel, `hier` als Lebenszeichen und `text`
beim Zustand. Gemerkt hat das nicht der Autor, sondern jemand, der beide
nebeneinandergelegt hat.

Genau so sieht der Fehler aus, wenn zwei Leute gegen zwei Staende bauen:
Er zeigt sich nicht als Absturz, sondern als eine Kachel, der eine
Spalte fehlt -- Wochen spaeter, in einer anderen Codebasis.

Dagegen hilft keine Sorgfalt, sondern eine Pruefung. Der Code ist die
Wahrheit; DRAHT.md ist eine Erklaerung davon, und Erklaerungen veralten.
Diese Datei sagt, wann.

    python einsatz/draht_pruefen.py

Rueckgabe 0, wenn alles uebereinstimmt, sonst 1. Taugt fuer einen
pre-commit-Haken.

WAS SIE PRUEFT UND WAS NICHT

Sie vergleicht Namen: Welche Arten und welche Felder sendet der Code,
und welche stehen in der Tabelle? Ob die BESCHREIBUNG daneben stimmt,
kann sie nicht wissen -- dafuer gibt es keinen Ersatz fuers Lesen. Aber
der haeufigste Fehler ist nicht die falsche Beschreibung, sondern das
vergessene Feld.
"""
import ast
import re
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
DOKU = WURZEL / "einsatz" / "DRAHT.md"

# Felder, die in der Tabelle bewusst fehlen duerfen. Jedes braucht eine
# Begruendung -- eine Ausnahmeliste ohne Gruende ist eine Abkuerzung, die
# man spaeter fuer eine Regel haelt.
GEDULDET = {
    # "art" steht in JEDER Nachricht und ist der Schluessel der Tabelle
    # selbst. Es in jede Zeile zu schreiben waere Rauschen.
    ("*", "art"),
    # anzeige.zustand() schickt ein "text", das hud.py nie liest -- ein
    # totes Feld am Draht. In der Doku steht es als solches vermerkt;
    # hier ist es geduldet, damit die Pruefung nicht auf einer Leiche
    # besteht.
    ("zustand", "text"),
}


def aus_anzeige() -> dict[str, set[str]]:
    """Was anzeige.Anzeige sendet -- aus den _senden()-Aufrufen gelesen."""
    baum = ast.parse((WURZEL / "sarvis" / "anzeige.py").read_text("utf-8"))
    raus: dict[str, set[str]] = {}
    for k in ast.walk(baum):
        if not (isinstance(k, ast.ClassDef) and k.name == "Anzeige"):
            continue
        for f in k.body:
            if not isinstance(f, ast.FunctionDef) or f.name.startswith("_"):
                continue
            for n in ast.walk(f):
                if (isinstance(n, ast.Call)
                        and getattr(n.func, "attr", "") == "_senden"):
                    felder = {kw.arg for kw in n.keywords if kw.arg}
                    art = f.name
                    # Die Art steht als Zeichenkette im Aufruf, nicht im
                    # Methodennamen -- bei kachel_weg heissen sie zufaellig
                    # gleich, bei anderen nicht.
                    for kw in n.keywords:
                        if kw.arg == "art" and isinstance(kw.value, ast.Constant):
                            art = kw.value.value
                    raus.setdefault(art, set()).update(felder)
    return raus


# Module, die am Traeger vorbei senden koennen. Jedes neue gehoert
# hierher -- sonst meldet die Pruefung eine Art als "steht in der Doku,
# der Code sendet sie nicht", und man sucht den Fehler in der Doku.
SENDER = ("netz/klang_netz.py", "netz/horch_netz.py",
          "werkzeuge/programme.py")


def aus_ton() -> dict[str, set[str]]:
    """Was die Netz-Module direkt ueber den Traeger schicken."""
    raus: dict[str, set[str]] = {}
    for datei in SENDER:
        pfad = WURZEL / "sarvis" / datei
        if not pfad.is_file():
            continue
        quelle = pfad.read_text("utf-8")
        # Zwei Schreibweisen: der Traeger nimmt ein Verzeichnis,
        # Anzeige._senden nimmt Schluesselwoerter. Beide kommen vor.
        for treffer in re.finditer(r'\.traeger\.senden\(\{(.*?)\}\)', quelle,
                                   re.S):
            block = treffer.group(1)
            art = re.search(r'"art":\s*"(\w+)"', block)
            if not art:
                continue
            raus[art.group(1)] = set(re.findall(r'"(\w+)":', block))
        for treffer in re.finditer(
                r'_senden\(\s*art\s*=\s*"(\w+)"(.*?)\)\n', quelle, re.S):
            art, rest = treffer.group(1), treffer.group(2)
            raus[art] = set(re.findall(r'(\w+)\s*=', rest)) | {"art"}
    return raus


def aus_server() -> set[str]:
    """Was der Endpunkt von einer Oberflaeche entgegennimmt."""
    quelle = (WURZEL / "sarvis" / "netz" / "server.py").read_text("utf-8")
    return set(re.findall(r'art == "(\w+)"', quelle))


def aus_doku() -> tuple[dict[str, set[str]], set[str]]:
    """Die beiden Tabellen aus DRAHT.md."""
    text = DOKU.read_text("utf-8")
    herein: dict[str, set[str]] = {}
    hinaus: set[str] = set()

    def abschnitt(marke: str) -> str:
        """Der Text zwischen <!-- draht:X --> und <!-- /draht:X -->.

        Ausdrueckliche Marken statt "alle Tabellen im Dokument": Sonst
        liest die Pruefung auch die Nebentabellen mit (die Sorten der
        Kachel etwa) und meldet "Art 'sorte' steht in der Doku". Eine
        Pruefung, die falschen Alarm gibt, schaltet man ab -- und dann
        prueft gar nichts mehr.
        """
        m = re.search(rf"<!-- draht:{marke}.*?-->(.*?)<!-- /draht:{marke} -->",
                      text, re.S)
        return m.group(1) if m else ""

    for name, ziel in (("herein", herein), ("hinaus", hinaus)):
        for zeile in abschnitt(name).splitlines():
            if not zeile.startswith("|") or zeile.startswith("|---"):
                continue
            spalten = [s.strip() for s in zeile.strip("|").split("|")]
            if len(spalten) < 2:
                continue
            arten = re.findall(r"`(\w+)`", spalten[0])
            felder = set(re.findall(r"`(\w+)`", spalten[1]))
            # Die Kopfzeile heisst selbst "| `art` | Felder | ..." -- sie
            # sieht wie eine Datenzeile aus. Es gibt keine Art namens
            # "art", also ist das Aussortieren eindeutig.
            arten = [a for a in arten if a != "art"]
            for a in arten:
                if name == "hinaus":
                    ziel.add(a)
                else:
                    ziel.setdefault(a, set()).update(felder)
    return herein, hinaus


def main() -> int:
    code = aus_anzeige() | aus_ton()
    doku_ein, doku_aus = aus_doku()
    server = aus_server()
    fehler: list[str] = []

    for art, felder in sorted(code.items()):
        if art not in doku_ein:
            fehler.append(f"Art '{art}' sendet der Code, steht aber nicht "
                          f"in DRAHT.md")
            continue
        fehlt = {f for f in felder - doku_ein[art]
                 if ("*", f) not in GEDULDET and (art, f) not in GEDULDET}
        if fehlt:
            fehler.append(f"Art '{art}': Code sendet {sorted(fehlt)}, "
                          f"DRAHT.md nennt sie nicht")
        zuviel = doku_ein[art] - felder
        if zuviel:
            fehler.append(f"Art '{art}': DRAHT.md nennt {sorted(zuviel)}, "
                          f"der Code sendet das nicht")

    for art in sorted(doku_ein):
        if art not in code:
            fehler.append(f"Art '{art}' steht in DRAHT.md, der Code sendet "
                          f"sie nicht")

    if server - doku_aus:
        fehler.append(f"Der Endpunkt nimmt {sorted(server - doku_aus)} "
                      f"entgegen, DRAHT.md nennt das nicht")
    if doku_aus - server:
        fehler.append(f"DRAHT.md nennt {sorted(doku_aus - server)}, "
                      f"der Endpunkt kennt das nicht")

    if fehler:
        print("DRAHT.md weicht vom Code ab:\n")
        for f in fehler:
            print(f"  - {f}")
        print(f"\n{len(fehler)} Abweichung(en). Der Code ist die Wahrheit.")
        return 1

    print(f"DRAHT.md stimmt mit dem Code überein "
          f"({len(code)} Arten hinein, {len(server)} hinaus).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
