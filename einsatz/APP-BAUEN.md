# Eine native Sarvis-App für Windows

**Auftrag für eine KI oder einen Entwickler auf dem Windows-Rechner.**

Das Protokoll steht **nicht hier**, sondern in [`DRAHT.md`](DRAHT.md) —
und zwar nur dort. Hier steht, was an Windows besonders ist.

Der Grund für diese Trennung ist Erfahrung, keine Ordnungsliebe: Es gab
kurzzeitig zwei Papiere über denselben Draht. Nach fünf Minuten fehlten
im zweiten drei Felder. Solche Fehler zeigen sich nicht als Absturz,
sondern als eine Kachel, der eine Spalte fehlt — Wochen später, in einer
anderen Codebasis. `DRAHT.md` lässt sich gegen den Code prüfen
(`python einsatz/draht_pruefen.py`), diese Datei nicht.

---

## Warum überhaupt eine native App

Es gibt eine Weboberfläche, die funktioniert (`web/` im Repo). Sie kann
Mikrofon, Ton, Anzeige, Startbildschirm — alles, was man erwartet.

Eine Windows-App lohnt sich wegen **eines** Dings:

**Der systemweite Tastaturhaken.** Sarvis' beste Bedienung ist die rechte
Strg-Taste: halten, reden, loslassen — mitten aus der Arbeit heraus, ohne
das Fenster zu wechseln. Ein Browser bekommt Tastendrücke nur, wenn er den
Fokus hat.

Dazu kommt, weniger wichtig, das **Overlay über allen Fenstern**:
klickdurchlässig, damit man hindurcharbeiten kann. So sah Sarvis vorher aus.

Wenn beides nicht gebraucht wird, ist die Weboberfläche weniger Arbeit.

### Warum eine Android-App noch warten sollte

Ihr einziger Vorteil gegenüber der Weboberfläche wäre „Hey Sarvis" bei
gesperrtem Bildschirm — ein Foreground Service darf das Mikrofon
offenhalten, ein Browser im Hintergrund nicht.

Genau das braucht aber den **Dauerstrom**, und der ist serverseitig noch
nicht gebaut (siehe „Was noch fehlt" in `DRAHT.md`). Ohne ihn kann eine
Android-App nur fertige Aufnahmen schicken — und das kann die
Weboberfläche auch. Erst der Dauerstrom auf dem Server, dann die App;
sonst baut man eine App, deren Daseinsgrund noch nicht ansprechbar ist,
und stellt am Ende fest, dass die Blockung (480 Werte, Silero) doch anders
sein muss als angenommen.

**Windows ist davon nicht betroffen** — der Tastaturhaken braucht keinen
Dauerstrom.

---

## Was die App kann, was der Browser nicht darf

Bei der Anmeldung meldet sie ihre Fähigkeiten:

```json
{ "schluessel": "…", "kann_browser": true, "kann": ["kann_rechner"] }
```

`kann_rechner` heißt: „Ich kann Programme starten und Medientasten
drücken." Damit bekommt die App eine Art, die eine Weboberfläche nie
sieht — `befehl` (Einzelheiten in DRAHT.md).

    { "art": "befehl", "befehl": "programm", "name": "Spotify" }
    { "art": "befehl", "befehl": "medien", "was": "pause" }

Unter Windows sind das `Start-Process` bzw. die virtuellen Medientasten
über `keybd_event` (`VK_MEDIA_PLAY_PAUSE`, `VK_VOLUME_UP` …). Der Reiz
daran ist, dass es **kein Konto braucht**: Das Signal geht ans
Betriebssystem, und wer gerade Ton macht, reagiert — Spotify, YouTube im
Browser, VLC.

**Melde `kann_rechner` nur, wenn du die Befehle wirklich ausführst.**
Eine App, die es meldet und dann nichts tut, ist schlimmer als eine, die
es weglässt: Sarvis sagt dann „erledigt", und nichts ist passiert. Ohne
die Meldung sagt er ehrlich, dass er es von dort nicht kann.

Unter Android ist `programm` mit einem Intent lösbar, `medien` über den
`MediaSession`-Dienst. Was dort nicht geht, lässt man weg — siehe oben.

## Der Tastaturhaken

`SetWindowsHookEx` mit `WH_KEYBOARD_LL`. Drei Dinge, die zählen:

**Die Taste nicht abfangen.** `CallNextHookEx` weiterrufen, damit das
Vordergrundprogramm den Tastendruck trotzdem bekommt. Bei der rechten
Strg-Taste ist das folgenlos; bei F10 oder Alt wäre es das nicht — und
genau deshalb ist es die rechte Strg. Sie tut allein gar nichts, während
F10 in vielen Programmen die Menüleiste aktiviert und Alt erst recht. Wer
Alt hält, während er redet, macht aus jedem Streifen von Tab oder F4 eine
Tastenkombination.

**Die Grenze kennen und benennen.** Hat ein Programm mit
Administratorrechten den Fokus, blockiert Windows den Haken. Das war beim
alten Sarvis genauso; es ist keine Fehlfunktion und sollte nicht als eine
gemeldet werden.

**Der Haken läuft in einem eigenen Faden** mit eigener Nachrichtenschleife.
Er darf dort nichts Langsames tun — Aufnahme starten heißt: ein Ereignis
setzen, nicht auf ein Audiogerät warten.

Die Taste steht im Repo als `config.TASTE = "ctrl_r"`. Wenn die App sie
konfigurierbar macht, sollte sie beim Start ansagen, welche es ist.

---

## Audio unter Windows

**Aufnahme mit WASAPI in 16 000 Hz**, mono, int16 — genau das erwartet
Whisper (Begründung in `DRAHT.md`). Nicht in 48 kHz aufnehmen und
umtasten; lineare Interpolation ohne Tiefpass macht hörbaren Schaden.

**Ringpuffer vor dem Tastendruck.** Dauerhaft in einen Ringpuffer von
etwa einer Sekunde aufnehmen und beim Loslassen die letzten ~300 ms
**vor** dem Tastendruck mitschicken. Menschen drücken die Taste oft eine
Silbe zu spät. Das ist der billigste spürbare Gewinn der ganzen App.

**Wiedergabe** in der Rate, die der Server im `ton` meldet (üblich
22 050). Blöcke nahtlos aneinanderhängen — die Runden-Logik in `DRAHT.md`
gilt unverändert und ist der fehleranfälligste Teil.

**Echo-Unterdrückung an, Verstärkungsautomatik aus.** Warum, steht in
`DRAHT.md`.

---

## Das Overlay

- Randlos, immer obenauf, klickdurchlässig:
  `WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW`, dazu
  `WS_EX_NOACTIVATE`, damit es keinen Fokus stiehlt.
- **Nicht anklickbar** ist eine Zusage, keine Bequemlichkeit — siehe den
  Abschnitt über Kacheln in `DRAHT.md`.
- Zum Verschieben muss es die Maus kurzzeitig annehmen können. Im
  Original geschieht das über eine Tastenkombination, die
  `WS_EX_TRANSPARENT` vorübergehend abschaltet. Windows übernimmt
  geänderte Fensterflags erst beim nächsten `ShowWindow`.

**Der Look ist übernommen, nicht neu erfunden.** Das Original steht in
`sarvis/hud.py` (1094 Zeilen) und `sarvis/kachel.py` (2766) — präziser
als jede Zusammenfassung. `web/sarvis.js` ist eine vollständige
Übersetzung davon und die praktischere Vorlage: dieselben Zahlen, aber in
250 Zeilen statt 3900.

Die Eckwerte, damit man weiß, worauf man sich einlässt:

```
Zeichenraster    660 × 548, Mitte bei (330, 222)
Ring             Radius 58
Werkzeugkranz    Radius 176, 17 Werkzeuge, oben beginnend im Uhrzeigersinn
Striche          72 Stück, an der Senkrechten gespiegelt
Takt             60 Bilder je Sekunde
```

---

## Technikwahl

Frei. Zwei, die beides können (Klickdurchlässigkeit und globaler Haken):

- **C# / WPF** — `HwndSourceHook` für den Haken, `AllowsTransparency`
  fürs Overlay, `NAudio` oder `WASAPI` direkt für den Ton.
- **Rust / egui + windows-rs** — kleiner, kein .NET-Laufzeitpaket,
  dafür mehr Handarbeit beim Zeichnen.

Autostart über den Startordner oder einen Registry-Run-Eintrag. Den
Geräteschlüssel in den **Windows Credential Manager**, nicht im Klartext
neben die ausführbare Datei.

---

## Reihenfolge

Nach Nutzen sortiert, nicht nach Aufwand:

1. **Verbinden, anmelden, wiederverbinden.** Ohne das ist nichts anderes
   prüfbar.
2. **Der Ring mit `zustand` und `pegel`.** Man sieht sofort, ob der Draht
   trägt.
3. **Tastaturhaken und Aufnahme.** Der Grund für die ganze App.
4. **Ton mit Runden-Logik.** Der fehleranfälligste Teil.
5. **Werkzeugkranz, Untertitel, Kacheln.**
6. **Overlay-Fenster**, klickdurchlässig, immer obenauf.

Nach Schritt 3 ist die App bereits nützlicher als die Weboberfläche.
Alles danach ist Politur.

---

## Testen ohne den Server

Im Repo liegt `einsatz/vorschau.py` — ein Endpunkt ohne Sarvis dahinter,
der auf `zuruf` und `sprache` mit sichtbaren Zuständen antwortet und
meldet, wie lang die angekommene Aufnahme war. So sieht man sofort, ob
das Audioformat stimmt. Er lässt sich auf einem beliebigen Rechner
starten und ist rund 60 Zeilen lang — als Vorlage für einen eigenen
Wegwerf-Server gut lesbar.

Was er noch nicht tut und was ein eigener Testserver ergänzen sollte:
eine Tondatei **satzweise** schicken und dabei die `runde` mitzählen.
Genau daran scheitert eine Umsetzung am ehesten.
