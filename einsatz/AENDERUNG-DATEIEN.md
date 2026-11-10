# Änderungsblatt: Dateien in beide Richtungen — 10.11.2026

**Für den Agenten, der die Android- (und Windows-)App baut.**

> **Es muss nichts angepasst werden, damit die Apps weiterlaufen.**
> Keine Nachrichtenart am Draht wurde geändert, kein Feld entfernt oder
> umbenannt. Dazugekommen sind ein HTTP-Weg (`GET /dateien`), eine
> höhere Größengrenze und mehr erlaubte Endungen beim Hochladen. Eine App,
> die unbekannte Arten still überspringt, läuft unverändert.

Anpassen lohnt sich, weil Sascha ausdrücklich will: **Dateien an Sarvis
schicken** und **Dateien von Sarvis bekommen** — auch solche, die auf dem
Server liegen. Sagt Sarvis „liegt bei dir“, und die App zeigt nichts an,
ist genau das kaputt.

Maßgeblich ist `einsatz/DRAHT.md` (Abschnitte „Dateien hochladen“,
„Dateien abholen“, „Teilen aus dem Handy-Menü“). Dieses Blatt ist nur die
Differenz. Prüfen: `python einsatz/draht_pruefen.py`.

---

## 1. Hochladen (App → Sarvis) — bestehender Weg, erweitert

`POST /datei`, multipart, Feld `datei`, Kopf `X-Sarvis-Schluessel` —
**unverändert**. Neu:

| | vorher | jetzt |
|---|---|---|
| Größe je Datei | 25 MB | **100 MB** |
| Endungen | Text, Code, Dokumente, Bilder | dazu `.zip .ics .vcf .gpx .kml .kmz .ppt .odp`, Audio `.mp3 .m4a .ogg .opus .wav .aac .flac`, Video `.mp4 .mov .webm .3gp .mkv`, Bild `.heif` |

Was die App bauen sollte:

1. **Knopf „Datei / Foto“** neben der Texteingabe → System-Dateiauswahl
   (`ACTION_OPEN_DOCUMENT`, mehrere erlaubt) und Kamera.
2. **Teilen-Ziel**: `ACTION_SEND` / `ACTION_SEND_MULTIPLE` mit `*/*`
   im Manifest. Geteilte Dateien direkt hochladen, geteilten Text (z. B.
   einen Link) ins Eingabefeld legen — nicht blind als Zuruf abschicken.
3. **Fortschritt** bei großen Dateien anzeigen, danach „ist bei Sarvis —
   frag ihn einfach dazu“. Sarvis liest die Datei **nicht** von selbst
   vor; er weiß beim nächsten Zuruf, dass sie da ist.
4. **Fehler lesbar machen**: 401 kein Zugang · 413 zu groß · 415 Dateiart
   nicht erlaubt (die Antwort nennt `endung`).

Fotos: JPG schicken, wenn möglich. HEIC nimmt der Server an, ansehen kann
Sarvis es aber nur, wenn es sich dekodieren lässt.

## 2. Herunterladen (Sarvis → App)

### Am Draht: nichts Neues

Ein `blatt` mit `sorte: "datei"` — wie seit 01.09. bei
`dokument_erstellen`. Neu ist nur, dass `datei` **jeder Dateiname** sein
kann (`foto.jpg`, `Projekt-20261110.zip`, `README.md`), nicht nur
PDF/Word/Excel/CSV/Text. Die App lädt `adresse` (relativ, `/blatt/…`,
ohne Schlüssel) und speichert unter `datei` — am besten über den
`DownloadManager` in „Downloads“, damit Sascha die Datei auch außerhalb
der App findet. Bei Bildendungen darf sie eine Vorschau zeigen.

### Neu: `GET /dateien`

Ein Blatt erreicht nur verbundene Apps. Was kam, während die App zu war,
steht hier. Die App holt die Liste **beim `willkommen`** und **nach jedem
Datei-Blatt**, und zeigt sie als eigenen Bereich „Dateien“:

```
GET /dateien
X-Sarvis-Schluessel: <Geräteschlüssel>
→ 200 {"von_sarvis": [ {kennung, titel, datei, adresse, bytes, seit, bis} … ],
       "von_dir":    [ {datei, bytes, seit} … ]}
→ 401 {"fehler": "kein Zugang"}
```

- `von_sarvis` neueste zuerst, 30 Tage gültig; Eintrag antippen = laden.
- `von_dir` nur Anzeige (keine Adresse).
- „Neu“-Markierung macht die App selbst (höchstes gesehenes `seit` merken).

## 3. Was sich im Verhalten von Sarvis ändert (zur Einordnung)

- „Schick mir …“ geht jetzt mit jeder Datei auf dem Server (Benutzerordner,
  Projekte, Sarvis' Daten); ein Ordner kommt als ZIP. Dateien, die
  Zugangsdaten enthalten könnten, gehen nur nach Rückfrage raus, `.env`
  und Schlüsseldateien gar nicht.
- Geschickte Fotos **sieht** Sarvis jetzt (vorher kamen sie als
  Zeichensalat an).
