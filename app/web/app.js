'use strict';

/* Le dressing — recherche hors ligne dans les annonces Vinted de flavie_grt.
   L'index est produit par indexeur.py ; cette page ne fait que le lire. */

const CLE_RANGEMENTS = 'dressing.rangements';

let ARTICLES = [];
let META = {};
let rangements = lireRangements();

const filtres = { q: '', genre: [], taille: [], type: [], marque: [], etat: [], rayon: [], range: [] };
let tri = 'recent';

const FACETTES = [
  { cle: 'genre',  titre: 'Genre',      champ: 'genre',  ordre: ['Fille', 'Garçon', 'Femme', 'Homme'] },
  { cle: 'taille', titre: 'Taille',     champ: 'taille', ordre: 'taille' },
  { cle: 'type',   titre: 'Type',       champ: 'type',   ordre: 'nombre' },
  { cle: 'marque', titre: 'Marque',     champ: 'marque', ordre: 'nombre' },
  { cle: 'etat',   titre: 'État',       champ: 'etat',
    ordre: ['Neuf avec étiquette', 'Neuf sans étiquette', 'Très bon état', 'Bon état', 'Satisfaisant'] },
  { cle: 'rayon',  titre: 'Rayon',      champ: 'rayon',  ordre: 'nombre' },
  { cle: 'range',  titre: 'Rangement',  champ: 'range',  ordre: ['Emplacement noté', 'Sans emplacement'] },
];

const TRIS = [
  ['recent', 'Plus récent d’abord'],
  ['taille', 'Par taille, du plus petit'],
  ['prix-bas', 'Prix croissant'],
  ['prix-haut', 'Prix décroissant'],
  ['favoris', 'Plus de favoris'],
];

const $ = (id) => document.getElementById(id);

// --------------------------------------------------------------- démarrage

demarrer();

async function demarrer() {
  brancher();

  // En fichier unique, l'index voyage dans la page : ni requête, ni service
  // worker, rien à côté du fichier.
  const embarque = $('index-embarque');
  if (embarque) {
    charger(JSON.parse(embarque.textContent));
    $('recharger').hidden = true;
    return;
  }

  try {
    const local = await fetch('index.json', { cache: 'no-cache' });
    charger(await local.json());
  } catch (erreur) {
    $('decompte').textContent = 'Index introuvable. Reconnectez-vous une fois au réseau.';
    return;
  }
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  }
}

function charger(index) {
  META = index;
  ARTICLES = index.articles.map((article) => ({
    ...article,
    recherche: [article.titre, article.marque, article.categorie, article.taille]
      .join(' ').toLowerCase(),
  }));
  marquerRangements();
  dessinerFacettes();
  rendre();
  dessinerTailles();
  $('infos-fraicheur').textContent =
    `${index.total} annonces, relevées le ${dateLisible(index.genere_le)}.`;
}

// ------------------------------------------------------------ branchements

function brancher() {
  const champ = $('champ-recherche');
  champ.addEventListener('input', () => {
    filtres.q = champ.value.trim().toLowerCase();
    $('effacer-recherche').hidden = !champ.value;
    rendre();
  });
  $('effacer-recherche').addEventListener('click', () => {
    champ.value = '';
    filtres.q = '';
    $('effacer-recherche').hidden = true;
    rendre();
    champ.focus();
  });

  document.querySelectorAll('.onglets button').forEach((bouton) => {
    bouton.addEventListener('click', () => montrerVue(bouton.dataset.vue));
  });

  $('voile').addEventListener('click', fermerFeuille);
  $('feuille-annuler').addEventListener('click', fermerFeuille);
  $('bouton-infos').addEventListener('click', () => {
    majInfos();
    $('infos').hidden = false;
  });
  $('infos-fermer').addEventListener('click', () => { $('infos').hidden = true; });
  $('fiche-fermer').addEventListener('click', () => { $('fiche').hidden = true; });

  $('exporter').addEventListener('click', exporter);
  $('importer').addEventListener('click', () => $('fichier-import').click());
  $('fichier-import').addEventListener('change', importer);
  $('recharger').addEventListener('click', recharger);
}

function montrerVue(vue) {
  $('vue-chercher').hidden = vue !== 'chercher';
  $('vue-tailles').hidden = vue !== 'tailles';
  document.querySelectorAll('.onglets button').forEach((bouton) => {
    bouton.classList.toggle('actif', bouton.dataset.vue === vue);
  });
  scrollTo(0, 0);
}

// ------------------------------------------------------------------ filtres

/** Les articles retenus, en ignorant éventuellement une facette.
 *  L'exception sert à compter les options d'une facette sans qu'elle
 *  se compte elle-même : sinon toute option non cochée afficherait zéro. */
function retenus(sauf) {
  return ARTICLES.filter((article) => {
    if (filtres.q && !article.recherche.includes(filtres.q)) return false;
    return FACETTES.every(({ cle, champ }) => {
      if (cle === sauf || filtres[cle].length === 0) return true;
      return filtres[cle].includes(article[champ] || '');
    });
  });
}

function trier(articles) {
  const copie = articles.slice();
  const par = {
    recent: (a, b) => b.id - a.id,
    taille: (a, b) => a.rang_taille - b.rang_taille || b.id - a.id,
    'prix-bas': (a, b) => a.prix - b.prix,
    'prix-haut': (a, b) => b.prix - a.prix,
    favoris: (a, b) => b.favoris - a.favoris || b.id - a.id,
  };
  return copie.sort(par[tri] || par.recent);
}

function actifs() {
  return FACETTES.filter(({ cle }) => filtres[cle].length > 0);
}

// ------------------------------------------------------------------ rendu

function rendre() {
  const liste = trier(retenus());
  const resultats = $('resultats');
  resultats.innerHTML = '';

  const total = ARTICLES.length;
  const compte = liste.length === total
    ? `${total} annonces`
    : `${liste.length} sur ${total} annonces`;
  $('decompte').textContent = compte + fraicheur();
  $('aucun-resultat').hidden = liste.length > 0;

  const fragment = document.createDocumentFragment();
  for (const article of liste) fragment.appendChild(carte(article));
  resultats.appendChild(fragment);

  majFacettes();
  majChips();
}

function carte(article) {
  const bouton = document.createElement('button');
  bouton.className = 'carte';
  bouton.appendChild(vignette(article));

  const texte = document.createElement('div');
  texte.className = 'carte__texte';
  texte.appendChild(ligne('carte__titre', article.titre));

  const details = [article.taille, article.marque].filter(Boolean).join(' · ');
  if (details) texte.appendChild(ligne('carte__detail', details));
  texte.appendChild(ligne('carte__prix', prixLisible(article.prix)));

  const emplacement = rangements[article.id];
  if (emplacement) {
    const pastille = ligne('pastille', emplacement);
    pastille.style.marginTop = '4px';
    pastille.style.alignSelf = 'flex-start';
    texte.appendChild(pastille);
  }

  bouton.appendChild(texte);
  bouton.addEventListener('click', () => ouvrirFiche(article));
  return bouton;
}

function vignette(article) {
  const image = document.createElement('img');
  image.loading = 'lazy';
  image.decoding = 'async';
  image.alt = '';
  image.src = article.vignette;
  return image;
}

function ligne(classe, texte) {
  const element = document.createElement('div');
  element.className = classe;
  element.textContent = texte;
  return element;
}

// ---------------------------------------------------------------- facettes

function dessinerFacettes() {
  const barre = $('facettes');
  barre.innerHTML = '';
  for (const facette of FACETTES) {
    const bouton = document.createElement('button');
    bouton.dataset.cle = facette.cle;
    bouton.addEventListener('click', () => ouvrirFeuille(facette));
    barre.appendChild(bouton);
  }
  const boutonTri = document.createElement('button');
  boutonTri.dataset.cle = 'tri';
  boutonTri.addEventListener('click', ouvrirTri);
  barre.appendChild(boutonTri);
  majFacettes();
}

function majFacettes() {
  for (const facette of FACETTES) {
    const bouton = document.querySelector(`.facettes [data-cle="${facette.cle}"]`);
    const choisis = filtres[facette.cle];
    bouton.textContent = choisis.length === 0
      ? facette.titre
      : (choisis.length === 1 ? etiquette(choisis[0]) : `${facette.titre} · ${choisis.length}`);
    bouton.classList.toggle('rempli', choisis.length > 0);
  }
  const boutonTri = document.querySelector('.facettes [data-cle="tri"]');
  boutonTri.textContent = TRIS.find(([cle]) => cle === tri)[1];
  boutonTri.classList.toggle('rempli', tri !== 'recent');
}

function majChips() {
  const zone = $('chips');
  zone.innerHTML = '';
  const enCours = actifs();
  zone.hidden = enCours.length === 0;
  if (zone.hidden) return;

  for (const facette of enCours) {
    for (const valeur of filtres[facette.cle]) {
      const bouton = document.createElement('button');
      bouton.textContent = `${etiquette(valeur)} ✕`;
      bouton.addEventListener('click', () => {
        filtres[facette.cle] = filtres[facette.cle].filter((v) => v !== valeur);
        rendre();
      });
      zone.appendChild(bouton);
    }
  }
  const raz = document.createElement('button');
  raz.className = 'raz';
  raz.textContent = 'Tout enlever';
  raz.addEventListener('click', () => {
    for (const { cle } of FACETTES) filtres[cle] = [];
    rendre();
  });
  zone.appendChild(raz);
}

function etiquette(valeur) {
  return valeur === '' ? 'Non précisé' : valeur;
}

/** Les options d'une facette, avec le nombre d'articles derrière chacune. */
function options(facette) {
  const base = retenus(facette.cle);
  const nombres = new Map();
  for (const article of base) {
    const valeur = article[facette.champ] || '';
    nombres.set(valeur, (nombres.get(valeur) || 0) + 1);
  }
  // Les valeurs cochées restent visibles même si plus rien ne les porte.
  for (const valeur of filtres[facette.cle]) {
    if (!nombres.has(valeur)) nombres.set(valeur, 0);
  }

  const liste = [...nombres.entries()].map(([valeur, nombre]) => ({ valeur, nombre }));
  if (Array.isArray(facette.ordre)) {
    liste.sort((a, b) => rangDans(facette.ordre, a.valeur) - rangDans(facette.ordre, b.valeur));
  } else if (facette.ordre === 'taille') {
    const rangs = new Map(ARTICLES.map((a) => [a.taille, a.rang_taille]));
    liste.sort((a, b) => (rangs.get(a.valeur) ?? 9999) - (rangs.get(b.valeur) ?? 9999));
  } else {
    liste.sort((a, b) => b.nombre - a.nombre || a.valeur.localeCompare(b.valeur, 'fr'));
  }
  return liste;
}

function rangDans(ordre, valeur) {
  const rang = ordre.indexOf(valeur);
  return rang < 0 ? ordre.length : rang;
}

// ------------------------------------------------------- feuille de filtre

let facetteOuverte = null;

function ouvrirFeuille(facette) {
  facetteOuverte = facette;
  $('feuille-titre').textContent = facette.titre;
  $('feuille-vider').hidden = false;
  $('feuille-vider').textContent = 'Tout enlever';
  $('feuille-vider').onclick = () => {
    filtres[facette.cle] = [];
    remplirFeuille();
    rendre();
  };
  $('feuille-valider').onclick = fermerFeuille;
  remplirFeuille();
  $('voile').hidden = false;
  $('feuille').hidden = false;
}

function remplirFeuille() {
  const facette = facetteOuverte;
  const corps = $('feuille-corps');
  corps.innerHTML = '';
  for (const { valeur, nombre } of options(facette)) {
    const choisi = filtres[facette.cle].includes(valeur);
    const bouton = document.createElement('button');
    bouton.className = 'option';
    bouton.setAttribute('aria-pressed', String(choisi));
    bouton.disabled = nombre === 0 && !choisi;
    bouton.innerHTML = '<span class="option__coche">✓</span>';
    bouton.appendChild(ligne('option__nom', etiquette(valeur)));
    bouton.appendChild(ligne('option__nombre', String(nombre)));
    bouton.addEventListener('click', () => {
      const choisis = filtres[facette.cle];
      filtres[facette.cle] = choisis.includes(valeur)
        ? choisis.filter((v) => v !== valeur)
        : choisis.concat(valeur);
      remplirFeuille();
      rendre();
    });
    corps.appendChild(bouton);
  }
  const liste = retenus();
  $('feuille-valider').textContent = liste.length === 1
    ? 'Voir 1 article'
    : `Voir les ${liste.length} articles`;
}

function ouvrirTri() {
  facetteOuverte = null;
  $('feuille-titre').textContent = 'Trier';
  $('feuille-vider').hidden = true;
  const corps = $('feuille-corps');
  corps.innerHTML = '';
  for (const [cle, nom] of TRIS) {
    const bouton = document.createElement('button');
    bouton.className = 'option';
    bouton.setAttribute('aria-pressed', String(tri === cle));
    bouton.innerHTML = '<span class="option__coche">✓</span>';
    bouton.appendChild(ligne('option__nom', nom));
    bouton.addEventListener('click', () => {
      tri = cle;
      fermerFeuille();
      rendre();
    });
    corps.appendChild(bouton);
  }
  $('feuille-valider').textContent = 'Fermer';
  $('feuille-valider').onclick = fermerFeuille;
  $('voile').hidden = false;
  $('feuille').hidden = false;
}

function fermerFeuille() {
  $('voile').hidden = true;
  $('feuille').hidden = true;
  facetteOuverte = null;
}

// -------------------------------------------------------------------- fiche

function ouvrirFiche(article) {
  const corps = $('fiche-corps');
  corps.innerHTML = '';

  const photo = document.createElement('img');
  photo.className = 'fiche__photo';
  photo.src = article.photo || article.vignette;
  photo.alt = '';
  corps.appendChild(photo);

  const titre = document.createElement('h2');
  titre.textContent = article.titre;
  corps.appendChild(titre);

  const lignes = [
    ['Prix', `${prixLisible(article.prix)} (${prixLisible(article.prix_total)} pour l’acheteur)`],
    ['Taille', article.taille],
    ['Marque', article.marque],
    ['État', article.etat],
    ['Catégorie', article.categorie],
    ['Favoris', article.favoris ? String(article.favoris) : ''],
    ['Réservé', article.reserve ? 'oui' : ''],
  ].filter(([, valeur]) => valeur);

  const tableau = document.createElement('table');
  tableau.className = 'tableau-infos';
  for (const [nom, valeur] of lignes) {
    const rangee = tableau.insertRow();
    const entete = document.createElement('th');
    entete.textContent = nom;
    rangee.appendChild(entete);
    rangee.insertCell().textContent = valeur;
  }
  corps.appendChild(tableau);

  const sousTitre = document.createElement('h3');
  sousTitre.textContent = 'Où est-il rangé ?';
  corps.appendChild(sousTitre);

  const aide = document.createElement('p');
  aide.className = 'gris';
  aide.textContent = 'Noté dans ce téléphone seulement. Par exemple : carton 3, penderie du bas.';
  corps.appendChild(aide);

  const champ = document.createElement('input');
  champ.className = 'champ-rangement';
  champ.type = 'text';
  champ.placeholder = 'Emplacement';
  champ.value = rangements[article.id] || '';
  champ.addEventListener('change', () => {
    noterRangement(article.id, champ.value.trim());
    rendre();
  });
  corps.appendChild(champ);

  const lien = document.createElement('a');
  lien.className = 'lien-vinted';
  lien.href = article.url;
  lien.target = '_blank';
  lien.rel = 'noopener';
  lien.textContent = 'Ouvrir l’annonce sur Vinted';
  corps.appendChild(lien);

  $('fiche').hidden = false;
  $('fiche').scrollTo(0, 0);
}

// ------------------------------------------------------- vue d'ensemble

function dessinerTailles() {
  const zone = $('tableau-tailles');
  zone.innerHTML = '';

  // Séparés pour que chaque tableau garde ses seules colonnes utiles : les
  // tailles bébé n'ont rien à faire en face d'une colonne « Femme » vide.
  const enfant = (article) => article.genre === 'Fille' || article.genre === 'Garçon';
  const adulte = (article) => article.genre === 'Femme' || article.genre === 'Homme';
  const groupes = [
    ['Vêtements d’enfant', (a) => enfant(a) && a.rang_taille < 1000],
    ['Chaussures d’enfant', (a) => enfant(a) && a.rang_taille >= 1000 && a.rang_taille < 2000],
    ['Adultes', (a) => adulte(a) && a.rang_taille < 2000],
  ];

  for (const [nom, dans] of groupes) {
    const concernes = ARTICLES.filter((article) => article.taille && dans(article));
    if (concernes.length === 0) continue;

    const genres = [...new Set(concernes.map((a) => a.genre || '—'))]
      .sort((a, b) => rangDans(['Fille', 'Garçon', 'Femme', 'Homme'], a)
                    - rangDans(['Fille', 'Garçon', 'Femme', 'Homme'], b));

    const tailles = [...new Set(concernes.map((a) => a.taille))]
      .sort((a, b) => rangTaille(a) - rangTaille(b));

    const bloc = document.createElement('div');
    bloc.className = 'bloc-tailles';
    const entete = document.createElement('h2');
    entete.textContent = nom;
    bloc.appendChild(entete);

    const tableau = document.createElement('table');
    tableau.className = 'tailles';
    const enTete = tableau.createTHead().insertRow();
    enTete.appendChild(cellule('th', 'Taille'));
    for (const genre of genres) enTete.appendChild(cellule('th', genre));
    enTete.appendChild(cellule('th', 'Total'));

    const corps = tableau.createTBody();
    for (const taille of tailles) {
      const rangee = corps.insertRow();
      rangee.insertCell().textContent = taille;
      let total = 0;
      for (const genre of genres) {
        const nombre = concernes.filter(
          (a) => a.taille === taille && (a.genre || '—') === genre).length;
        total += nombre;
        rangee.appendChild(celluleNombre(nombre, taille, genre));
      }
      rangee.appendChild(celluleNombre(total, taille, null));
    }

    const pied = tableau.createTFoot().insertRow();
    pied.insertCell().textContent = 'Total';
    for (const genre of genres) {
      pied.insertCell().textContent =
        concernes.filter((a) => (a.genre || '—') === genre).length;
    }
    pied.insertCell().textContent = concernes.length;
    for (const cellulePied of pied.cells) cellulePied.style.textAlign = 'right';
    pied.cells[0].style.textAlign = 'left';

    bloc.appendChild(tableau);
    zone.appendChild(bloc);
  }
}

function rangTaille(taille) {
  const article = ARTICLES.find((a) => a.taille === taille);
  return article ? article.rang_taille : 9999;
}

function cellule(balise, texte) {
  const element = document.createElement(balise);
  element.textContent = texte;
  return element;
}

function celluleNombre(nombre, taille, genre) {
  const cellule = document.createElement('td');
  const bouton = document.createElement('button');
  bouton.textContent = nombre || '·';
  bouton.disabled = nombre === 0;
  bouton.addEventListener('click', () => {
    for (const { cle } of FACETTES) filtres[cle] = [];
    filtres.taille = [taille];
    if (genre) filtres.genre = [genre === '—' ? '' : genre];
    $('champ-recherche').value = '';
    filtres.q = '';
    rendre();
    montrerVue('chercher');
  });
  cellule.appendChild(bouton);
  return cellule;
}

// -------------------------------------------------------------- rangements

function lireRangements() {
  try {
    return JSON.parse(localStorage.getItem(CLE_RANGEMENTS) || '{}');
  } catch (erreur) {
    return {};
  }
}

function noterRangement(id, valeur) {
  if (valeur) rangements[id] = valeur;
  else delete rangements[id];
  garder();
  marquerRangements();
}

/** Écrit les rangements, sans casser là où le navigateur refuse d'écrire.
 *  C'est le cas d'un fichier ouvert directement depuis le disque, ou d'une
 *  navigation privée : la recherche doit continuer de marcher. */
function garder() {
  try {
    localStorage.setItem(CLE_RANGEMENTS, JSON.stringify(rangements));
    return true;
  } catch (erreur) {
    return false;
  }
}

function marquerRangements() {
  for (const article of ARTICLES) {
    article.range = rangements[article.id] ? 'Emplacement noté' : 'Sans emplacement';
  }
}

// ------------------------------------------------------------------- infos

function majInfos() {
  const notes = Object.keys(rangements).length;
  if (!garder()) {
    $('infos-rangements').textContent =
      'Ce navigateur refuse d’enregistrer : les emplacements notés ici seront '
      + 'perdus en fermant. Ouvrez l’app depuis une adresse web plutôt que '
      + 'depuis un fichier.';
    return;
  }
  $('infos-rangements').textContent = notes === 0
    ? 'Aucun emplacement noté pour l’instant.'
    : `${notes} emplacement${notes > 1 ? 's' : ''} noté${notes > 1 ? 's' : ''}.`;
}

function exporter() {
  const blob = new Blob([JSON.stringify(rangements, null, 1)],
    { type: 'application/json' });
  const lien = document.createElement('a');
  lien.href = URL.createObjectURL(blob);
  lien.download = 'rangements-dressing.json';
  lien.click();
  setTimeout(() => URL.revokeObjectURL(lien.href), 5000);
}

async function importer(evenement) {
  const fichier = evenement.target.files[0];
  if (!fichier) return;
  try {
    const venus = JSON.parse(await fichier.text());
    rangements = { ...rangements, ...venus };
    garder();
    marquerRangements();
    majInfos();
    rendre();
  } catch (erreur) {
    alert('Ce fichier n’est pas un export de rangements.');
  }
  evenement.target.value = '';
}

async function recharger() {
  const bouton = $('recharger');
  bouton.textContent = 'Chargement…';
  try {
    const reponse = await fetch('index.json', { cache: 'reload' });
    charger(await reponse.json());
    bouton.textContent = 'À jour';
  } catch (erreur) {
    bouton.textContent = 'Pas de réseau';
  }
  setTimeout(() => { bouton.textContent = 'Recharger maintenant'; }, 2500);
}

// ------------------------------------------------------------------ formats

function prixLisible(montant) {
  return montant.toFixed(2).replace('.', ',') + ' €';
}

function dateLisible(iso) {
  const date = new Date(iso);
  return date.toLocaleDateString('fr-FR',
    { day: 'numeric', month: 'long', year: 'numeric' });
}

/** Depuis quand l'index date — l'app se rafraîchit une fois par nuit, mieux
 *  vaut le dire que de laisser croire à des chiffres de l'instant. */
function fraicheur() {
  if (!META.genere_le) return '';
  const jour = (date) => new Date(
    date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  const releve = new Date(META.genere_le);
  const ecart = Math.round((jour(new Date()) - jour(releve)) / 86400000);
  if (ecart <= 0) return ' · relevées aujourd’hui';
  if (ecart === 1) return ' · relevées hier';
  if (ecart < 7) return ` · relevées il y a ${ecart} jours`;
  return ` · relevées le ${releve.toLocaleDateString('fr-FR',
    { day: 'numeric', month: 'long' })}`;
}
