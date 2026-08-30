/* Sarvis im Browser.
 *
 * Die Zeichenroutinen sind keine Neuerfindung, sondern eine Uebersetzung
 * von hud.py: dasselbe Raster 660x548, dieselbe Mitte bei 330/222,
 * derselbe Ring mit 58, derselbe Kranz mit 176, dieselben fuenf Farben.
 * Was dort QPainter tat, tut hier ein Canvas. Der Grund ist nicht
 * Nostalgie: Sarvis soll auf dem Handy nicht wie ein anderes Programm
 * aussehen als am Rechner.
 */
'use strict';

// --- Aus hud.py uebernommen ------------------------------------------
const BREITE = 660, HOEHE = 548;
const MITTE = { x: 330, y: 222 };
const RADIUS = 58;      // der Ring
const KRANZ = 176;      // Abstand der Werkzeuge von der Mitte
const BALKEN = 72;      // Striche rund um den Ring
const VERLAUF_LAENGE = BALKEN / 2;
const ICON = 17;

const FARBEN = {
  ruhig:   [126, 158, 200],
  hoert:   [0, 229, 255],
  denkt:   [180, 124, 255],
  spricht: [255, 179, 71],
  fragt:   [255, 120, 140],
};
const BESCHRIFTUNG = {
  ruhig: 'bereit', hoert: 'hört zu', denkt: 'denkt nach',
  spricht: 'spricht', fragt: 'wartet auf dich',
};
const WERKZEUGE = ['Timer', 'Gedächtnis', 'Telegram', 'Websuche', 'Programme',
  'Musik', 'Dateien', 'Projekte', 'Aufträge', 'Kalender', 'E-Mail', 'Aufgaben',
  'Kontakte', 'Drive', 'Tabellen', 'Entwicklung', 'Finanzen'];

const KACHEL_ANTWORT = [255, 179, 71];
const KACHEL_ZUSTAND = [126, 224, 168];

// --- Zustand ----------------------------------------------------------
const S = {
  zustand: 'ruhig', pegel: 0, geglaettet: 0, verlauf: new Array(VERLAUF_LAENGE).fill(0),
  untertitel: '', wer: 'sarvis', hervor: 0, nachhoeren: 0, nachhoerenGanz: 1,
  glut: new Map(), hintergrund: [], hgGesamt: 0, hgSeit: 0, hgFertig: false,
  tick: 0, kacheln: new Map(), verbunden: false,
};
WERKZEUGE.forEach(w => S.glut.set(w, 0));

const rgb = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
const mischen = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t));

// =====================================================================
// Zeichnen
// =====================================================================
const leinwand = document.getElementById('ring');
const p = leinwand.getContext('2d');
let skala = 1, versatzX = 0, versatzY = 0;

/* Eingepasst wird der INHALT, nicht das Raster.
 *
 * hud.py rechnet in 660x548, aber gemalt wird darin nur ein Kreis von
 * 176 Radius plus Beschriftung -- gut 470x460. Wer das ganze Raster
 * einpasst, bekommt auf einem hochkant gehaltenen Handy einen winzigen
 * Ring mit viel Schwarz darum: Der Platz geht an Flaeche verloren, die
 * nie bemalt wird.
 *
 * Also der Ausschnitt, in dem wirklich etwas steht -- und ein Deckel
 * nach oben, damit der Ring am grossen Bildschirm nicht ins Alberne
 * waechst. */
// 176 Kranzradius + 15 Abstand + bis zu 90 fuer das laengste Wort
// ("ENTWICKLUNG") ergeben 281 je Seite. Gemessen wurde das nicht
// geschaetzt: Bei 472 stand "PROGRAMME" halb ausserhalb des Bildes.
const INHALT_B = 580, INHALT_H = 470;
const INHALT_X = MITTE.x - INHALT_B / 2, INHALT_Y = MITTE.y - INHALT_H / 2 + 24;
const SKALA_MAX = 1.6;

function messen() {
  const dpr = window.devicePixelRatio || 1;
  // Das Canvas selbst messen, nicht seinen Elternteil. Hochkant ist es
  // ein Flex-Kind neben den Kacheln und damit KLEINER als die Bühne --
  // gemessen wurde der Ring dadurch zur Ellipse gestreckt, weil die
  // Pixelmaße des Canvas nicht mehr zu seiner Fläche im Layout passten.
  const b = leinwand.getBoundingClientRect();
  if (b.width < 2 || b.height < 2) return;
  leinwand.width = Math.round(b.width * dpr);
  leinwand.height = Math.round(b.height * dpr);
  skala = Math.min(b.width / INHALT_B, b.height / INHALT_H, SKALA_MAX) * dpr;
  versatzX = leinwand.width / 2 - MITTE.x * skala;
  versatzY = leinwand.height / 2 - (INHALT_Y + INHALT_H / 2) * skala;
}
window.addEventListener('resize', messen);
if (window.ResizeObserver) new ResizeObserver(messen).observe(leinwand);

function malen() {
  const farbeAus = () => {
    if (S.zustand === 'ruhig' && S.nachhoeren > 0) {
      // Der ruhige Ring zieht sich Richtung Cyan, je mehr Nachhoerfenster
      // noch offen ist -- damit man SIEHT, dass kein Weckwort noetig ist.
      const anteil = 0.30 + 0.35 * (S.nachhoeren / S.nachhoerenGanz);
      return mischen(FARBEN.ruhig, FARBEN.hoert, anteil);
    }
    return FARBEN[S.zustand] || FARBEN.ruhig;
  };
  const farbe = farbeAus();
  const atem = 0.5 + 0.5 * Math.sin(S.tick * 1.6);
  const staerke = (S.zustand === 'hoert' || S.zustand === 'spricht')
    ? S.geglaettet : Math.max(atem * 0.25, S.geglaettet);

  p.setTransform(1, 0, 0, 1, 0, 0);
  p.clearRect(0, 0, leinwand.width, leinwand.height);
  p.setTransform(skala, 0, 0, skala, versatzX, versatzY);

  untergrund(staerke);
  kranz(farbe);
  schein(farbe, staerke);
  if (S.zustand === 'denkt' || S.zustand === 'fragt') boegen(farbe);
  else striche(farbe);
  ring(farbe, staerke);
  kern(farbe, staerke);
  zustandswort(farbe);
}

function untergrund(staerke) {
  // Ohne diese Scheibe ist helle Schrift auf hellem Grund unlesbar.
  const r = KRANZ * 1.85, ry = r * 0.92;
  p.save(); p.translate(MITTE.x, MITTE.y); p.scale(1, ry / r);
  const v = p.createRadialGradient(0, 0, 0, 0, 0, r);
  const f = 1.30 * (0.8 + 0.2 * staerke);
  [[0, 178], [0.45, 146], [0.72, 74], [1, 0]].forEach(([s, a]) =>
    v.addColorStop(s, `rgba(6,10,20,${Math.min(255, a * f) / 255})`));
  p.fillStyle = v; p.beginPath(); p.arc(0, 0, r, 0, 6.2832); p.fill();
  p.restore();
}

function kranz(farbe) {
  const n = WERKZEUGE.length;
  WERKZEUGE.forEach((name, i) => {
    const w = -Math.PI / 2 + 2 * Math.PI * i / n;
    const cx = MITTE.x + Math.cos(w) * KRANZ, cy = MITTE.y + Math.sin(w) * KRANZ;
    let glut = S.glut.get(name) || 0;
    if (name === 'Entwicklung' && (S.hintergrund.length || S.hgFertig)) {
      const puls = 0.5 + 0.5 * Math.sin(S.tick * 2.4);
      glut = Math.max(glut, 0.30 + 0.40 * puls);
    }
    const kraft = Math.min(1, 0.95 + glut * 0.9);
    const c = glut > 0.02 ? farbe : [150, 168, 196];

    // Speiche nach innen
    p.strokeStyle = rgb(c, kraft * 0.35); p.lineWidth = 1;
    p.beginPath();
    p.moveTo(MITTE.x + Math.cos(w) * (KRANZ - 30), MITTE.y + Math.sin(w) * (KRANZ - 30));
    p.lineTo(MITTE.x + Math.cos(w) * (KRANZ - 17), MITTE.y + Math.sin(w) * (KRANZ - 17));
    p.stroke();

    if (glut > 0.02) {
      // Ein Schein HINTER dem Zeichen: eine duenne Linie hat zu wenig
      // Flaeche, um aus dem Augenwinkel aufzufallen.
      const v = p.createRadialGradient(cx, cy, 0, cx, cy, ICON * 1.6);
      v.addColorStop(0, rgb(c, Math.min(1, 0.5 * glut)));
      v.addColorStop(1, rgb(c, 0));
      p.fillStyle = v; p.beginPath(); p.arc(cx, cy, ICON * 1.6, 0, 6.2832); p.fill();
    }
    p.fillStyle = rgb(c, kraft);
    p.beginPath(); p.arc(cx, cy, 2.6 + glut * 3.0, 0, 6.2832); p.fill();

    // Beschriftung nach aussen, gesperrt und in Grossbuchstaben
    p.save();
    p.font = '600 8px "Segoe UI",system-ui,sans-serif';
    p.textAlign = Math.cos(w) < -0.3 ? 'right' : (Math.cos(w) > 0.3 ? 'left' : 'center');
    p.textBaseline = 'middle';
    saum(name.toUpperCase(),
      cx + Math.cos(w) * 15, cy + Math.sin(w) * 19 - 2, rgb(c, kraft));
    p.restore();
  });
}

function schein(farbe, staerke) {
  const r = RADIUS * (2.6 + staerke * 0.8);
  const v = p.createRadialGradient(MITTE.x, MITTE.y, 0, MITTE.x, MITTE.y, r);
  v.addColorStop(0, rgb(farbe, 0.20 + 0.28 * staerke));
  v.addColorStop(0.45, rgb(farbe, Math.round(40 * (0.4 + staerke)) / 255));
  v.addColorStop(1, rgb(farbe, 0));
  p.fillStyle = v; p.beginPath(); p.arc(MITTE.x, MITTE.y, r, 0, 6.2832); p.fill();
}

function striche(farbe) {
  // 72 Striche, an der Senkrechten gespiegelt: links und rechts gleich.
  p.lineCap = 'round'; p.lineWidth = 2.2;
  for (let i = 0; i < BALKEN; i++) {
    const idx = i < VERLAUF_LAENGE ? i : BALKEN - 1 - i;
    const wert = S.verlauf[idx] || 0;
    const w = -Math.PI / 2 + 2 * Math.PI * i / BALKEN;
    const laenge = 5 + wert * 46;
    p.strokeStyle = rgb(farbe, 0.30 + 0.55 * Math.min(1, wert * 1.6));
    p.beginPath();
    p.moveTo(MITTE.x + Math.cos(w) * (RADIUS + 7), MITTE.y + Math.sin(w) * (RADIUS + 7));
    p.lineTo(MITTE.x + Math.cos(w) * (RADIUS + 7 + laenge),
             MITTE.y + Math.sin(w) * (RADIUS + 7 + laenge));
    p.stroke();
  }
}

function boegen(farbe) {
  // Beim Nachdenken kein Ausschlag, sondern drei kreisende Boegen.
  p.lineCap = 'round'; p.lineWidth = 2.4;
  [[RADIUS + 16, 1.0, 110, 0.55], [RADIUS + 28, -0.7, 70, 0.42],
   [RADIUS + 40, 0.45, 40, 0.29]].forEach(([r, tempo, spanne, alpha]) => {
    const start = (S.tick * tempo * 200) % 360;
    p.strokeStyle = rgb(farbe, alpha);
    p.beginPath();
    p.arc(MITTE.x, MITTE.y, r, -start * Math.PI / 180,
          (-start - spanne) * Math.PI / 180, true);
    p.stroke();
  });
}

function ring(farbe, staerke) {
  p.strokeStyle = rgb(farbe, 0.85); p.lineWidth = 2;
  p.beginPath(); p.arc(MITTE.x, MITTE.y, RADIUS + staerke * 5, 0, 6.2832); p.stroke();
}

function kern(farbe, staerke) {
  const r = 6 + staerke * 9;
  const v = p.createRadialGradient(MITTE.x, MITTE.y, 0, MITTE.x, MITTE.y, r * 2.2);
  v.addColorStop(0, rgb(farbe, 0.9)); v.addColorStop(1, rgb(farbe, 0));
  p.fillStyle = v; p.beginPath(); p.arc(MITTE.x, MITTE.y, r * 2.2, 0, 6.2832); p.fill();
  p.fillStyle = 'rgba(235,245,255,.9)';
  p.beginPath(); p.arc(MITTE.x, MITTE.y, r * 0.45, 0, 6.2832); p.fill();
}

function zustandswort(farbe) {
  let wort = BESCHRIFTUNG[S.zustand] || '';
  if (S.zustand === 'ruhig' && S.nachhoeren > 0) wort = 'hört noch zu';
  p.save();
  p.font = '8px "Segoe UI",system-ui,sans-serif';
  p.textAlign = 'center'; p.textBaseline = 'middle';
  saum(wort.toUpperCase().split('').join(' '),
       MITTE.x, MITTE.y + RADIUS + 83, rgb(farbe, 0.92));
  p.restore();
}

function saum(text, x, y, farbe) {
  // Fuenfmal dunkel versetzt, dann einmal in Farbe -- derselbe Saum wie
  // in hud.py. Er ist der Grund, warum die Schrift ueber jedem
  // Untergrund lesbar bleibt.
  p.fillStyle = 'rgba(4,8,16,.55)';
  [[-1, 0], [1, 0], [0, -1], [0, 1], [1, 1]].forEach(([dx, dy]) =>
    p.fillText(text, x + dx, y + dy));
  p.fillStyle = farbe; p.fillText(text, x, y);
}

function schlag() {
  S.tick += 0.016;
  // Steigend schneller als fallend: Der Ring soll sofort ausschlagen,
  // aber nicht flackern.
  const k = S.pegel > S.geglaettet ? 0.45 : 0.12;
  S.geglaettet += (S.pegel - S.geglaettet) * k;
  S.verlauf.push((S.zustand === 'hoert' || S.zustand === 'spricht')
    ? S.geglaettet
    : Math.max(S.geglaettet, (S.verlauf[S.verlauf.length - 1] || 0) * 0.85));
  if (S.verlauf.length > VERLAUF_LAENGE) S.verlauf.shift();
  S.glut.forEach((v, k2) => { if (v > 0.001) S.glut.set(k2, v * 0.975); });
  if (S.hervor > 0) S.hervor -= 0.016;
  if (S.nachhoeren > 0) S.nachhoeren -= 0.016;
  malen();
  requestAnimationFrame(schlag);
}

// =====================================================================
// Kacheln und Hintergrund
// =====================================================================
const kachelraum = document.getElementById('kacheln');

/* NEUN FORMEN, EIN AUSSEHEN -- uebersetzt aus kachel.py.
 *
 * Uebersetzt, nicht neu erfunden: Die Zahlen dort sind gemessen, und die
 * Begruendungen daneben gelten hier genauso. Was hier steht, sind nur
 * die Stellen, an denen der Browser etwas anderes verlangt als QPainter.
 *
 * DIE BREITE IST DER EINE GROSSE UNTERSCHIED.
 * kachel.py darf sich seine Breite aussuchen -- ein eigenes Fenster ist
 * so breit, wie sein Inhalt es braucht (bis 800 beim Fluss). Hier steckt
 * die Kachel in einer Spalte: am Rechner rechts neben dem Ring, hoechstens
 * 290 Punkte breit, auf dem Handy darunter ueber die volle Breite (rund
 * 390). Beides ist WENIGER als die 800 des Flusses und die 708 des
 * Ablaufs, und ein Bild einfach herunterzuskalieren waere die schlechteste
 * aller Antworten: Bei Faktor 0,36 ist die Schrift 4 Punkte hoch, und ein
 * Diagramm, dessen Beschriftung niemand lesen kann, ist ein Muster.
 *
 * Deshalb wird nicht skaliert, sondern GERECHNET: Jede Form bekommt die
 * wirklich vorhandene Breite und legt ihr Inneres darin aus. Was dabei je
 * Form entschieden wurde, steht bei der Form.
 *
 * KEIN HERVORHEBEN. kachel.py kann eine Zeile leuchten lassen (hervor),
 * aber ueber den Draht geht dafuer nichts -- leuchten() ist Qt-intern.
 * Was hier nicht ankommen kann, wird auch nicht gebaut.
 */

// --- Schriften ---------------------------------------------------------
// Messen und Malen holen sich ihre Schrift HIER, aus demselben Grund wie
// _schrift_klein() drueben: Stuenden die Zeilen an zwei Stellen, waere
// der Tag absehbar, an dem eine davon springt und der Umbruch nicht mehr
// zum Kasten passt.
const SCHRIFT_KLEIN = '11px "Segoe UI",system-ui,-apple-system,sans-serif';
const SCHRIFT_FUSS = '9px "Segoe UI",system-ui,-apple-system,sans-serif';
const ZH = 14;          // Zeilenhoehe der Datenschrift
const ZF = 12;          // ... der Fussschrift
const GRUND = [8, 13, 20];   // der Kachelgrund, gegen den gerechnet wird
/* WELCHER TEXT WELCHE FARBE TRAEGT.
   kachel.py schreibt ALLES in der Kachelfarbe -- dort ist eine Kachel
   ein eigenes Fenster ueber einem fremden Bildschirm, und die eine
   Farbe ist das, was sie zusammenhaelt. Hier liegt sie in Sarvis'
   eigener Oberflaeche, und die vorhandene Form "liste" setzt ihre
   Zeilen seit jeher in die Schriftfarbe der Seite. Zwei Regeln in
   einer Kachel saehen aus wie zwei Kacheln, also gilt durchgehend:

     Text, den man LIEST (Bezeichnungen, Betraege, Fliesstext,
     Nachrichten)                        -> Schriftfarbe der Seite
     Alles GEZEICHNETE und die Beschriftung AM Bild (Achsen, Marken,
     Zwischenueberschriften, Raender, Flaechen, Baender)
                                         -> Kachelfarbe

   Im Fluss faellt beides zusammen -- die Beschriftung liegt AUF dem
   Band. Dort wird gerechnet statt gewaehlt, siehe schriftAuf(). */
const TINTE = [232, 241, 253];

// Die Marken. Ein stummer Schnitt sieht aus wie ein vollstaendiger Text.
const MARKE = '[… gekürzt]';
const MARKE_ALT = '[… ältere ausgeblendet]';
const MARKE_OHNE = '[… ohne negative Werte]';
const MARKE_KANTEN = '[… unvollständige Bänder weggelassen]';
const MARKE_KREIS = '[… Kreis aufgetrennt]';
const MARKE_TIEF = '[… tiefere Stufen weggelassen]';

const _messer = document.createElement('canvas').getContext('2d');
function misst(text, schrift) {
  _messer.font = schrift || SCHRIFT_KLEIN;
  return _messer.measureText(String(text == null ? '' : text)).width;
}

/* Wortweiser Umbruch -- wie _umbrechen() drueben, und aus demselben Grund
 * selbst gemacht: Der Browser bricht erst beim Malen um, und dann ist es
 * zu spaet. Die Hoehe der Blase, der Deckel des Fliesstextes und die Zahl
 * der Zeilen in einem Ablauf-Kasten stehen VORHER fest oder gar nicht.
 *
 * Ein Wort, das allein nicht passt, wird hart getrennt: Eine URL liefe
 * sonst aus der Blase heraus und waere zur Haelfte weg. */
function umbrechen(text, breite, schrift) {
  const zeilen = [];
  for (const absatz of String(text == null ? '' : text).split('\n')) {
    const worte = absatz.split(/\s+/).filter(Boolean);
    if (!worte.length) { zeilen.push(''); continue; }
    let zeile = '';
    for (let wort of worte) {
      const probe = zeile ? zeile + ' ' + wort : wort;
      if (misst(probe, schrift) <= breite) { zeile = probe; continue; }
      if (zeile) { zeilen.push(zeile); zeile = ''; }
      while (misst(wort, schrift) > breite && wort.length > 1) {
        let n = 1;
        while (n < wort.length && misst(wort.slice(0, n + 1), schrift) <= breite) n++;
        zeilen.push(wort.slice(0, n));
        wort = wort.slice(n);
      }
      zeile = wort;
    }
    if (zeile) zeilen.push(zeile);
  }
  return zeilen;
}

function kuerzen(text, breite, schrift) {
  text = String(text == null ? '' : text);
  if (breite <= 0) return '';
  if (misst(text, schrift) <= breite) return text;
  let n = text.length;
  while (n > 0 && misst(text.slice(0, n) + '…', schrift) > breite) n--;
  return n > 0 ? text.slice(0, n) + '…' : '';
}

// --- Zahlen -------------------------------------------------------------
const zahlVon = v => (typeof v === 'number' && isFinite(v)) ? v : null;

/* 1234.5 -> "1.234,50". Ohne Vorzeichen, das setzt der Aufrufer.
   Zwei Nachkommastellen nur, wenn es welche gibt. */
function zahlDeutsch(wert) {
  const stellen = Math.abs(wert - Math.round(wert)) < 0.005 ? 0 : 2;
  return Math.abs(wert).toLocaleString('de-DE',
    { minimumFractionDigits: stellen, maximumFractionDigits: stellen });
}

/* Unter zehn Prozent eine Nachkommastelle, darueber keine. Was auf null
   runden wuerde, wird "<0,1 %": Eine gemalte Null neben einem sichtbaren
   Stueck waere ein Widerspruch. */
function prozentText(anteil) {
  const p = anteil * 100;
  if (p <= 0) return '0 %';
  if (p < 0.1) return '<0,1 %';
  if (p < 10) return p.toFixed(1).replace('.', ',') + ' %';
  return p.toFixed(0) + ' %';
}

/* Die Differenz rechnet die Kachel SELBST -- eine gerechnete Zahl kann
   nicht halluziniert sein, eine uebergebene schon. Fehlt eine der beiden
   Zahlen, wird nichts behauptet. */
function differenz(a, b) {
  a = zahlVon(a); b = zahlVon(b);
  if (a === null || b === null) return { text: '', richtung: 0 };
  const d = a - b;
  if (Math.abs(d) < 0.005) return { text: '±0', richtung: 0 };
  // Echtes Minuszeichen, kein Bindestrich: der ist neben einer Ziffer
  // zu kurz, um aufzufallen.
  return { text: (d > 0 ? '+' : '−') + zahlDeutsch(d), richtung: d > 0 ? 1 : -1 };
}

// --- Farbe ---------------------------------------------------------------
const FARBE_MEHR = [126, 224, 168];      // mehr, NICHT "gut"
const FARBE_WENIGER = [255, 138, 128];   // weniger, NICHT "schlecht"

function nachHsv(c) {
  const r = c[0] / 255, g = c[1] / 255, b = c[2] / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
  let h = 0;
  if (d > 1e-9) {
    if (max === r) h = ((g - b) / d) % 6;
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h /= 6;
    if (h < 0) h += 1;
  } else h = -1;                          // unbunt
  return [h, max > 0 ? d / max : 0, max];
}

function ausHsv(h, s, v) {
  if (h < 0 || s <= 0) { const w = Math.round(v * 255); return [w, w, w]; }
  const i = Math.floor(h * 6), f = h * 6 - i;
  const p = v * (1 - s), q = v * (1 - f * s), t = v * (1 - (1 - f) * s);
  const tab = [[v, t, p], [q, v, p], [p, v, t], [p, q, v], [t, p, v], [v, p, q]];
  return tab[i % 6].map(x => Math.round(Math.max(0, Math.min(1, x)) * 255));
}

/* Die i-te Abstufung der Kachelfarbe -- kein Regenbogen.
 *
 * Drei Groessen wandern gleichzeitig (Ton, Saettigung, Helligkeit) statt
 * nur der Helligkeit: Wandert nur eine, faellt die ganze Unterscheidung
 * aus, sobald sie fuer einen Betrachter ausfaellt.
 *
 * Vergeben wird UEBER KREUZ (0, 4, 1, 5, …), damit zwei im Kreis
 * benachbarte Stuecke moeglichst weit auseinanderliegen. Der Reihe nach
 * lagen bei acht Stuecken zwei Nachbarn 1,08:1 auseinander -- die Kante
 * zwischen ihnen war keine. */
function stufe(farbe, i, anzahl) {
  if (anzahl <= 1) return farbe.slice();
  const [h, s, v] = nachHsv(farbe);
  const platz = (i % 2) * Math.ceil(anzahl / 2) + Math.floor(i / 2);
  const anteil = platz / (anzahl - 1);
  if (h < 0) return ausHsv(-1, 0, Math.max(0, v * (1 - 0.62 * anteil)));
  return ausHsv((h + 0.055 * anteil) % 1,
    Math.max(0, Math.min(1, s * (1 - 0.38 * anteil))),
    Math.max(0, Math.min(1, v * (1 - 0.58 * anteil))));
}

/* Relative Helligkeit nach WCAG -- nicht (r+g+b)/3: Gruen traegt zur
   empfundenen Helligkeit gut siebenmal so viel bei wie Blau, und ein
   Mittelwert schaetzte ausgerechnet die beiden Kachelfarben falsch ein,
   weil die eine orange und die andere gruen ist. */
function leuchtdichte(c) {
  const k = v => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  return 0.2126 * k(c[0]) + 0.7152 * k(c[1]) + 0.0722 * k(c[2]);
}

/* Was man WIRKLICH sieht, wenn ton mit dieser Deckung ueber dem
   Kachelgrund liegt. Ein Band ist halbdurchsichtig; seine Farbe allein
   sagt nichts darueber, wie hell die Stelle am Ende ist. */
function ueberGrund(ton, deckung) {
  const rest = 1 - deckung;
  return ton.map((v, i) => Math.round(v * deckung + GRUND[i] * rest));
}

/* Welche Schrift auf DIESEM Grund noch zu lesen ist.
 *
 * Die Kachelfarbe bleibt, solange sie traegt -- eine Kachel, in der die
 * Beschriftung mal orange und mal weiss ist, sieht aus wie zwei Kacheln.
 * Erst wenn sie MESSBAR nicht mehr traegt, wird gewechselt. Die Schwelle
 * ist die 4,5:1 aus WCAG fuer normalen Fliesstext, nicht die 3,0:1 fuer
 * grosse Schrift: Hier steht 11 px, und das ist keine grosse Schrift. */
function schriftAuf(grund, kerze) {
  const hell = leuchtdichte(grund);
  const kontrast = c => {
    const dort = leuchtdichte(c);
    return (Math.max(hell, dort) + 0.05) / (Math.min(hell, dort) + 0.05);
  };
  if (kontrast(kerze) >= 4.5) return kerze;
  const dunkel = GRUND, weiss = [245, 248, 252];
  return kontrast(dunkel) >= kontrast(weiss) ? dunkel : weiss;
}

// --- Raenge: die eine Rechnung, die sich Fluss und Ablauf teilen ---------
/* Spalte (Fluss) bzw. Zeile (Ablauf) je Knoten -- der LAENGSTE Weg von
 * vorn, nicht der kuerzeste: Nur so zeigt jede Kante nach vorn. Beim
 * kuerzesten landet ein Knoten neben seinem eigenen Vorgaenger.
 *
 * DER KREIS IST DER PUNKT DIESER FUNKTION. Ein Modell kann "A -> B -> A"
 * schicken -- kein boeser Wille, sondern zwei Buchungen, die es beide
 * gesehen hat. Eine Rangrechnung, die einfach entspannt, bis sich nichts
 * mehr aendert, laeuft dann bis zum Stillstand der Anzeige. Gezaehlt
 * werden deshalb die offenen Eingaenge; bleiben nur noch Knoten im Kreis,
 * wird der mit den wenigsten aufgemacht und seine restlichen Eingaenge
 * werden AUFGETRENNT -- weggelassen und vermerkt. */
function raenge(knoten, kanten) {
  const aus = new Map(), ein = new Map(), rang = new Map();
  knoten.forEach(k => { aus.set(k, []); ein.set(k, 0); rang.set(k, 0); });
  kanten.forEach(([a, b], nr) => {
    if (!aus.has(a) || !ein.has(b)) return;
    aus.get(a).push(nr); ein.set(b, ein.get(b) + 1);
  });
  const fertig = new Set(), getrennt = new Set();
  const schlange = knoten.filter(k => ein.get(k) === 0);
  while (fertig.size < knoten.length) {
    if (!schlange.length) {
      const offen = knoten.filter(k => !fertig.has(k));
      let naechster = offen[0];
      for (const k of offen) if (ein.get(k) < ein.get(naechster)) naechster = k;
      kanten.forEach(([a, b], nr) => {
        if (b === naechster && !getrennt.has(nr) && !fertig.has(a)) {
          getrennt.add(nr); ein.set(naechster, ein.get(naechster) - 1);
        }
      });
      schlange.push(naechster);
    }
    const k = schlange.shift();
    if (fertig.has(k)) continue;
    fertig.add(k);
    for (const nr of aus.get(k)) {
      if (getrennt.has(nr)) continue;
      const b = kanten[nr][1];
      rang.set(b, Math.max(rang.get(b), rang.get(k) + 1));
      ein.set(b, ein.get(b) - 1);
      if (ein.get(b) <= 0 && !fertig.has(b)) schlange.push(b);
    }
  }
  return [rang, getrennt];
}

// --- Bausteine, die mehrere Formen brauchen -----------------------------
const markenZeilen = (marken, farbe) => marken
  .map(t => `<div class="marke" style="color:${rgb(farbe, 0.45)}">${sicher(t)}</div>`)
  .join('');

const svgText = (x, y, text, farbe, opt) => {
  const o = opt || {};
  return `<text x="${x.toFixed(1)}" y="${y.toFixed(1)}" fill="${farbe}"`
    + ` font-family="Segoe UI,system-ui,sans-serif"`
    + ` font-size="${o.gross || 11}"`
    + (o.gewicht ? ` font-weight="${o.gewicht}"` : '')
    + (o.sperr ? ` letter-spacing="${o.sperr}"` : '')
    + ` text-anchor="${o.anker || 'start'}" dominant-baseline="central"`
    + `>${sicher(text)}</text>`;
};

// =====================================================================
// 1  liste -- Zeilen mit Wert rechts und Balken hinter der Schrift
// =====================================================================
function formListe(punkte, farbe) {
  const zahlen = punkte.map(x => zahlVon(x.zahl)).filter(x => x !== null && x > 0);
  const groesste = zahlen.length ? Math.max(...zahlen) : 0;
  return punkte.map(x => {
    const z = zahlVon(x.zahl);
    // Nur positive Zahlen bekommen einen Balken: Einer fuer minus achtzig
    // muesste in die andere Richtung zeigen, und solange diese Ueberlegung
    // nicht angestellt ist, lieber keiner als ein falscher.
    const breite = (groesste && z !== null && z > 0) ? (100 * z / groesste) : 0;
    return `<div class="zeile">
      ${breite ? `<i class="balken" style="width:${breite}%;background:${rgb(farbe, 1)}"></i>` : ''}
      <span>${sicher(x.text)}</span><span>${sicher(x.wert)}</span></div>`;
  }).join('');
}

// =====================================================================
// 2  blasen -- Gespraechsblasen, links der andere, rechts ich
// =====================================================================
/* Die Seite ist die Auskunft darueber, wer geschrieben hat -- die
 * Sehgewohnheit aus jedem Messenger, und sie kostet keine Zeile Text.
 * Damit sie auch bei gleich breiten Blasen traegt, unterscheiden sie sich
 * zusaetzlich: meine ist gefuellt, seine traegt einen Balken an der Kante.
 *
 * Gekappt wird OBEN, am Aelteren: Ein Verlauf wird von unten gelesen. */
function formBlasen(punkte, farbe, W) {
  const ANTEIL = 0.78, R = 7, LUFT = 7, MAXZEILEN = 7, DECKEL = 340;
  const innen = Math.round(W * ANTEIL) - 2 * R;
  const blasen = punkte.map(pt => {
    let zeilen = umbrechen(pt.text, innen);
    if (!zeilen.length) zeilen = [''];
    if (zeilen.length > MAXZEILEN) zeilen = zeilen.slice(0, MAXZEILEN - 1).concat([MARKE]);
    // So breit wie ihre laengste Zeile, nicht so breit wie erlaubt: Ein
    // "ja" in einem 250 Punkte breiten Kasten sieht aus wie ein Fehler.
    const breit = Math.min(innen, Math.max(...zeilen.map(z => misst(z))));
    return {
      zeilen, wert: String(pt.wert || ''), mir: !!pt.von_mir,
      breite: Math.ceil(breit) + 2 * R, hoehe: zeilen.length * ZH + 2 * R,
      // Die Zeit steht UNTER der Blase, nicht darin: darin konkurriert
      // sie mit dem Text um die Breite, und bei kurzen Nachrichten
      // gewinnt sie.
      fuss: pt.wert ? ZF : 0,
    };
  });

  let platz = DECKEL, gekappt = false;
  const behalten = [];
  for (let i = blasen.length - 1; i >= 0; i--) {
    const braucht = blasen[i].hoehe + blasen[i].fuss + (behalten.length ? LUFT : 0);
    if (braucht > platz && behalten.length) { gekappt = true; break; }
    platz -= braucht;
    behalten.unshift(blasen[i]);
  }

  return (gekappt ? `<div class="marke" style="color:${rgb(farbe, 0.45)}">${MARKE_ALT}</div>` : '')
    + behalten.map(b => {
      const grund = rgb(farbe, b.mir ? 0.22 : 0.12);
      const kante = b.mir ? '' : `box-shadow:inset 2.5px 0 0 ${rgb(farbe, 0.70)};`;
      return `<div class="blase${b.mir ? ' mir' : ''}" style="width:${b.breite}px;background:${grund};${kante}">`
        + b.zeilen.map(z => `<div>${sicher(z) || '&nbsp;'}</div>`).join('')
        + `</div>`
        + (b.fuss ? `<div class="blasenzeit${b.mir ? ' mir' : ''}">${sicher(b.wert)}</div>` : '');
    }).join('');
}

// =====================================================================
// 3  vergleich -- zwei Wertspalten und eine selbst gerechnete Differenz
// =====================================================================
/* Drueben stehen feste Spaltenbreiten (68 / 68 / 74), weil QFontMetrics
 * dort einmal misst und das Fenster danach 360 breit ist. Hier gibt es
 * die 360 nicht -- also uebernimmt das Raster die Aufteilung: Die drei
 * Zahlenspalten bekommen, was sie brauchen, die Bezeichnung den Rest und
 * kuerzt sich selbst. Das ist dieselbe Rangfolge wie drueben (Zahlen
 * vollstaendig, Name notfalls gekuerzt), nur vom Browser gemessen. */
function formVergleich(punkte, farbe, W, m) {
  const spalten = (m.spalten || []).map(String);
  const kopf = spalten.length
    ? `<div class="k n"></div>`
    + `<div class="k z">${sicher(spalten[0] || '')}</div>`
    + `<div class="k z">${sicher(spalten[1] || '')}</div>`
    + `<div class="k z">Differenz</div>`
    : '';
  const zeilen = punkte.map(pt => {
    const d = differenz(pt.zahl, pt.zahl2);
    let dz = '';
    if (d.text) {
      const c = d.richtung === 0 ? rgb(farbe, 0.55)
        : rgb(d.richtung > 0 ? FARBE_MEHR : FARBE_WENIGER, 0.95);
      // Die Farbe ist nie das einzige Zeichen: Rot und Gruen sind fuer
      // rund jeden zwoelften Mann dieselbe Farbe. Vor der Zahl steht ihr
      // Vorzeichen, davor ein Dreieck in dieselbe Richtung -- und selbst
      // gemalt, nicht als Zeichen aus einer Schrift, die fehlen kann.
      const pfeil = d.richtung === 0 ? '' :
        `<svg width="7" height="6" viewBox="0 0 7 6" aria-hidden="true"><polygon points="${
          d.richtung > 0 ? '0,5 7,5 3.5,0' : '0,1 7,1 3.5,6'}" fill="${c}"/></svg>`;
      dz = `<span style="color:${c}">${pfeil}${sicher(d.text)}</span>`;
    }
    return `<div class="n">${sicher(pt.text)}</div>`
      + `<div class="z">${sicher(pt.wert)}</div>`
      + `<div class="z">${sicher(pt.wert2)}</div>`
      + `<div class="z d">${dz}</div>`;
  }).join('');
  return `<div class="vgl">${kopf}${zeilen}</div>`;
}

// =====================================================================
// 4  text -- Fliesstext fuer eine Zusammenfassung oder einen Auszug
// =====================================================================
function formText(punkte, farbe, W) {
  const DECKEL = 18;
  let zeilen = [];
  punkte.forEach(pt => {
    if (zeilen.length) zeilen.push('');        // Absatzabstand
    zeilen = zeilen.concat(umbrechen(pt.text, W));
  });
  // Die Marke ERSETZT die letzte Zeile, sie kommt nicht dazu: sonst waere
  // die gekuerzte Fassung hoeher als der Deckel.
  if (zeilen.length > DECKEL) zeilen = zeilen.slice(0, DECKEL - 1).concat([MARKE]);
  return `<div class="fliess">`
    + zeilen.map(z => z === MARKE
      ? `<div class="marke" style="color:${rgb(farbe, 0.45)}">${sicher(z)}</div>`
      : `<div>${sicher(z) || '&nbsp;'}</div>`).join('')
    + `</div>`;
}

// =====================================================================
// 5  balken -- senkrechte Saeulen mit Grundlinie
// =====================================================================
/* DIE GRUNDLINIE LIEGT NICHT AM BODEN, sondern dort, wo die Null liegt:
 * Sind Ausgaben und Einnahmen in einem Bild, geht ein Teil der Balken
 * nach unten. Beide Richtungen teilen sich die Hoehe im Verhaeltnis ihrer
 * Betraege. Zwei getrennte Massstaebe waeren bequemer zu rechnen und eine
 * Luege: Dann waere ein Minus von 20 so lang wie ein Plus von 2.000.
 *
 * NACH UNTEN WIRD NICHT ROT, sondern UMRISSEN. Die Richtung sagt es
 * schon; eine zweite Farbe daneben waere ausgerechnet das Paar
 * Gruen/Rot, das rund jeder zwoelfte Mann nicht trennt. Die Form bleibt
 * auch in Graustufen stehen.
 *
 * DIE BESCHRIFTUNG duennt in drei Stufen aus: ungekuerzt, sonst drei
 * Zeichen, sonst nur noch jeder n-te Balken. Drei Zeichen ohne
 * Auslassungspunkte -- bei dieser Groesse frisst das "…" ein Drittel des
 * Platzes, und "Ja…" sagt weniger als "Jan". */
function formBalken(punkte, farbe, W) {
  if (!punkte.length) return '';           // Kein Balken, keine Achse.
  const HOCH = 96, FUSS = 3, SCHMAL = 3, SCHRITTE = [2, 3, 4, 6];
  const n = punkte.length;
  const fach = W / n;
  const luft = Math.max(2, Math.min(5, fach * 0.22));
  const breit = Math.max(SCHMAL, fach - luft);

  const zahlen = punkte.map(p => zahlVon(p.zahl));
  const pos = zahlen.filter(z => z !== null && z > 0);
  const neg = zahlen.filter(z => z !== null && z < 0);
  const dach = pos.length ? Math.max(...pos) : 0;
  const boden = neg.length ? Math.min(...neg) : 0;
  const spanne = dach - boden;
  const nulllinie = spanne > 0 ? HOCH * (dach / spanne) : HOCH;

  const voll = punkte.map(p => String(p.text || ''));
  const kurz = voll.map(t => t.slice(0, 3));
  const passt = (texte, schritt) => {
    const platz = fach * schritt - 2;
    for (let i = 0; i < n; i += schritt)
      if (misst(texte[i], SCHRIFT_FUSS) > platz) return false;
    return true;
  };
  let texte = voll, schritt = 1;
  if (!passt(voll, 1)) {
    texte = kurz;
    if (!passt(kurz, 1)) schritt = SCHRITTE.find(s => passt(kurz, s)) || SCHRITTE[SCHRITTE.length - 1];
  }

  // Der hoechste und der tiefste Balken werden angeschrieben. Ohne das
  // waere die Kachel ein Muster: Man saehe, dass Juli groesser ist als
  // Juni, aber nicht, ob es um 30 oder 3.000 Euro geht.
  let obenI = -1, untenI = -1;
  zahlen.forEach((z, i) => {
    if (z === null) return;
    if (z > 0 && (obenI < 0 || z > zahlen[obenI])) obenI = i;
    if (z < 0 && (untenI < 0 || z < zahlen[untenI])) untenI = i;
  });
  const geschrieben = i => {
    if (punkte[i].wert) return String(punkte[i].wert);
    const z = zahlen[i];
    return z === null ? '' : (z < 0 ? '−' : '') + zahlDeutsch(z);
  };

  const yF = ZF + 2, yNull = yF + nulllinie;
  let yM = yF + HOCH + FUSS;
  const H = yM + ZF + (untenI >= 0 ? ZF : 0);

  let s = '';
  zahlen.forEach((z, i) => {
    if (z === null || spanne <= 0 || Math.abs(z) < 1e-9) return;   // keine gemalte Null
    const laenge = HOCH * (Math.abs(z) / spanne);
    const x = i * fach + (fach - breit) / 2;
    if (z > 0) {
      s += `<rect x="${x.toFixed(1)}" y="${(yNull - laenge).toFixed(1)}" width="${breit.toFixed(1)}" height="${laenge.toFixed(1)}" fill="${rgb(farbe, 0.58)}"/>`;
    } else {
      s += `<rect x="${(x + 0.5).toFixed(1)}" y="${(yNull + 0.5).toFixed(1)}" width="${Math.max(1, breit - 1).toFixed(1)}" height="${Math.max(1, laenge - 1).toFixed(1)}" fill="${rgb(farbe, 0.16)}" stroke="${rgb(farbe, 0.62)}" stroke-width="1"/>`;
    }
  });
  // Die Grundlinie zuletzt und ueber den Balken: Sie ist die Achse, an
  // der abgelesen wird, und darf von keinem Balken verdeckt werden.
  s += `<line x1="0" y1="${yNull.toFixed(1)}" x2="${W}" y2="${yNull.toFixed(1)}" stroke="${rgb(farbe, 0.55)}" stroke-width="1"/>`;

  const anschreiben = (text, mitte, oben) => {
    const b = misst(text, SCHRIFT_FUSS) + 2;
    const x = Math.min(Math.max(mitte - b / 2, 0), Math.max(0, W - b)) + b / 2;
    return svgText(x, oben + ZF / 2, text, rgb(farbe, 0.80), { gross: 9, anker: 'middle' });
  };
  if (obenI >= 0) s += anschreiben(geschrieben(obenI), (obenI + 0.5) * fach, 0);
  if (untenI >= 0) { s += anschreiben(geschrieben(untenI), (untenI + 0.5) * fach, yM); yM += ZF; }

  texte.forEach((t, i) => {
    if (i % schritt !== 0 || !t) return;
    const platz = fach * schritt - 2;
    s += svgText((i + 0.5) * fach, yM + ZF / 2, kuerzen(t, platz, SCHRIFT_FUSS),
      rgb(farbe, 0.62), { gross: 9, anker: 'middle' });
  });

  return `<svg class="bild" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${s}</svg>`;
}

// =====================================================================
// 6  torte -- Kreis und Legende
// =====================================================================
/* KEIN STUECK WIRD AUFGEBLASEN. Ein Bild, das 0,5 Prozent wie 5 Prozent
 * aussehen laesst, behauptet etwas Falsches -- und zwar lautlos. Eine
 * Prozentzahl steht nur IM Stueck, wenn der Winkel mindestens 30 Grad
 * hat UND die Sehne auf dem Beschriftungsradius breit genug ist.
 *
 * NEGATIVE UND FEHLENDE WERTE bekommen kein Stueck: Ein negativer Anteil
 * ist keiner. Sie stehen aber mit ihrem Betrag in der Legende, ohne
 * Prozentzahl und mit leerem Kaestchen, und eine Marke sagt, dass die
 * 100 Prozent sie nicht enthalten.
 *
 * WO DIE LEGENDE STEHT, entscheidet die Breite. Drueben stehen Kreis und
 * Legende immer nebeneinander, weil das Fenster dafuer 320 breit sein
 * darf: 104 Kreis + 14 Luft + 174 Legende. Hier sind am Rechner nur rund
 * 264 Punkte da -- nebeneinander bliebe der Legende 146, und aus
 * "Lebensmittel 612,40 21 %" wuerde "Lebens… 612,40 21 %". Also: unter
 * 300 Punkten Kreis oben, Legende darunter ueber die volle Breite. Auf
 * dem Handy (rund 364) passt beides nebeneinander, und dort steht es
 * auch so. */
function formTorte(punkte, farbe, W) {
  if (!punkte.length) return '';
  const AUS = 4, LUFT = 14, ZEILE = 16;
  const stapeln = W < 300;
  const RING = stapeln ? 124 : 104;
  const rad = (RING - 2 * AUS) / 2;

  const werte = punkte.map(p => { const z = zahlVon(p.zahl); return (z !== null && z > 0) ? z : null; });
  const summe = werte.reduce((s, w) => s + (w || 0), 0);
  const fehlt = werte.some(w => w === null);
  const ring = summe > 0;
  const anzahl = punkte.length;

  // Die Winkel entstehen als Fliesskommagrad und werden AUFSUMMIERT
  // weitergereicht: Rundet man acht Stuecke einzeln, fehlen am Ende ein
  // paar Zehntelgrad, und der Kreis hat einen feinen Spalt bei zwoelf Uhr.
  let winkel = 90;
  const stuecke = werte.map((w, i) => {
    const anteil = (w !== null && summe > 0) ? w / summe : 0;
    const spanne = -360 * anteil;
    const prozent = w !== null ? prozentText(anteil) : '';
    const halb = rad * 0.62;
    const sehne = 2 * halb * Math.sin(Math.abs(spanne) * Math.PI / 360);
    const st = {
      i, start: winkel, spanne, prozent, stueck: w !== null,
      innen: (w !== null && Math.abs(spanne) >= 30
        && sehne >= misst(prozent) + 4) ? prozent : '',
    };
    winkel += spanne;
    return st;
  });

  let kreis = '';
  if (ring) {
    const cx = RING / 2, cy = RING / 2;
    const punktAuf = (a, r) => [cx + r * Math.cos(a * Math.PI / 180),
    cy - r * Math.sin(a * Math.PI / 180)];
    let pfade = '';
    stuecke.forEach(st => {
      if (!st.stueck || Math.abs(st.spanne) < 1e-9) return;
      const f = rgb(stufe(farbe, st.i, anzahl), 0.86);
      if (Math.abs(st.spanne) >= 359.99) {
        pfade += `<circle cx="${cx}" cy="${cy}" r="${rad}" fill="${f}"/>`;
        return;
      }
      const [x0, y0] = punktAuf(st.start, rad);
      const [x1, y1] = punktAuf(st.start + st.spanne, rad);
      const gross = Math.abs(st.spanne) > 180 ? 1 : 0;
      // Die Fuge zwischen zwei Stuecken hat die Farbe des Grundes. Sie
      // ist der eigentliche Grund, warum benachbarte Abstufungen
      // auseinanderzuhalten sind: Selbst wenn zwei Toene fuer jemanden
      // gleich aussehen, bleibt die Kante sichtbar.
      pfade += `<path d="M${cx},${cy} L${x0.toFixed(2)},${y0.toFixed(2)}`
        + ` A${rad},${rad} 0 ${gross} 1 ${x1.toFixed(2)},${y1.toFixed(2)} Z"`
        + ` fill="${f}" stroke="${rgb(GRUND, 0.85)}" stroke-width="1"/>`;
    });
    // Die Prozentzahlen zuletzt, damit keine Fuge darueber laeuft.
    stuecke.forEach(st => {
      if (!st.innen) return;
      const a = (st.start + st.spanne / 2) * Math.PI / 180;
      const x = cx + Math.cos(a) * rad * 0.62, y = cy - Math.sin(a) * rad * 0.62;
      // Auf dunklen Stuecken hell schreiben, auf hellen dunkel -- sonst
      // verschwindet die Zahl in der eigenen Abstufung.
      const g = stufe(farbe, st.i, anzahl);
      const c = (Math.max(g[0], g[1], g[2]) / 255 > 0.62) ? GRUND : [245, 248, 252];
      pfade += svgText(x, y, st.innen, rgb(c, 0.95), { anker: 'middle' });
    });
    kreis = `<svg class="bild ring" viewBox="0 0 ${RING} ${RING}" width="${RING}" height="${RING}">${pfade}</svg>`;
  }

  const legende = stuecke.map(st => {
    const pt = punkte[st.i];
    const tupf = st.stueck
      ? `<i class="tupf" style="background:${rgb(stufe(farbe, st.i, anzahl), 1)}"></i>`
      // Kein Stueck, kein Tupfer: ein leeres Kaestchen sagt, dass dieser
      // Posten im Kreis nicht vorkommt.
      : `<i class="tupf leer" style="border-color:${rgb(farbe, 0.35)}"></i>`;
    return `<div class="leg">${tupf}<span class="nm">${sicher(pt.text)}</span>`
      + `<span class="wt">${sicher(pt.wert)}</span>`
      + `<span class="pz">${sicher(st.prozent)}</span></div>`;
  }).join('');

  return `<div class="torte${stapeln ? ' hoch' : ''}">`
    + kreis + `<div class="legende">${legende}</div></div>`
    + (fehlt ? `<div class="marke" style="color:${rgb(farbe, 0.45)}">${MARKE_OHNE}</div>` : '');
}

// =====================================================================
// 7  kategorien -- Zwischenueberschriften und Gruppensummen
// =====================================================================
/* Gruppiert wird in der Reihenfolge des ERSTEN Auftretens, nicht
 * alphabetisch: Der Aufrufer hat eine Reihenfolge im Kopf.
 *
 * Die Gruppensumme rechnet die Kachel -- aber nur, wenn JEDER Eintrag
 * der Gruppe eine Zahl hat. Eine Summe ueber unvollstaendige Posten
 * sieht aus wie ein Ergebnis und ist keines.
 *
 * Gekappt wird UNTEN, anders als bei den Blasen: Ein Verlauf wird von
 * unten gelesen, eine aufgeschluesselte Ausgabenliste von oben.
 *
 * Der Balken hinter der Schrift misst sich am groessten Posten
 * UEBERHAUPT, nicht am groessten der eigenen Gruppe -- sonst saehen die
 * 40 Euro Freizeit aus wie die 1.098 Euro Wohnen. */
function formKategorien(punkte, farbe) {
  if (!punkte.length) return '';
  const KOPF = 18, LUFT = 6, ZEILE = 15, DECKEL = 360;
  const ordnung = [], mitglieder = new Map();
  punkte.forEach((pt, i) => {
    const g = String(pt.gruppe || '');
    if (!mitglieder.has(g)) { mitglieder.set(g, []); ordnung.push(g); }
    mitglieder.get(g).push(i);
  });
  const zahlen = punkte.map(p => zahlVon(p.zahl));

  const reihen = [];
  ordnung.forEach((g, nr) => {
    const leute = mitglieder.get(g);
    // Punkte ohne Gruppe stehen ohne Ueberschrift da. Eine erfundene
    // Ueberschrift ("Sonstiges") waere eine Auskunft, die niemand gab.
    if (g) {
      const teile = leute.map(i => zahlen[i]);
      const summe = teile.every(t => t !== null) ? teile.reduce((a, b) => a + b, 0) : null;
      reihen.push({
        art: 'kopf', text: g,
        summe: summe === null ? '' : (summe < -0.005 ? '−' : '') + zahlDeutsch(summe),
        hoehe: KOPF + (nr ? LUFT : 0),
      });
    }
    leute.forEach(i => reihen.push({ art: 'zeile', punkt: i, hoehe: ZEILE }));
  });

  let hoehe = 0, gekappt = false;
  const behalten = [];
  for (const r of reihen) {
    if (hoehe + r.hoehe > DECKEL) { gekappt = true; break; }
    hoehe += r.hoehe; behalten.push(r);
  }
  if (gekappt) {
    // Platz fuer die Marke freiraeumen statt sie anzuhaengen -- und keine
    // Ueberschrift ohne Zeilen stehen lassen: Die sagt nur, dass etwas
    // fehlt, ohne zu zeigen, was.
    while (behalten.length && (hoehe + ZH > DECKEL || behalten[behalten.length - 1].art === 'kopf'))
      hoehe -= behalten.pop().hoehe;
  }

  const groesste = Math.max(0, ...zahlen.filter(z => z !== null && z > 0));
  return behalten.map(r => {
    if (r.art === 'kopf')
      return `<div class="grkopf" style="color:${rgb(farbe, 0.62)};border-color:${rgb(farbe, 0.22)}">`
        + `<span>${sicher(r.text)}</span><span>${sicher(r.summe)}</span></div>`;
    const pt = punkte[r.punkt], z = zahlen[r.punkt];
    const breite = (groesste > 0 && z !== null && z > 0) ? 100 * Math.min(1, z / groesste) : 0;
    return `<div class="zeile ein">`
      + (breite ? `<i class="balken" style="width:${breite}%;background:${rgb(farbe, 1)}"></i>` : '')
      + `<span>${sicher(pt.text)}</span><span>${sicher(pt.wert)}</span></div>`;
  }).join('')
    + (gekappt ? `<div class="marke" style="color:${rgb(farbe, 0.45)}">${MARKE}</div>` : '');
}

// =====================================================================
// 8  fluss -- Sankey: die DICKE eines Bandes ist der Betrag
// =====================================================================
/* HIER LIEGT DIE ACHSE ANDERS ALS DRUEBEN, und das ist die eine grosse
 * Entscheidung dieser Datei.
 *
 * kachel.py legt die Stufen NEBENEINANDER und braucht dafuer Breite:
 * 14 + n*9 Knotenbalken + n*111 Namensspur + (n-1)*72 Schwung. Drei
 * Stufen sind 532 Punkte, fuenf sind 800. Diese Kachel hat 264 (Rechner)
 * bzw. rund 364 (Handy). Rechnet man die Spur auf 264 herunter, bleiben
 * bei drei Stufen 49 Punkte je Spur -- davon gehen 5 Innenabstand und
 * 42 Betragsspalte ab, und fuer den Namen bleibt nichts. Der Ausweg
 * "dann eben ohne Namen" ist keiner: Ein Sankey ohne Knotennamen ist
 * ein Ornament.
 *
 * Also wird die Achse getauscht: Die Stufen liegen UNTEREINANDER, die
 * Baender fliessen nach unten, die Dicke eines Bandes ist seine BREITE.
 * Damit ist die knappe Groesse (Breite) die, ueber die sich alle Knoten
 * EINER Stufe teilen -- und die reichliche (Hoehe) die, in der die
 * Stufen liegen. Genau das ist die Lage in einer schmalen Spalte.
 *
 * Alles andere bleibt, wie es drueben steht, nur um 90 Grad gedreht:
 *
 *   GERADE STRECKE. Die Beschriftung hat ihre eigene Spur -- hier
 *   UNTER dem Knotenbalken statt rechts davon. Dort laufen die
 *   abgehenden Baender dieses einen Knotens noch senkrecht, also auf
 *   genau seiner Breite; fremde Baender koennen nicht hinein, weil die
 *   auf der Breite IHRES Knotens liegen. Unter der Beschriftung liegt
 *   deshalb eine BEKANNTE Farbe, und die Schriftfarbe laesst sich
 *   ausrechnen (schriftAuf) statt raten.
 *
 *   DIE SPUR IST ZWEIZEILIG (Name, darunter der Betrag). Drueben stehen
 *   beide nebeneinander, weil dort die Breite reichlich war. Hier ist
 *   sie es nicht und die Hoehe schon -- also untereinander. Beide
 *   bekommen so die ganze Breite des Knotens statt der Haelfte.
 *
 *   DER ABSTAND ZWEIER KNOTEN ist eine Beschriftung breit (drueben: eine
 *   Textzeile hoch). Das ist es, was die Namen duenner Baender rettet:
 *   Zwei Knoten liegen immer so weit auseinander, dass ihre Namen sich
 *   nicht ueberlappen koennen, egal wie duenn sie sind.
 *
 *   DER MASSSTAB ist der KLEINSTE, den irgendeine Stufe vertraegt. Einer
 *   je Stufe waere bequemer und eine Luege: Dann waere ein Band unten
 *   dicker als sein eigener Zufluss oben.
 *
 *   UNGLEICHE SUMMEN sind der Normalfall: Von 3.400 Euro gehen 1.098
 *   nach Wohnen, der Rest ist nicht aufgeschluesselt. Der Knoten ist so
 *   breit wie das GROESSERE von Ein- und Ausgang; was nicht
 *   weitergereicht wird, bleibt als unbebaenderter Balkenrest stehen.
 */
function formFluss(punkte, farbe, W, m) {
  const BAR = 9, SPALTEN_MAX = 5, BOGEN = 42, STRICH = 0.8;
  const SPUR = 2 * ZH;                       // Name + Betrag
  const marken = [];
  if (Number(m.weggelassen)) marken.push('[… zu viele Punkte, gekürzt]');

  // --- 1. Was ist ueberhaupt eine Kante?
  let kanten = [], unklar = false;
  punkte.forEach(pt => {
    const von = String(pt.von || '').trim(), nach = String(pt.nach || '').trim();
    const z = zahlVon(pt.zahl);
    // Die Dicke IST der Betrag, und ein negativer Betrag hat keine Dicke.
    if (!von || !nach || von === nach || z === null || z <= 0) { unklar = true; return; }
    kanten.push({ von, nach, wert: z });
  });
  if (unklar) marken.push(MARKE_KANTEN);
  if (!kanten.length) return markenZeilen(marken, farbe);

  // --- 2. Knoten in der Reihenfolge des ersten Auftretens
  let namen = [];
  kanten.forEach(k => [k.von, k.nach].forEach(nm => { if (!namen.includes(nm)) namen.push(nm); }));

  // --- 3. Stufen, Kreise auftrennen
  const [rang, getrennt] = raenge(namen, kanten.map(k => [k.von, k.nach]));
  if (getrennt.size) {
    marken.push(MARKE_KREIS);
    kanten = kanten.filter((k, nr) => !getrennt.has(nr));
  }
  // --- 4. Zu tief? Dann faellt der Rest weg, aber nicht stumm.
  if (namen.some(nm => rang.get(nm) >= SPALTEN_MAX)) {
    marken.push(MARKE_TIEF);
    namen = namen.filter(nm => rang.get(nm) < SPALTEN_MAX);
    const bleibt = new Set(namen);
    kanten = kanten.filter(k => bleibt.has(k.von) && bleibt.has(k.nach));
  }
  if (!kanten.length || !namen.length) return markenZeilen(marken, farbe);

  const tiefe = Math.max(...namen.map(nm => rang.get(nm)));
  const reihen = [];
  for (let r = 0; r <= tiefe; r++) reihen.push([]);
  namen.forEach(nm => reihen[rang.get(nm)].push(nm));

  // --- 5. Reihenfolge der Knoten je Stufe (Schwerpunkt der Nachbarn).
  // Die uebliche Heuristik, vier Durchgaenge hin und zurueck. Mehr als
  // eine Heuristik ist hier nicht zu holen -- das Problem ist NP-schwer.
  const vorher = new Map(namen.map(n => [n, []])), nachher = new Map(namen.map(n => [n, []]));
  kanten.forEach(k => { vorher.get(k.nach).push(k.von); nachher.get(k.von).push(k.nach); });
  const ort = new Map();
  const merken = () => reihen.forEach(r => r.forEach((n, i) => ort.set(n, i)));
  const schwerpunkt = (reihe, nachbarn) => {
    const mitte = n => {
      const w = nachbarn.get(n).filter(x => ort.has(x)).map(x => ort.get(x));
      return w.length ? w.reduce((a, b) => a + b, 0) / w.length : ort.get(n);
    };
    return reihe.map((n, i) => [n, i])
      .sort((a, b) => (mitte(a[0]) - mitte(b[0])) || (a[1] - b[1]))
      .map(x => x[0]);
  };
  merken();
  for (let d = 0; d < 4; d++) {
    for (let c = 1; c < reihen.length; c++) { reihen[c] = schwerpunkt(reihen[c], vorher); merken(); }
    for (let c = reihen.length - 2; c >= 0; c--) { reihen[c] = schwerpunkt(reihen[c], nachher); merken(); }
  }

  // --- 6. Wie breit ist ein Knoten?
  const ein = new Map(namen.map(n => [n, 0])), aus = new Map(namen.map(n => [n, 0]));
  kanten.forEach(k => { aus.set(k.von, aus.get(k.von) + k.wert); ein.set(k.nach, ein.get(k.nach) + k.wert); });
  const durch = new Map(namen.map(n => [n, Math.max(ein.get(n), aus.get(n))]));

  const breiteste = Math.max(...reihen.map(r => r.length));
  // Die Fuge zwischen zwei Knoten soll eine Beschriftung breit sein (44).
  // Bei vielen Knoten in einer Stufe frassen die Fugen sonst die ganze
  // Breite auf -- deshalb bekommen sie hoechstens 55 Prozent davon.
  const fuge = Math.max(10, Math.min(44, (W * 0.55) / Math.max(1, breiteste)));
  // n Fugen, nicht n-1: Auch der LETZTE Knoten einer Stufe braucht rechts
  // von sich eine Fuge, denn dort steht seine Beschriftung. Ohne diese
  // eine Fuge stand der aeusserste Balken buendig am Rand und sein Name
  // gar nicht -- gemessen an "Auto" ganz rechts, das schlicht fehlte.
  const moeglich = reihen
    .filter(r => r.length && r.reduce((s, n) => s + durch.get(n), 0) > 0)
    .map(r => (W - r.length * fuge) / r.reduce((s, n) => s + durch.get(n), 0));
  const massstab = moeglich.length ? Math.max(0, Math.min(...moeglich)) : 0;

  const knoten = [], nummer = new Map();
  reihen.forEach((reihe, r) => {
    const stapel = reihe.reduce((s, n) => s + durch.get(n) * massstab, 0)
      + fuge * Math.max(0, reihe.length - 1);
    // Die Fuge des letzten Knotens zaehlt mit, sonst laege der Stapel
    // um eine halbe Fuge zu weit rechts.
    let x = (W - stapel - fuge) / 2;
    const y = r * (BAR + SPUR + BOGEN);
    reihe.forEach((nm, platz) => {
      const br = durch.get(nm) * massstab;
      nummer.set(nm, knoten.length);
      knoten.push({
        name: nm, platz, anzahl: Math.max(2, reihe.length), x, y,
        breite: br, aus: aus.get(nm) * massstab,
        betrag: zahlDeutsch(durch.get(nm)),
        // Die Spur reicht bis zum naechsten Knoten -- das ist der Sinn
        // der Fuge, und beim letzten der Stufe ist sie durch die
        // Reservierung oben genauso sicher vorhanden.
        spur: br + fuge,
      });
      x += br + fuge;
    });
  });
  const flaeche = reihen.length * (BAR + SPUR + BOGEN) - BOGEN;

  // --- 7. Stapelreihenfolge an jedem Knoten. Keine Heuristik, sondern
  // eine Sortierung -- und sie schliesst Kreuzungen IM Knoten aus:
  // abgehende nach der Lage ihres Ziels, eingehende nach der der Quelle.
  const mitteVon = nm => { const k = knoten[nummer.get(nm)]; return k.x + k.breite / 2; };
  namen.forEach(nm => {
    const k = knoten[nummer.get(nm)];
    let x = k.x;
    kanten.filter(e => e.von === nm).sort((a, b) => mitteVon(a.nach) - mitteVon(b.nach))
      .forEach(e => { e.x0 = x; x += e.wert * massstab; });
    x = k.x;
    kanten.filter(e => e.nach === nm).sort((a, b) => mitteVon(a.von) - mitteVon(b.von))
      .forEach(e => { e.x1 = x; x += e.wert * massstab; });
  });

  // --- 8. Die Baender. Erst gerade durch die Namensspur, dann der Bogen.
  // Ein Band ist halbdurchsichtig, ein Balken nicht: Zwei Baender, die
  // sich kreuzen, muessen als zwei lesbar bleiben -- deckend waere das
  // obere einfach vorn und das untere weg. Der Balken dagegen ist die
  // Marke, an der abgelesen wird, und die darf nicht durchscheinen.
  let s = '';
  kanten.forEach(e => {
    const a = knoten[nummer.get(e.von)], b = knoten[nummer.get(e.nach)];
    const y0 = a.y + BAR, yg = y0 + SPUR, y1 = b.y, ym = (yg + y1) / 2;
    const d = e.wert * massstab;
    const c = rgb(stufe(farbe, a.platz, a.anzahl), 0.38);
    s += `<path d="M${e.x0.toFixed(2)},${y0.toFixed(1)} L${e.x0.toFixed(2)},${yg.toFixed(1)}`
      + ` C${e.x0.toFixed(2)},${ym.toFixed(1)} ${e.x1.toFixed(2)},${ym.toFixed(1)} ${e.x1.toFixed(2)},${y1.toFixed(1)}`
      + ` L${(e.x1 + d).toFixed(2)},${y1.toFixed(1)}`
      + ` C${(e.x1 + d).toFixed(2)},${ym.toFixed(1)} ${(e.x0 + d).toFixed(2)},${ym.toFixed(1)} ${(e.x0 + d).toFixed(2)},${yg.toFixed(1)}`
      + ` L${(e.x0 + d).toFixed(2)},${y0.toFixed(1)} Z" fill="${c}"/>`;
  });

  knoten.forEach(k => {
    s += `<rect x="${k.x.toFixed(2)}" y="${k.y.toFixed(1)}" width="${Math.max(k.breite, STRICH).toFixed(2)}" height="${BAR}"`
      + ` fill="${rgb(stufe(farbe, k.platz, k.anzahl), 0.95)}"/>`;
    // Was liegt unter dieser Zeile? Die abgehenden Baender fuellen den
    // Knoten von links auf k.aus Punkte auf -- deckt das mehr als die
    // halbe Spur, ist der Bandton der Grund, sonst der Kachelgrund.
    // Gemessen wird die wirkliche Ueberlappung und nicht "hat der Knoten
    // Ausgaenge": Ein Knoten, der 1.098 aufnimmt und 820 weitergibt, hat
    // unter dem Anfang seiner Zeile noch Band, unter dem Ende nicht mehr.
    const ueber = Math.max(0, Math.min(k.spur, k.aus));
    const grund = ueber >= k.spur / 2
      ? ueberGrund(stufe(farbe, k.platz, k.anzahl), 0.38) : GRUND;
    const tinte = rgb(schriftAuf(grund, TINTE), 1);
    s += svgText(k.x + 2, k.y + BAR + ZH / 2, kuerzen(k.name, k.spur - 4), tinte);
    s += svgText(k.x + 2, k.y + BAR + ZH + ZH / 2, k.betrag, tinte, { gross: 9 });
  });

  const H = flaeche;
  return `<svg class="bild" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${s}</svg>`
    + markenZeilen(marken, farbe);
}

// =====================================================================
// 9  ablauf -- Kaesten und Pfeile, ein Weg durch Schritte
// =====================================================================
/* Ein Punkt ist ein KASTEN, kein Pfeil: Leuchten soll der Kasten, und
 * die gerade Kette ist der Regelfall -- steht "von" nicht da, ist der
 * vorige Punkt gemeint. Nennt "von" einen Namen, den es nicht gibt, gilt
 * ebenfalls der vorige: Ein Kasten ohne Vorgaenger stuende als zweiter
 * Anfang daneben, und ein Ablauf mit zwei Anfaengen sieht kaputt aus,
 * obwohl nur ein Name falsch geschrieben war.
 *
 * WAS HIER DAZUKOMMT: DER UMBRUCH EINER STUFE.
 * Drueben duerfen vier Kaesten nebeneinander stehen, dafuer ist das
 * Fenster 708 breit. Hier sind 264 da. Ein Kasten unter rund 78 Punkten
 * traegt keine zwei lesbaren Zeilen mehr ("Ergebnis geprüft" waere
 * "Erge…"), und Kaesten wegzulassen ist keine Option -- ein Ablauf, dem
 * der vierte Zweig fehlt, ist ein anderer Ablauf.
 *
 * Also bricht eine zu breite Stufe UM: Ihre Kaesten laufen wie Text in
 * eine zweite Reihe. Der Rang bleibt derselbe -- es sind weiterhin die
 * Zweige EINER Verzweigung --, nur die Zeile ist eine andere. Die
 * Pfeile brauchen dafuer nichts Neues: Die Regel "geht der Pfeil ueber
 * mehr als eine Zeile, laeuft er durch die Gasse am Rand" trifft die
 * umgebrochenen von selbst, und damit geht keiner durch einen Kasten. */
function formAblauf(punkte, farbe, W, m) {
  if (!punkte.length) return '';
  const KASTEN_MAX = 150, KASTEN_MIN = 78, LUFT_MAX = 22, LUFT_MIN = 8;
  const RAND_K = 5, ECKE = 5, PFEIL = 24, GASSE = 14, KOPF = 3.2;
  const ZEILEN_MAX = 2, DECKEL = 470;
  const marken = [];
  if (Number(m.weggelassen)) marken.push('[… zu viele Punkte, gekürzt]');
  const n = punkte.length;

  // Namen -> ERSTER Punkt mit diesem Namen. Wer zweimal "fertig"
  // schickt, meint beim Verweisen das erste.
  const wo = new Map();
  punkte.forEach((pt, i) => {
    const t = String(pt.text || '').trim();
    if (t && !wo.has(t)) wo.set(t, i);
  });
  const kanten = [], aufschrift = new Map();
  punkte.forEach((pt, i) => {
    const v = String(pt.von || '').trim();
    const eltern = wo.has(v) ? wo.get(v) : (i ? i - 1 : null);
    if (eltern !== null && eltern !== i) {
      kanten.push([eltern, i]);
      if (pt.wert) aufschrift.set(eltern + '>' + i, String(pt.wert));
    }
  });
  // "nach" ist eine ZUSAETZLICHE Kante: darueber laufen Zweige wieder
  // zusammen. Beide zusammen gehen durch raenge(), und deshalb rutscht
  // ein Kasten, in den zwei Zweige muenden, von selbst unter den
  // tieferen der beiden -- sonst zeigte einer der Pfeile zur Seite.
  punkte.forEach((pt, i) => {
    const ziel = wo.get(String(pt.nach || '').trim());
    if (ziel !== undefined && ziel !== i && !kanten.some(k => k[0] === i && k[1] === ziel))
      kanten.push([i, ziel]);
  });

  const alle = Array.from({ length: n }, (_, i) => i);
  const [rang, getrennt] = raenge(alle, kanten);
  let kanten2 = kanten.filter((k, nr) => !getrennt.has(nr));
  if (getrennt.size) marken.push(MARKE_KREIS);

  const tiefe = Math.max(...alle.map(i => rang.get(i)));
  const stufen = [];
  for (let r = 0; r <= tiefe; r++) stufen.push([]);
  alle.forEach(i => stufen[rang.get(i)].push(i));

  // --- Zeilen: eine Stufe kann umbrechen. Zwei Durchgaenge, weil die
  // Gasse erst noetig ist, wenn ein Pfeil eine Zeile ueberspringt --
  // und das haengt am Umbruch. Mehr als zwei braucht es nicht: Weniger
  // Kaesten je Zeile koennen die Zahl der Spruenge nur erhoehen, und
  // die Gasse kostet danach keine weitere Breite.
  let gasse = 0, zeilen = [], zeileVon = new Map(), kastenBreit = 0, luft = 0;
  for (let durchgang = 0; durchgang < 2; durchgang++) {
    const zone = W - gasse;
    const proZeile = Math.max(1, Math.floor((zone + LUFT_MIN) / (KASTEN_MIN + LUFT_MIN)));
    zeilen = [];
    stufen.forEach(stufe0 => {
      const teile = Math.ceil(stufe0.length / proZeile);
      const jeZeile = Math.ceil(stufe0.length / teile);   // gleichmaessig, nicht 3+1
      for (let i = 0; i < stufe0.length; i += jeZeile) zeilen.push(stufe0.slice(i, i + jeZeile));
    });
    zeileVon = new Map();
    zeilen.forEach((z, nr) => z.forEach(i => zeileVon.set(i, nr)));
    const breiteste = Math.max(...zeilen.map(z => z.length));
    luft = Math.min(LUFT_MAX, zone / (2 * breiteste));
    kastenBreit = Math.min(KASTEN_MAX, (zone - (breiteste - 1) * luft) / breiteste);
    const braucht = kanten2.some(([a, b]) => zeileVon.get(b) - zeileVon.get(a) > 1) ? GASSE : 0;
    if (braucht === gasse) break;
    gasse = braucht;
  }

  /* WIE VIELE PFEILE VERLASSEN EINE ZEILE DURCH DIE GASSE?
     Die Frage muss VOR dem Layout beantwortet sein, denn sie kostet
     Hoehe: Zwei Gassenpfeile aus derselben Zeile brauchen zwei
     Querstuecke uebereinander, und jedes traegt eine Aufschrift.
     Beide in die 24 Punkte zwischen zwei Zeilen zu zwaengen ging nicht
     -- gemessen lag "WRT" halb auf "NOT". Also bekommt die Luecke fuer
     jeden weiteren Gassenpfeil eine Zeilenhoehe dazu. */
  const gassenSpur = new Map(), gassenZahl = new Map();
  kanten2.forEach(([a, b]) => {
    if (zeileVon.get(b) - zeileVon.get(a) <= 1) return;
    const r = zeileVon.get(a), k = gassenZahl.get(r) || 0;
    gassenSpur.set(a + '>' + b, k);
    gassenZahl.set(r, k + 1);
  });
  const zusatz = r => 13 * Math.min(2, Math.max(0, (gassenZahl.get(r) || 0) - 1));

  const innen = Math.max(1, kastenBreit - 2 * RAND_K);
  const texte = punkte.map(pt => {
    let u = umbrechen(pt.text, innen);
    if (!u.length) u = [''];
    if (u.length > ZEILEN_MAX)
      u = u.slice(0, ZEILEN_MAX - 1).concat([kuerzen(u.slice(ZEILEN_MAX - 1).join(' '), innen)]);
    return u;
  });

  // --- Lage der Kaesten, von oben nach unten
  const lage = new Map();
  let y = 0, gekappt = false;
  const zone = W - gasse;
  zeilen.forEach((reihe, r) => {
    if (gekappt) return;
    const hoch = Math.max(...reihe.map(i => texte[i].length)) * ZH + 2 * RAND_K;
    const luecke = PFEIL + (r ? zusatz(r - 1) : 0);
    if (r && y + luecke + hoch > DECKEL) { gekappt = true; return; }
    if (r) y += luecke;
    const gesamt = reihe.length * kastenBreit + (reihe.length - 1) * luft;
    let x = (zone - gesamt) / 2;
    reihe.forEach(i => { lage.set(i, { x, y, b: kastenBreit, h: hoch }); x += kastenBreit + luft; });
    y += hoch;
  });
  // Gekappt wird UNTEN. Beim Ablauf ist das der schlechtere Schnitt (das
  // Ende ist das Ziel), aber der einzige, der nicht luegt: Oben zu kappen
  // hiesse, einen Weg ohne Anfang zu zeigen.
  if (gekappt) marken.push(MARKE);

  // --- Pfeile zuerst, Kaesten darueber: Die Spitze endet auf der
  // Oberkante ihres Kastens, und der deckt sie nicht zu, sondern
  // schliesst an sie an.
  let s = '', beschriftung = '';
  kanten2.forEach(([a, b]) => {
    if (!lage.has(a) || !lage.has(b)) return;
    const o = lage.get(a), u = lage.get(b);
    const sx = o.x + o.b / 2, sy = o.y + o.h;
    const tx = u.x + u.b / 2, ty = u.y;
    const strich = rgb(farbe, 0.55);
    let ecken, sch, anker;
    const neben = h => ({ x: sx + 4, y: h + ZF / 2, w: Math.min(kastenBreit / 2, W - sx - 4) });
    if (zeileVon.get(b) - zeileVon.get(a) > 1) {
      // Ueber die Gasse aussen herum -- ohne sie waere das genau der
      // Fehler, den man bei jedem vierten Graphen sieht: ein Pfeil, der
      // durch einen Kasten geht. Zwei Spuren nebeneinander reichen.
      const nr = gassenSpur.get(a + '>' + b) || 0;
      const gx = W - 5 - (nr % 2) * 6;
      // Auch das Querstueck wird gestaffelt, nicht nur die senkrechte
      // Spur: Zwei Pfeile aus DEMSELBEN Kasten verlassen ihn auf
      // derselben Hoehe, und dann laege Strich auf Strich. Der Platz
      // dafuer steht schon im Layout, siehe zusatz().
      const quer0 = sy + 6 + Math.min(2, nr) * 13;
      ecken = [[sx, sy], [sx, quer0], [gx, quer0], [gx, ty - 8], [tx, ty - 8], [tx, ty]];
      // Die Aufschrift sitzt UNTER ihrem eigenen Querstueck und am
      // Ende, kurz vor der Gasse -- nicht neben dem Kasten: Dort
      // haetten zwei Pfeile aus demselben Kasten denselben Ort.
      sch = { x: gx - 4, y: quer0 + ZF / 2 + 1, w: Math.max(20, gx - sx - 8) };
      anker = 'end';
    } else if (Math.abs(sx - tx) < 0.6) {
      ecken = [[sx, sy], [tx, ty]];
      // Auf derselben Hoehe wie die Beschriftung der geknickten
      // Geschwister, naemlich unter deren Querstrich: Ein Kasten mit
      // drei Ausgaengen hat einen geraden Pfeil in der Mitte und zwei
      // geknickte daneben -- stuende sein Wort weiter oben, laege es
      // genau auf dem Querstrich der beiden anderen.
      sch = neben(sy + PFEIL / 2 + 1); anker = 'start';
    } else {
      const quer = sy + PFEIL / 2;
      ecken = [[sx, sy], [sx, quer], [tx, quer], [tx, ty]];
      // UNTER dem Querstueck, nicht darueber: Darueber stiesse sie an
      // die Unterkante des Kastens, aus dem der Pfeil kommt.
      sch = { x: (sx + tx) / 2, y: quer + 1 + ZF / 2, w: Math.abs(tx - sx) };
      anker = 'middle';
    }
    s += `<polyline points="${ecken.map(e => e[0].toFixed(1) + ',' + e[1].toFixed(1)).join(' ')}"`
      + ` fill="none" stroke="${strich}" stroke-width="1"/>`;
    s += `<polygon points="${(tx - KOPF).toFixed(1)},${(ty - 5).toFixed(1)} ${(tx + KOPF).toFixed(1)},${(ty - 5).toFixed(1)} ${tx.toFixed(1)},${ty.toFixed(1)}" fill="${strich}"/>`;
    const wort = aufschrift.get(a + '>' + b);
    if (wort) beschriftung += svgText(sch.x, sch.y, kuerzen(wort, sch.w, SCHRIFT_FUSS),
      rgb(farbe, 0.72), { gross: 9, anker });
  });
  s += beschriftung;

  Array.from(lage.keys()).sort((a, b) => a - b).forEach(i => {
    const k = lage.get(i);
    s += `<rect x="${(k.x + 0.5).toFixed(1)}" y="${(k.y + 0.5).toFixed(1)}" width="${(k.b - 1).toFixed(1)}" height="${(k.h - 1).toFixed(1)}"`
      + ` rx="${ECKE}" fill="${rgb(farbe, 0.12)}" stroke="${rgb(farbe, 0.50)}" stroke-width="1"/>`;
    texte[i].forEach((z, nr) => {
      s += svgText(k.x + k.b / 2, k.y + RAND_K + nr * ZH + ZH / 2, z,
        rgb(TINTE, 0.92), { anker: 'middle' });
    });
  });

  const H = Math.max(1, y);
  return `<svg class="bild" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${s}</svg>`
    + markenZeilen(marken, farbe);
}

// =====================================================================
// Die Kachel selbst
// =====================================================================
const FORMEN = {
  liste: formListe, blasen: formBlasen, vergleich: formVergleich,
  text: formText, balken: formBalken, torte: formTorte,
  kategorien: formKategorien, fluss: formFluss, ablauf: formAblauf,
};

function kachelZeigen(m) {
  const farbe = m.sorte === 'zustand' ? KACHEL_ZUSTAND : KACHEL_ANTWORT;
  let el = S.kacheln.get(m.name);
  if (!el) {
    el = document.createElement('div');
    el.className = 'kachel';
    kachelraum.appendChild(el);
    S.kacheln.set(m.name, el);
  }
  el.style.borderColor = rgb(farbe, 0.30);
  const punkte = m.punkte || [];

  // Die WIRKLICH vorhandene Innenbreite, nicht eine geratene: Am Rechner
  // rund 264, auf dem Handy rund 364. Die gerechneten Formen legen ihr
  // Inneres darin aus -- siehe den Kopf dieses Abschnitts. Der leere
  // Kasten steht schon im Baum, also hat er seine Breite; nur beim
  // allerersten Bild vor dem ersten Layout ist sie 0, dafuer der Notnagel.
  const breite = Math.max(180, (el.clientWidth || Math.min(290, kachelraum.clientWidth || 290)) - 24);

  // Etwas Unbekanntes faellt auf "liste" zurueck: Eine Kachel, die wegen
  // eines Tippfehlers gar nicht aufgeht, ist schlechter als eine, die
  // schlicht aussieht.
  const bauen = FORMEN[m.form] || formListe;
  let rumpf = '';
  try {
    rumpf = bauen(punkte, farbe, breite, m);
  } catch (e) {
    // Lieber schlicht als gar nicht -- aus demselben Grund wie oben.
    rumpf = formListe(punkte, farbe, breite, m);
    if (window.console) console.warn('Kachelform', m.form, e);
  }

  const weg = Number(m.weggelassen) || 0;
  el.innerHTML = `<div class="strich" style="background:${rgb(farbe, 0.85)}"></div>
    <h4 style="color:${rgb(farbe, 0.95)}">${sicher(m.kopf)}</h4>
    ${m.gross ? `<div class="gross" style="color:${rgb(farbe, 1)}">${sicher(m.gross)}</div>` : ''}
    ${rumpf}
    ${weg ? `<div class="fuss">und ${weg} weitere</div>` : ''}
    ${m.stand ? `<div class="fuss">${sicher(m.stand)}</div>` : ''}`;

  const sek = Number(m.sekunden) || (m.sorte === 'zustand' ? 0 : 45);
  clearTimeout(el._uhr);
  if (sek > 0) el._uhr = setTimeout(() => kachelWeg(m.name), sek * 1000);
}

function kachelWeg(name) {
  const el = S.kacheln.get(name);
  if (!el) return;
  clearTimeout(el._uhr);
  el.style.transition = 'opacity .35s'; el.style.opacity = '0';
  setTimeout(() => el.remove(), 360);
  S.kacheln.delete(name);
}

const sicher = t => String(t == null ? '' : t)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

function hintergrundZeigen() {
  const kasten = document.getElementById('hintergrund');
  if (!S.hintergrund.length && !S.hgFertig) { kasten.classList.remove('an'); return; }
  kasten.classList.add('an');
  // Die WIRKLICHE Zahl, nicht die der angezeigten Zeilen.
  const gesamt = Math.max(S.hgGesamt, S.hintergrund.length);
  const farbe = S.hgFertig ? [120, 226, 140]
    : (S.hgSeit < 90 ? [255, 104, 104] : [255, 176, 72]);
  kasten.style.color = rgb(farbe, 0.95);
  kasten.innerHTML = `<div class="kopf">im Hintergrund${gesamt > 1 ? ' · ' + gesamt : ''}</div>`
    + S.hintergrund.slice(0, 3).map(z => `<div class="zeile">${sicher(z)}</div>`).join('');
}

// =====================================================================
// Die Leitung
// =====================================================================
let draht = null, schluessel = localStorage.getItem('sarvis-schluessel') || '';
let wiederIn = 1000;

function lage(text, an) {
  document.getElementById('lage').textContent = text;
  document.getElementById('ampel').classList.toggle('an', !!an);
  document.getElementById('reden').disabled = !an;
  S.verbunden = !!an;
}

function verbinden() {
  const wo = (location.protocol === 'https:' ? 'wss://' : 'ws://')
    + location.host + '/draht';
  lage('verbindet …', false);
  draht = new WebSocket(wo);

  draht.onopen = () => draht.send(JSON.stringify({
    schluessel,
    // Nur ein Geraet mit grossem Bildschirm bekommt Browser-Fragen.
    kann_browser: window.innerWidth >= 900,
  }));

  draht.onmessage = e => {
    let m; try { m = JSON.parse(e.data); } catch { return; }
    empfangen(m);
  };

  draht.onclose = ev => {
    if (ev.code === 4401) {          // Schlüssel gilt nicht
      localStorage.removeItem('sarvis-schluessel');
      document.getElementById('torhinweis').textContent =
        'Dieser Schlüssel gilt nicht. Leg auf dem Server ein Gerät an.';
      document.getElementById('tor').classList.remove('weg');
      lage('kein Zugang', false);
      return;
    }
    lage('getrennt', false);
    setTimeout(verbinden, wiederIn);
    wiederIn = Math.min(wiederIn * 1.6, 20000);   // nicht im Kreis hämmern
  };
}

function empfangen(m) {
  switch (m.art) {
    case 'willkommen':
      wiederIn = 1000;
      lage('verbunden', true);
      document.getElementById('geraet').textContent = m.geraet || '';
      document.getElementById('tor').classList.add('weg');
      localStorage.setItem('sarvis-schluessel', schluessel);
      break;
    case 'zustand':
      if (m.strom) break;            // gehört einem Vorgang, nicht dem Ring
      if (m.zustand !== S.zustand) {
        S.zustand = m.zustand;
        if (m.zustand === 'hoert') {
          S.verlauf.fill(0);
          S.untertitel = ''; zeigeUntertitel();
        }
      }
      break;
    case 'pegel':
      // Solange wir selbst aufnehmen, gilt UNSER Pegel. Der Server
      // kennt ihn nicht -- das Mikrofon steht hier. Ohne diese
      // Bedingung überschreibt eine Meldung von dort den Ausschlag,
      // und der Ring steht still, während man redet.
      if (!nimmtAuf) S.pegel = Math.max(0, Math.min(1, Number(m.pegel) || 0));
      break;
    case 'untertitel':
      if (m.strom) break;
      S.untertitel = m.text || ''; S.wer = m.wer || 'sarvis'; S.hervor = 4;
      zeigeUntertitel();
      break;
    case 'nachhoeren':
      S.nachhoeren = Number(m.sekunden) || 0;
      S.nachhoerenGanz = Math.max(0.1, S.nachhoeren);
      break;
    case 'werkzeug':
      if (m.aktiv) S.glut.set(m.name, 1.0);
      break;
    case 'hintergrund':
      S.hintergrund = m.zeilen || [];
      S.hgGesamt = Number(m.gesamt) || S.hintergrund.length;
      S.hgSeit = Number(m.seit) || 0;
      S.hgFertig = !!m.fertig;
      hintergrundZeigen();
      break;
    case 'kachel':     kachelZeigen(m); break;
    case 'kachel_weg': kachelWeg(m.name); break;
    case 'ton':        tonSpielen(m); break;
    case 'ton_stopp':  tonStopp(m.runde); break;
    case 'horchen':
      // Während Sarvis redet oder eine Rückfrage läuft, braucht er den
      // Strom nicht. Ohne dieses Wort sendet die Oberfläche weiter, der
      // Rückstand läuft auf, und am Ende wirft der Deckel echte Sprache
      // weg -- ausgerechnet die, die nach dem Reden kommt.
      horchPause = !m.an;
      break;
  }
}

function zeigeUntertitel() {
  const el = document.getElementById('untertitel');
  el.textContent = S.untertitel;
  el.style.color = S.wer === 'du' ? 'rgba(232,241,253,.94)'
    : rgb(FARBEN[S.zustand] || FARBEN.ruhig, 0.92);
}

function senden(o) {
  if (draht && draht.readyState === 1) draht.send(JSON.stringify(o));
}

// =====================================================================
// Ton: hin und zurück
// =====================================================================
let hoerer = null, quelle = null, knoten = null, gesammelt = [], nimmtAuf = false;

async function aufnahmeStart() {
  if (nimmtAuf) return;
  try {
    if (!hoerer) {
      // 16 kHz direkt anfordern -- dann muss nichts umgetastet werden,
      // und Whisper bekommt genau das, was es erwartet.
      hoerer = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    }
    if (hoerer.state === 'suspended') await hoerer.resume();
    const gewaehlt = localStorage.getItem('sarvis-mikro') || '';
    const strom = await navigator.mediaDevices.getUserMedia({
      audio: {
        ...(gewaehlt ? { deviceId: { exact: gewaehlt } } : {}),
        // Der Echo-Filter auf dem Server vergleicht TEXT, keine Wellen.
        // Was hier nicht unterdrückt wird, hört Sarvis von sich selbst.
        echoCancellation: true, noiseSuppression: true,
        // Aus: Die Weckwort-Schwelle ist ein absoluter Pegel und wird
        // von einer Verstärkungsautomatik wertlos gemacht.
        autoGainControl: false,
      },
    });
    quelle = hoerer.createMediaStreamSource(strom);
    knoten = hoerer.createScriptProcessor(2048, 1, 1);
    gesammelt = [];
    knoten.onaudioprocess = e => {
      const d = e.inputBuffer.getChannelData(0);
      gesammelt.push(new Float32Array(d));
      let summe = 0; for (let i = 0; i < d.length; i++) summe += d[i] * d[i];
      S.pegel = Math.min(1, Math.pow(Math.sqrt(summe / d.length) / 0.14, 0.6));
    };
    quelle.connect(knoten); knoten.connect(hoerer.destination);
    // Wer zu reden anfängt, während Sarvis noch spricht, unterbricht
    // ihn -- und zwar SOFORT hier, ohne auf den Server zu warten. Der
    // schickt sein ton_stopp gleich hinterher; bis das ankommt, hätte
    // man sich sonst selbst zugehört.
    tonStopp(null);
    nimmtAuf = true;
    S.zustand = 'hoert';
    mikrofoneListen();      // jetzt gibt es auch Namen
  } catch (e) {
    lage('kein Mikrofon', S.verbunden);
  }
}

function aufnahmeStop() {
  if (!nimmtAuf) return;
  nimmtAuf = false; S.pegel = 0;
  try { quelle.disconnect(); knoten.disconnect(); } catch {}
  quelle.mediaStream && quelle.mediaStream.getTracks().forEach(t => t.stop());

  const gesamt = gesammelt.reduce((n, a) => n + a.length, 0);
  if (gesamt < 16000 * 0.4) { S.zustand = 'ruhig'; return; }  // zu kurz

  const alles = new Int16Array(gesamt);
  let i = 0, spitze = 0;
  for (const stueck of gesammelt)
    for (let j = 0; j < stueck.length; j++) {
      const w = stueck[j];
      if (Math.abs(w) > spitze) spitze = Math.abs(w);
      alles[i++] = Math.max(-32768, Math.min(32767, w * 32768));
    }
  gesammelt = [];

  /* Es NICHT stillschweigend hinschicken, wenn nichts drin ist.
   *
   * Genau das ist passiert: 60 Sekunden Aufnahme kamen beim Server an,
   * Whisper war nach einer Zehntelsekunde fertig und verstand nichts,
   * und auf dem Bildschirm stand -- gar nichts. Man drückt dann fester
   * und länger, statt nachzusehen, ob das richtige Mikrofon anliegt.
   *
   * Die Schwelle ist bewusst niedrig: 0,01 trennt "gar kein Signal"
   * von "leise gesprochen". Wer bei 0,02 flüstert, soll durchkommen. */
  if (spitze < 0.01) {
    S.zustand = 'ruhig';
    S.wer = 'sarvis'; S.hervor = 4;
    S.untertitel = 'Da kam kein Ton an. Ist das richtige Mikrofon '
      + 'ausgewählt und nicht stummgeschaltet?';
    zeigeUntertitel();
    return;
  }
  senden({ art: 'sprache', rate: 16000, daten: alsBase64(alles.buffer) });
  S.zustand = 'denkt';
  S.untertitel = ''; zeigeUntertitel();
}

function alsBase64(puffer) {
  const b = new Uint8Array(puffer);
  let s = '';
  for (let i = 0; i < b.length; i += 8192)
    s += String.fromCharCode.apply(null, b.subarray(i, i + 8192));
  return btoa(s);
}

let tonZeit = 0, tonRunde = -1;
const laufendeToene = new Set();

/* Sofort still -- der Gegenpart zum Abbruch auf dem Server.
 *
 * Reinreden ist bei Sarvis ausdrücklich erlaubt ("Wer einen Assistenten
 * nicht unterbrechen kann, wartet jedes Mal eine falsche Antwort zu Ende
 * ab"). Lokal genügte dafür ein sd.stop(): Wenn es zurückkehrt, ist es
 * still. Über Netz gibt es diese Garantie nicht -- der Server kann nur
 * ein Kommando absetzen, und was hier schon im AudioContext eingeplant
 * ist, läuft ohne dieses Zutun weiter.
 *
 * Deshalb zweierlei: alle eingeplanten Quellen abbrechen UND die Runde
 * hochsetzen, damit ein Satz, der beim Abbruch schon unterwegs war,
 * beim Eintreffen verworfen wird. */
function tonStopp(runde) {
  if (runde != null) tonRunde = Math.max(tonRunde, runde);
  laufendeToene.forEach(q => { try { q.stop(); } catch {} });
  laufendeToene.clear();
  tonZeit = hoerer ? hoerer.currentTime : 0;
}

function tonSpielen(m) {
  if (!hoerer) hoerer = new (window.AudioContext || window.webkitAudioContext)();
  // Was aus einer alten Runde stammt, ist ungültig -- der Abbruch kann
  // schon unterwegs gewesen sein, als dieser Satz losgeschickt wurde.
  if (m.runde != null && m.runde < tonRunde) return;
  if (m.runde != null) tonRunde = m.runde;
  const roh = atob(m.daten || '');
  const zahlen = new Int16Array(roh.length / 2);
  for (let i = 0; i < zahlen.length; i++)
    zahlen[i] = (roh.charCodeAt(i * 2) | (roh.charCodeAt(i * 2 + 1) << 8)) << 16 >> 16;
  const puffer = hoerer.createBuffer(1, zahlen.length, m.rate || 22050);
  const ziel = puffer.getChannelData(0);
  for (let i = 0; i < zahlen.length; i++) ziel[i] = zahlen[i] / 32768;
  const q = hoerer.createBufferSource();
  q.buffer = puffer; q.connect(hoerer.destination);
  // Nahtlos anhängen, damit zwischen zwei Sätzen keine Lücke entsteht.
  tonZeit = Math.max(tonZeit, hoerer.currentTime);
  q.start(tonZeit); tonZeit += puffer.duration;
  laufendeToene.add(q);
  q.onended = () => laufendeToene.delete(q);
}

// =====================================================================
// Mithören: „Hey Sarvis" ohne Tastendruck
// =====================================================================
/* Das Mikrofon bleibt offen, und was es hört, geht blockweise zum
 * Server. Dort läuft dieselbe Erkennung wie früher lokal: erst der
 * Sprach-Erkenner (billig, auf der CPU), und nur wenn wirklich jemand
 * redet, Whisper.
 *
 * Was hier NICHT passiert, ist die Erkennung selbst. Die Schwellen sind
 * mühsam vermessen (sarvis 1,00 · jarvis 0,83 · service 0,62), und sie
 * gehören an EINE Stelle — nicht in jede Oberfläche einzeln, wo sie
 * dreimal auseinanderlaufen.
 *
 * Gebündelt wird auf etwa eine Viertelsekunde. Einzeln zu senden wären
 * acht Nachrichten je Sekunde, nur für Rahmen-Overhead; länger zu
 * sammeln würde das Weckwort träge machen. */
let horchQuelle = null, horchKnoten = null, horcht = false;
let horchPuffer = [], horchPause = false;
const HORCH_BUENDEL = 4096;   // ≈ 256 ms bei 16 kHz

async function horchenStart() {
  if (horcht) return;
  try {
    if (!hoerer) hoerer = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    if (hoerer.state === 'suspended') await hoerer.resume();
    const gewaehlt = localStorage.getItem('sarvis-mikro') || '';
    const strom = await navigator.mediaDevices.getUserMedia({
      audio: {
        ...(gewaehlt ? { deviceId: { exact: gewaehlt } } : {}),
        echoCancellation: true, noiseSuppression: true, autoGainControl: false,
      },
    });
    horchQuelle = hoerer.createMediaStreamSource(strom);
    horchKnoten = hoerer.createScriptProcessor(2048, 1, 1);
    horchPuffer = [];
    horchKnoten.onaudioprocess = e => {
      // Während des Push-to-talk und während Sarvis redet: nichts
      // schicken. Sonst hört er sich selbst zu, und der Rückstand
      // läuft auf.
      if (nimmtAuf || horchPause) { horchPuffer = []; return; }
      horchPuffer.push(new Float32Array(e.inputBuffer.getChannelData(0)));
      const summe = horchPuffer.reduce((n, a) => n + a.length, 0);
      if (summe < HORCH_BUENDEL) return;
      const alles = new Int16Array(summe);
      let i = 0;
      for (const st of horchPuffer)
        for (let k = 0; k < st.length; k++)
          alles[i++] = Math.max(-32768, Math.min(32767, st[k] * 32768));
      horchPuffer = [];
      senden({ art: 'strom', rate: 16000, daten: alsBase64(alles.buffer) });
    };
    horchQuelle.connect(horchKnoten);
    horchKnoten.connect(hoerer.destination);
    horcht = true;
    document.getElementById('mithoeren').classList.add('laeuft');
    mikrofoneListen();
  } catch (e) {
    document.getElementById('horchen').checked = false;
    lage('Mikrofon abgelehnt', S.verbunden);
  }
}

function horchenStop() {
  if (!horcht) return;
  horcht = false; horchPuffer = [];
  try {
    horchQuelle.disconnect(); horchKnoten.disconnect();
    horchQuelle.mediaStream.getTracks().forEach(t => t.stop());
  } catch {}
  document.getElementById('mithoeren').classList.remove('laeuft');
}

document.getElementById('horchen').addEventListener('change', e => {
  localStorage.setItem('sarvis-horchen', e.target.checked ? '1' : '');
  e.target.checked ? horchenStart() : horchenStop();
});

// =====================================================================
// Bedienung
// =====================================================================
const reden = document.getElementById('reden');
['pointerdown'].forEach(e => reden.addEventListener(e, ev => {
  ev.preventDefault(); reden.classList.add('haelt');
  reden.setPointerCapture && reden.setPointerCapture(ev.pointerId);
  aufnahmeStart();
}));
['pointerup', 'pointercancel', 'pointerleave'].forEach(e =>
  reden.addEventListener(e, () => {
    reden.classList.remove('haelt'); aufnahmeStop();
  }));

// Am Rechner tut die Leertaste dasselbe wie die Fläche.
document.addEventListener('keydown', e => {
  if (e.code === 'Space' && !e.repeat && document.activeElement.tagName !== 'INPUT') {
    e.preventDefault(); reden.classList.add('haelt'); aufnahmeStart();
  }
});
document.addEventListener('keyup', e => {
  if (e.code === 'Space' && document.activeElement.tagName !== 'INPUT') {
    reden.classList.remove('haelt'); aufnahmeStop();
  }
});

document.getElementById('tippen').addEventListener('submit', e => {
  e.preventDefault();
  const feld = document.getElementById('zeile');
  const text = feld.value.trim();
  if (!text) return;
  senden({ art: 'zuruf', text });
  S.untertitel = text; S.wer = 'du'; S.hervor = 4; zeigeUntertitel();
  feld.value = '';
});

document.getElementById('anmelden').addEventListener('click', () => {
  schluessel = document.getElementById('schluessel').value.trim();
  if (!schluessel) return;
  document.getElementById('torhinweis').textContent = 'verbindet …';
  if (draht) draht.close();
  verbinden();
});
document.getElementById('schluessel').addEventListener('keydown', e => {
  if (e.key === 'Enter') document.getElementById('anmelden').click();
});

/* Welche Mikrofone es gibt.
 *
 * Die Namen bekommt man erst NACH der ersten Erlaubnis -- vorher liefert
 * der Browser leere Beschriftungen, aus Sorge, dass eine Seite Geräte
 * zum Wiedererkennen benutzt. Deshalb wird die Liste nach der ersten
 * Aufnahme noch einmal geholt. */
async function mikrofoneListen() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
  let geraete;
  try { geraete = await navigator.mediaDevices.enumerateDevices(); }
  catch { return; }
  const mikros = geraete.filter(g => g.kind === 'audioinput');
  const feld = document.getElementById('mikro');
  if (mikros.length < 2) { feld.classList.remove('zeigen'); return; }
  const gewaehlt = localStorage.getItem('sarvis-mikro') || '';
  feld.innerHTML = '<option value="">Mikrofon: Standard</option>'
    + mikros.map((m, i) =>
        `<option value="${m.deviceId}"${m.deviceId === gewaehlt ? ' selected' : ''}>`
        + `${sicher(m.label || 'Mikrofon ' + (i + 1))}</option>`).join('');
  feld.classList.add('zeigen');
}

document.getElementById('mikro').addEventListener('change', e => {
  localStorage.setItem('sarvis-mikro', e.target.value);
  // Den alten Strom fallen lassen, damit die neue Wahl beim nächsten
  // Drücken wirklich greift.
  if (hoerer) { try { hoerer.close(); } catch {} hoerer = null; }
});

// --- Los --------------------------------------------------------------
messen();
mikrofoneListen();
if (localStorage.getItem('sarvis-horchen')) {
  document.getElementById('horchen').checked = true;
  // Erst nach der Verbindung -- ohne Draht ginge das Senden ins Leere.
  setTimeout(() => { if (S.verbunden) horchenStart(); }, 1500);
}
requestAnimationFrame(schlag);
if (schluessel) { document.getElementById('tor').classList.add('weg'); verbinden(); }
if ('serviceWorker' in navigator)
  navigator.serviceWorker.register('/dabei/waechter.js').catch(() => {});
