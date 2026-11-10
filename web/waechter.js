/* Der Service Worker. Drei Aufgaben, und mehr soll es nicht werden:
 *
 * 1. Sarvis laesst sich auf den Startbildschirm legen und zeigt ohne Netz
 *    wenigstens eine Oberflaeche statt einer Fehlerseite.
 * 2. "Teilen -> Sarvis" aus dem Android-Menue (seit 10.11.2026): Der POST
 *    auf /teilen wird HIER abgefangen. Der Worker kennt den
 *    Geraeteschluessel nicht (der liegt im localStorage der Seite), also
 *    legt er die Dateien in einen eigenen Zwischenspeicher und schickt
 *    die Seite hin, die sie mit Schluessel hochlaedt.
 * 3. Nichts sonst. Bewusst OHNE Zwischenspeicher fuer Draht, Dateiliste
 *    und Downloads: Ein Assistent, der gespeicherte Antworten zeigt, waere
 *    schlimmer als einer, der sagt, dass er nicht erreichbar ist -- und ein
 *    100-MB-Download hat im Cache nichts verloren. (Bis 10.11. landete
 *    JEDE erfolgreiche GET-Antwort im Cache, auch /blatt/-Downloads.)
 *
 * Wird an der WURZEL ausgeliefert (/waechter.js, netz/server.py). Unter
 * /dabei/ galt er nur fuer /dabei/ und haette /teilen nie gesehen.
 */
const LAGER = 'sarvis-2';
const HUELLE = ['/', '/dabei/sarvis.js', '/dabei/manifest.json', '/dabei/symbol.svg'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(LAGER).then(c => c.addAll(HUELLE)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(n => Promise.all(n.filter(x => x !== LAGER && x !== 'sarvis-teilen')
                             .map(x => caches.delete(x))))
    .then(() => self.clients.claim()));
});

async function geteilt(anfrage) {
  try {
    const form = await anfrage.formData();
    const lager = await caches.open('sarvis-teilen');
    const stempel = Date.now();
    let i = 0;
    for (const f of form.getAll('dateien')) {
      if (!f || typeof f === 'string') continue;
      await lager.put(`/teilen/${stempel}-${i++}`, new Response(f, { headers: {
        'Content-Type': f.type || 'application/octet-stream',
        'X-Name': encodeURIComponent(f.name || 'geteilt'),
      } }));
    }
    const text = ['title', 'text', 'url'].map(k => form.get(k))
      .filter(x => x && typeof x === 'string').join('\n').trim();
    if (text) {
      await lager.put(`/teilen/${stempel}-text`,
                      new Response(text, { headers: { 'X-Text': '1' } }));
    }
    return Response.redirect('/?geteilt=1', 303);
  } catch (err) {
    return Response.redirect('/?geteilt=verpasst', 303);
  }
}

self.addEventListener('fetch', e => {
  const wo = new URL(e.request.url);
  if (wo.origin !== self.location.origin) return;
  if (e.request.method === 'POST' && wo.pathname === '/teilen') {
    e.respondWith(geteilt(e.request));
    return;
  }
  if (e.request.method !== 'GET' || !HUELLE.includes(wo.pathname)) return;
  // Erst das Netz, der Zwischenspeicher nur als Rueckfall: Sonst sieht
  // man nach einem Deploy tagelang die alte Oberflaeche.
  e.respondWith(
    fetch(e.request).then(a => {
      if (a.ok) { const k = a.clone(); caches.open(LAGER).then(c => c.put(e.request, k)); }
      return a;
    }).catch(() => caches.match(e.request))
  );
});
