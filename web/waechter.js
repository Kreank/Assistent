/* Nur so viel Service Worker, wie noetig ist, damit sich Sarvis auf den
 * Startbildschirm legen laesst und ohne Netz wenigstens eine Oberflaeche
 * zeigt statt einer Fehlerseite.
 *
 * Bewusst OHNE Zwischenspeicher fuer den Draht: Ein Assistent, der
 * gespeicherte Antworten zeigt, waere schlimmer als einer, der sagt,
 * dass er gerade nicht erreichbar ist.
 */
const LAGER = 'sarvis-1';
const HUELLE = ['/', '/dabei/sarvis.js', '/dabei/manifest.json', '/dabei/symbol.svg'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(LAGER).then(c => c.addAll(HUELLE)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(n => Promise.all(n.filter(x => x !== LAGER).map(x => caches.delete(x))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  // Erst das Netz, der Zwischenspeicher nur als Rueckfall: Sonst sieht
  // man nach einem Deploy tagelang die alte Oberflaeche.
  e.respondWith(
    fetch(e.request).then(a => {
      if (a.ok) { const k = a.clone(); caches.open(LAGER).then(c => c.put(e.request, k)); }
      return a;
    }).catch(() => caches.match(e.request))
  );
});
