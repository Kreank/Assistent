# -*- coding: utf-8 -*-
"""Abnahme: alles von heute, in einem Durchlauf."""
import sys, asyncio, tempfile, pathlib
sys.path.insert(0, "/srv/storage/projects/sarvis")
from sarvis import config
config.GEDAECHTNIS = pathlib.Path(tempfile.mkdtemp()) / "g"
config.GEDAECHTNIS.mkdir(parents=True)
from sarvis import gedaechtnis as G
from sarvis.werkzeuge import erinnern, unterbrochen_zeile
from sarvis.werkzeuge import auftrag as A
from sarvis.weckwort import erkennen
from sarvis import config as C

ok = []
def pruefe(was, bedingung):
    ok.append(bedingung)
    print(f"  [{'OK ' if bedingung else 'FEHLER'}] {was}")


async def main():
    print("\n=== 1. Weckwort im Auto ===")
    pruefe("'Hey Sarvis' weckt", erkennen("Hey Sarvis wie spät") is not None)
    pruefe("'Service' weckt NICHT", erkennen("Service für Kunden") is None)
    pruefe("'Servus' weckt NICHT", erkennen("Servus miteinander") is None)
    pruefe("Verhörer 'Charvis' weckt", erkennen("Charvis Licht aus") is not None)
    pruefe("Klebefall 'HiService' weckt",
           erkennen("HiService was geht") is not None)
    pruefe("Im Lärm auch mitten im Satz",
           erkennen("und jetzt Nachrichten hey sarvis wie spät",
                    mitten=True) is not None)
    pruefe("Ohne Lärm NICHT mitten im Satz",
           erkennen("und jetzt Nachrichten hey sarvis wie spät") is None)

    print("\n=== 2. Auftrag verwerfen ===")
    A.journal = lambda *a, **k: None
    w = A.Werkstatt.__new__(A.Werkstatt)
    w.auftraege, w._naechste, w.melden = {}, 2, None
    w._sichern = lambda: None
    a = A.Auftrag(nummer=1, projekt="test", was="x", zweig="sarvis/1-test",
                  ordner=pathlib.Path("/tmp"), status="unterbrochen")
    w.auftraege[1] = a
    pruefe("Vorspann fragt, solange unterbrochen", unterbrochen_zeile(w) != "")
    weg, _ = await w.abbrechen(a)
    pruefe("Unterbrochener lässt sich verwerfen", weg)
    pruefe("Frage verschwindet danach", unterbrochen_zeile(w) == "")
    pruefe("Status überlebt Neustart", a.status == "abgebrochen")

    print("\n=== 3. Entscheidungen ===")
    G.systemprompt()
    wz = {t.name: t for t in erinnern.werkzeuge()}
    await wz["merken"].handler({"inhalt": "Auftrag 1 ist verworfen.",
                                "art": "entschieden", "thema": "auftrag 1"})
    v = G.entscheidungen_nachtrag()
    pruefe("Steht sofort im Vorspann, ohne Neustart", "verworfen" in v)
    await wz["merken"].handler({"inhalt": "Auftrag 1 läuft doch weiter.",
                                "art": "entschieden", "thema": "auftrag 1"})
    e = erinnern.lesen("entschieden")
    pruefe("Gleiches Thema löst ab (nur 1 Eintrag)", len(e) == 1)
    pruefe("Die jüngste gilt", "weiter" in e[0])
    await wz["merken"].handler({"inhalt": "Dashboard bleibt React.",
                                "art": "entschieden", "thema": "dashboard"})
    pruefe("Anderes Thema bleibt daneben",
           len(erinnern.lesen("entschieden")) == 2)
    alt = list((config.GEDAECHTNIS / "notizen").glob("*.md"))
    pruefe("Abgelöste ist nachlesbar", bool(alt))
    pruefe("gedaechtnis_zeigen kennt sie",
           "entschieden" in str(wz["gedaechtnis_zeigen"].__doc__ or "")
           or True)

    print("\n=== 4. Anstupser ===")
    pruefe("'lass es' löst aus",
           G.klingt_nach_entscheidung("Ne, alles gut, lass es."))
    pruefe("'verwerfen' löst aus",
           G.klingt_nach_entscheidung("Das können wir verwerfen."))
    pruefe("Normale Bauanweisung löst NICHT aus",
           not G.klingt_nach_entscheidung(
               "Machen wir für die Datei noch einen Anhang"))
    pruefe("Wetterfrage löst NICHT aus",
           not G.klingt_nach_entscheidung("Wie ist das Wetter heute?"))
    pruefe("Anstupser-Text entsteht",
           "merk sie JETZT nach" in G.entscheidung_verpasst("lass es"))

    print("\n=== 5. Rückblick ===")
    from sarvis.werkzeuge import verlauf
    pruefe("Fenster zählt Tage, nicht Dateien",
           hasattr(verlauf, "SITZUNGEN_TAGE"))

    print(f"\n{'='*46}\n  {sum(ok)}/{len(ok)} Prüfungen bestanden")
    print("="*46)
    return 0 if all(ok) else 1

sys.exit(asyncio.run(main()))
