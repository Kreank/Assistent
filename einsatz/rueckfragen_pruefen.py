"""Prueft, dass jede Rueckfrage fuer Menschen lesbar ist.

Anlass (Sascha, 19.11.2026): "Mail 6 nach papierkorb verschieben" --
"Woher soll ich wissen, was Mail 6 ist? ... eine interne Modellangabe
bringt mir nichts." Das gilt fuer JEDE Genehmigung, nicht nur fuer Mails.

Geht alle Werkzeuge durch, die laut config.WERKZEUG_STUFEN nachfragen
(Stufe "fragen" oder "browser"), fuettert sie mit typischen Eingaben und
schlaegt fehl, wenn in der Frage etwas Internes steht:

  - der Werkzeugname selbst oder ueberhaupt ein Unterstrich-Bezeichner
  - "None" oder leere Platzhalter
  - eine Kennung (konto_id 2, nachricht_id 4711)
  - der Auffangfall ("das tun") -- jedes fragende Werkzeug braucht eine
    eigene Formulierung in rueckfrage.formulieren()

Ausfuehren im Container:
    docker compose exec -T sarvis python einsatz/rueckfragen_pruefen.py
Neues fragendes Werkzeug ohne Formulierung -> rot. So soll es sein.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sarvis import config, rueckfrage  # noqa: E402
from sarvis.werkzeuge import finanzen, microsoft, zeit  # noqa: E402

# Listen so fuellen, wie sie nach einem Abruf aussehen.
microsoft._mails[:] = [{
    "subject": "Ihre Rechnung November",
    "from": {"emailAddress": {"name": "Telekom", "address": "rechnung@telekom.de"}},
    "receivedDateTime": "2026-11-12T08:00:00Z",
    "_anhaenge": [{"name": "Rechnung.pdf"}],
}]
microsoft._termine[:] = [{"subject": "Zahnarzt",
                          "start": {"dateTime": "2026-11-24T10:30:00"}}]
finanzen._konto_namen.update({1: "Girokonto", 2: "Sparkonto"})


class _Wecker:
    laufende = {1: {"was": "Jeden Morgen die Mails sortieren"}}


zeit._wecker = _Wecker()

# Typische Eingaben, gezielt mit Nummern und Kennungen -- genau die
# duerfen nicht in der Frage landen.
EINGABE = {
    "nummer": 1, "anhang": 1, "nachricht_id": 4711, "konto_id": 1,
    "von_konto_id": 1, "nach_konto_id": 2, "antwort_auf": 1,
    "betrag": "-12.50", "verwendungszweck": "Bäcker", "datum": "2026-11-19",
    "titel": "Zahnarzt", "neuer_beginn": "2026-11-26 09:00",
    "beginn": "2026-11-26 09:00",
    "name": "Spotify", "wohin": "papierkorb", "suche": "from:telekom older_than:1y",
    "an": "anna@example.org", "betreff": "Hallo", "text": "Bis morgen",
    "chat": "Anna", "inhalt": "Herr Kettner ist der Nachbar",
    "stichwort": "Kettner", "pfad": "/srv/data/sascha/brief.pdf",
    "projekt": "orbitum", "label": "Rechnungen", "rhythmus": "monatlich",
    "start": "2026-12-01", "bereich": "A1:B2", "werte": ["1", "2"],
    "werkzeuge": ["termin_anlegen", "mail_verschieben"],
    "element": {"art": "knopf", "text": "Weiter", "im_formular": True},
}

VERBOTEN = [
    (re.compile(r"\b[a-z]+_[a-z_]+\b"), "interner Bezeichner"),
    (re.compile(r"\bNone\b"), "None"),
    (re.compile(r"\b(?:id|nummer)\s*\d", re.I), "Kennung"),
    (re.compile(r"\b(?:Mail|Termin|Anhang|Aufgabe|Konto|Nachricht)\s+\d+\b"),
     "nackte Listennummer"),
    (re.compile(r"\b(?:from|to|subject|has|is|in|label|category|after|before):"),
     "Gmail-Suchsyntax"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "Datum in Technikschreibweise"),
    (re.compile(r"\b\d+\.\d{2} Euro"), "Betrag mit Punkt"),
    (re.compile(r"\bdas tun\b"), "Auffangfall -- eigene Formulierung fehlt"),
    (re.compile(r"„“|\s[,?]"), "leerer Platzhalter"),
]

fehler = 0
for werkzeug, stufe in config.WERKZEUG_STUFEN.items():
    if stufe not in ("fragen", "browser"):
        continue
    frage = rueckfrage.formulieren(werkzeug, dict(EINGABE))
    gruende = [g for muster, g in VERBOTEN
               if muster.search(frage.replace(werkzeug, f"<{werkzeug}>"))
               or werkzeug in frage]
    if gruende:
        fehler += 1
        print(f"ROT  {werkzeug}: {', '.join(sorted(set(gruende)))}\n     {frage}")
    else:
        print(f"ok   {werkzeug}: {frage}")

print(f"\n{fehler} unlesbare Rückfrage(n).")
sys.exit(1 if fehler else 0)
