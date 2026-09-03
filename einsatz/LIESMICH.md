# Einsatz

Was auf dem Server eingerichtet werden muss und `sudo` braucht --
also von Sascha kommt, nicht von Claude.

## Caddy

`Caddyfile.fertig` ist die **komplette** `/etc/caddy/Caddyfile` mit dem
Sarvis-Block hinten angehängt. Geprüft mit `caddy validate`:
*Valid configuration*. Nichts Bestehendes wurde geändert, es kamen 40
Zeilen dazu.

`caddy-block.conf` ist nur der neue Teil, falls die Datei sich
inzwischen anderswo geändert hat und von Hand eingefügt werden soll.

Einspielen:

    sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak-vor-sarvis
    sudo cp /srv/storage/projects/sarvis/einsatz/Caddyfile.fertig /etc/caddy/Caddyfile
    sudo systemctl reload caddy

Bis der Sarvis-Dienst auf 8900 läuft, antwortet die Domain mit 502.
Das ist richtig so -- Caddy holt sich in der Zeit schon das Zertifikat.

Zurück:

    sudo cp /etc/caddy/Caddyfile.bak-vor-sarvis /etc/caddy/Caddyfile
    sudo systemctl reload caddy

## Warum die Zeitlimits so hoch sind

Der WebSocket steht offen, solange eine Oberfläche verbunden ist -- also
stundenlang. Mit den üblichen 60 Sekunden risse er ständig ab, und die
Oberfläche hinge in einer Endlosschleife aus Verbinden und Verlieren.

## Was NICHT nötig ist

Ein eigener Block für WebSockets. Caddy erkennt das Upgrade selbst und
reicht es durch.

## Google neu anmelden -- auf dem Server, nicht auf Windows

`google_anmelden.bat` im Projektwurzelordner ist aus der Zeit, als Sarvis
auf Saschas Rechner lief. Sie hilft hier nicht: Sie schreibt den Zugang
in den Windows-Projektordner, gebraucht wird er aber in
`/srv/data/sarvis/google_token.json`. Der Server hat dafür keinen
Browser, also kann der übliche Weg -- Fenster auf, bestätigen, fertig --
nicht laufen.

`google_anmelden_server.py` teilt ihn deshalb in zwei Schritte:

    docker exec sarvis python \
      /srv/storage/projects/sarvis/einsatz/google_anmelden_server.py link

Der ausgegebene Link geht an Sascha, er bestätigt im Browser und landet
auf einer **Fehlerseite** (`localhost:8123` gibt es auf seinem Rechner
nicht). Das ist der Normalfall, nicht der Fehler -- gebraucht wird nur
die Adresszeile dieser Seite:

    docker exec -e OAUTHLIB_INSECURE_TRANSPORT=1 -e OAUTHLIB_RELAX_TOKEN_SCOPE=1 \
      sarvis python \
      /srv/storage/projects/sarvis/einsatz/google_anmelden_server.py \
      code "<die zurückkopierte Adresse>"

Die beiden Umgebungsvariablen sind nötig, nicht optional: `oauthlib`
verweigert `http` grundsätzlich (bei `localhost` unbegründet), und
Google gibt die Bereiche in anderer Reihenfolge zurück, als sie
angefragt wurden. Ohne sie bricht der Eintausch ab -- und ein
Google-Code gilt nur einmal, der Link muss dann neu geholt werden.

Danach greift es sofort: Sarvis hängt seinen Merker am Änderungsstempel
der Tokendatei, ein Neustart ist nicht nötig.

## Warum das alle sieben Tage passiert

Das Google-Projekt steht im **Testing**-Modus, und dort wirft Google den
Auffrisch-Schlüssel nach sieben Tagen weg -- er meldet dann
`invalid_grant: Token has been expired or revoked`, und kein Auffrischen
hilft mehr, nur die Neuanmeldung oben. Dauerhaft beendet ist das erst,
wenn der Zustimmungsbildschirm in der Google Cloud Console auf
**In Produktion** steht.
