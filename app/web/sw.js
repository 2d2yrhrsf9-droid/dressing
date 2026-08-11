/* Service worker : l'app doit s'ouvrir et rester utilisable sans réseau.

   Trois régimes selon ce qu'on demande :
   - la coquille (HTML, CSS, JS, icônes) : le cache d'abord, mise à jour en fond ;
   - index.json : le réseau d'abord, le cache si ça ne répond pas ;
   - les photos Vinted : le cache d'abord, plafonné pour ne pas saturer. */

const VERSION = 'dressing-v1';
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

  if (url.origin === self.location.origin && url.pathname.endsWith('index.json')) {
    evenement.respondWith(reseauDabord(requete));
    return;
  }
  if (url.origin === self.location.origin) {
    evenement.respondWith(cacheDabord(requete, COQUILLE));
    return;
  }
  if (/vinted\.net$/.test(url.hostname)) {
    evenement.respondWith(photo(requete));
  }
});

async function reseauDabord(requete) {
  const cache = await caches.open(DONNEES);
  try {
    const reponse = await fetch(requete);
    if (reponse.ok) cache.put(requete, reponse.clone());
    return reponse;
  } catch (erreur) {
    const garde = await cache.match(requete);
    if (garde) return garde;
    throw erreur;
  }
}

async function cacheDabord(requete, nomCache) {
  const cache = await caches.open(nomCache);
  const garde = await cache.match(requete);
  const frais = fetch(requete)
    .then((reponse) => {
      if (reponse.ok) cache.put(requete, reponse.clone());
      return reponse;
    })
    .catch(() => garde);
  return garde || frais;
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
