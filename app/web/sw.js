/* Service worker : l'app doit s'ouvrir et rester utilisable sans réseau.

   Deux régimes selon ce qu'on demande :
   - la coquille (HTML, CSS, JS, icônes) et index.json : le réseau d'abord, le
     cache si ça ne répond pas ;
   - les photos Vinted : le cache d'abord, plafonné pour ne pas saturer.

   La coquille a d'abord été servie par le cache, avec mise à jour en fond :
   c'est plus rapide, mais on voyait alors la version précédente au premier
   chargement suivant une publication, et la nouvelle seulement au second. Pour
   trente kilo-octets, la fraîcheur vaut mieux que les quelques millisecondes
   gagnées. Hors réseau, le cache prend le relais comme avant. */

// À changer quand la stratégie de cache change : l'activation vide alors les
// caches des versions précédentes.
const VERSION = 'dressing-v2';
const COQUILLE = `${VERSION}-coquille`;
const DONNEES = `${VERSION}-donnees`;
const PHOTOS = `${VERSION}-photos`;
const PLAFOND_PHOTOS = 700;

const FICHIERS = [
  './',
  './index.html',
  './app.css',
  './app.js',
  './manifest.webmanifest',
  './icone-180.png',
  './icone-192.png',
  './icone-512.png',
];

self.addEventListener('install', (evenement) => {
  evenement.waitUntil(
    caches.open(COQUILLE)
      .then((cache) => cache.addAll(FICHIERS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (evenement) => {
  evenement.waitUntil(
    caches.keys()
      .then((noms) => Promise.all(
        noms.filter((nom) => !nom.startsWith(VERSION))
            .map((nom) => caches.delete(nom))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (evenement) => {
  const requete = evenement.request;
  if (requete.method !== 'GET') return;

  const url = new URL(requete.url);

  if (url.origin === self.location.origin) {
    const cache = url.pathname.endsWith('index.json') ? DONNEES : COQUILLE;
    evenement.respondWith(reseauDabord(requete, cache));
    return;
  }
  if (/vinted\.net$/.test(url.hostname)) {
    evenement.respondWith(photo(requete));
  }
});

async function reseauDabord(requete, nomCache) {
  const cache = await caches.open(nomCache);
  try {
    const reponse = await fetch(requete);
    if (reponse.ok) cache.put(requete, reponse.clone());
    return reponse;
  } catch (erreur) {
    const garde = await cache.match(requete);
    if (garde) return garde;
    // Une navigation hors réseau vers une adresse jamais visitée : on rend la
    // page d'accueil, qui est en cache, plutôt qu'une erreur du navigateur.
    if (requete.mode === 'navigate') {
      const accueil = await cache.match('./index.html');
      if (accueil) return accueil;
    }
    throw erreur;
  }
}

async function photo(requete) {
  const cache = await caches.open(PHOTOS);
  const garde = await cache.match(requete);
  if (garde) return garde;
  const reponse = await fetch(requete);
  if (reponse.ok) {
    cache.put(requete, reponse.clone());
    elaguer(cache);
  }
  return reponse;
}

async function elaguer(cache) {
  const clefs = await cache.keys();
  if (clefs.length <= PLAFOND_PHOTOS) return;
  for (const clef of clefs.slice(0, clefs.length - PLAFOND_PHOTOS)) {
    await cache.delete(clef);
  }
}
