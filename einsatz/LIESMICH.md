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
