# Vertrag: Ort im Kalender antippbar (16.11.2026)

**Für den Agenten, der die Sarvis-Android-App baut** (Package `de.techartist.sarvis`).

Saschas Wunsch: Ein Termin mit Ort soll sich mit einem Tipp in Google Maps öffnen.

## Server (✅ fertig)

- Jeder Termin aus `GET /termine` und aus `POST /termin/anlegen|aendern` hat ein neues
  Feld **`karte`**: fertige Google-Maps-URL, `""` wenn kein Ort.
- Maps-Kurzlinks im `ort` werden beim Anlegen in die echte Adresse aufgelöst.
- Nichts Bestehendes wurde geändert oder entfernt. Maßgeblich: `einsatz/DRAHT.md`, Abschnitt „Kalender“.

## App (⬜ offen)

1. Termin-Modell: Feld `karte: String = ""` (fehlt es → leer, ältere Server).
2. In der Terminansicht (Liste/Woche/Detail): ist `karte` nicht leer, den Ort als
   antippbaren Link darstellen (Karten-Symbol + Ortstext).
3. Tippen → `startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(termin.karte)))`.
   Android öffnet damit die Maps-App (oder den Browser, falls keine da ist).
   `ActivityNotFoundException` abfangen.
4. Auch in der Chat-Blase: `https://…`-Links müssen antippbar sein (falls noch nicht).
