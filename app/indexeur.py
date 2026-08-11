#!/usr/bin/env python3
"""Construit l'index du dressing Vinted de flavie_grt.

Le navigateur ne peut pas interroger Vinted lui-même (l'API ne renvoie aucun
en-tête CORS) : c'est ce script qui va chercher les annonces et écrit
web/index.json, que l'app lit ensuite depuis le téléphone.

    python3 indexeur.py            met l'index à jour
    python3 indexeur.py --complet  reclasse tout depuis zéro

Aucune dépendance : bibliothèque standard uniquement, Python 3.8+.
"""

import argparse
import gzip
import http.cookiejar
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

MEMBRE = 14271229
PROFIL = "flaviegrt"
BASE = "https://www.vinted.fr"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)

RACINE = Path(__file__).resolve().parent
SORTIE = RACINE / "web" / "index.json"
GRAINE = RACINE.parent / "reconnaissance" / "classement-catalogues.json"

# Les intitulés de premier niveau du catalogue Vinted. Ils servent de points
# d'entrée pour retrouver l'arbre complet dans le HTML de la page profil.
RACINES = [
    "Femmes",
    "Hommes",
    "Articles de créateurs",
    "Enfants",
    "Maison",
    "Électronique",
    "Divertissement",
    "Livres et médias",
    "Loisirs et collections",
    "Sport",
]


class Vinted:
    """Une session Vinted : quelques cookies suffisent, aucun compte requis."""

    def __init__(self, pause=0.4):
        self.cookies = http.cookiejar.CookieJar()
        self.ouvreur = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies)
        )
        self.pause = pause
        self._dernier = 0.0
        self._amorcer()

    def _amorcer(self):
        self.get(BASE + "/", json_attendu=False)

    def get(self, url, json_attendu=True, essais=5):
        """GET avec ralentissement et reprise sur limitation de débit."""
        for essai in range(essais):
            attente = self.pause - (time.time() - self._dernier)
            if attente > 0:
                time.sleep(attente)
            requete = urllib.request.Request(
                url,
                headers={
                    "User-Agent": UA,
                    "Accept": "application/json" if json_attendu else "text/html",
                    "Accept-Encoding": "gzip",
                    "Accept-Language": "fr-FR,fr;q=0.9",
                },
            )
            try:
                with self.ouvreur.open(requete, timeout=30) as reponse:
                    brut = reponse.read()
                    if reponse.headers.get("Content-Encoding") == "gzip":
                        brut = gzip.decompress(brut)
                    self._dernier = time.time()
                    texte = brut.decode("utf-8", "replace")
                    return json.loads(texte) if json_attendu else texte
            except urllib.error.HTTPError as erreur:
                self._dernier = time.time()
                if erreur.code in (429, 403, 503) and essai < essais - 1:
                    repos = 5 * (essai + 1)
                    print(
                        f"    (Vinted limite le débit, pause de {repos} s)",
                        file=sys.stderr,
                    )
                    time.sleep(repos)
                    continue
                raise
            except (urllib.error.URLError, TimeoutError):
                self._dernier = time.time()
                if essai < essais - 1:
                    time.sleep(3 * (essai + 1))
                    continue
                raise
        raise RuntimeError(f"échec après {essais} essais : {url}")


# --------------------------------------------------------------------------
# Les annonces
# --------------------------------------------------------------------------

def lire_dressing(vinted):
    """Toutes les annonces actives, en une poignée de requêtes."""
    articles, page = [], 1
    while True:
        url = (
            f"{BASE}/api/v2/wardrobe/{MEMBRE}/items"
            f"?page={page}&per_page=96&order=relevance"
        )
        reponse = vinted.get(url)
        lot = reponse.get("items", [])
        for brut in lot:
            articles.append(convertir(brut))
        pagination = reponse.get("pagination", {})
        print(
            f"  page {page}/{pagination.get('total_pages', '?')} "
            f"— {len(articles)} annonces",
            file=sys.stderr,
        )
        if page >= pagination.get("total_pages", 0) or not lot:
            break
        page += 1
    return articles


def convertir(brut):
    photos = brut.get("photos") or []
    vignette, grande = "", ""
    if photos:
        for miniature in photos[0].get("thumbnails", []):
            if miniature.get("type") == "thumb310x430":
                vignette = miniature["url"]
        grande = photos[0].get("url", "")
        if not vignette:
            vignette = grande
    return {
        "id": brut["id"],
        "titre": brut.get("title", ""),
        "marque": brut.get("brand") or "",
        "taille": brut.get("size") or "",
        "etat": brut.get("status") or "",
        "prix": float(brut.get("price", {}).get("amount", 0)),
        "prix_total": float(brut.get("total_item_price", {}).get("amount", 0)),
        "favoris": brut.get("favourite_count", 0),
        "reserve": bool(brut.get("is_reserved")),
        "url": brut.get("url") or f"{BASE}/items/{brut['id']}",
        "vignette": vignette,
        "photo": grande,
        "photos": len(photos),
    }


# --------------------------------------------------------------------------
# L'arbre des catégories
# --------------------------------------------------------------------------

def lire_arbre(vinted):
    """Extrait l'arbre du catalogue Vinted, embarqué dans la page profil."""
    html = vinted.get(f"{BASE}/member/{MEMBRE}-{PROFIL}", json_attendu=False)
    texte = html.replace('\\\\"', '"').replace('\\"', '"')
    noeuds, connus = [], set()
    candidats = []
    for titre in RACINES:
        marque = f'"title":"{titre}","url":"/catalog/'
        depart = 0
        while True:
            trouve = texte.find(marque, depart)
            if trouve < 0:
                break
            debut = texte.rfind("{", 0, trouve)
            objet = _decouper(texte, debut)
            if objet:
                candidats.append(objet)
            depart = trouve + 1
    # Le plus gros sous-arbre gagne : les homonymes de sous-catégorie
    # (« Sport », « Chaussures »…) sont absorbés par leur racine.
    for objet in sorted(candidats, key=lambda n: -_taille(n)):
        if objet["id"] in connus:
            continue
        _marquer(objet, connus)
        noeuds.append(objet)
    return noeuds


def _decouper(texte, debut):
    """Isole l'objet JSON qui commence à `debut` en comptant les accolades."""
    if debut < 0:
        return None
    profondeur = 0
    for position in range(debut, min(len(texte), debut + 4_000_000)):
        caractere = texte[position]
        if caractere == "{":
            profondeur += 1
        elif caractere == "}":
            profondeur -= 1
            if profondeur == 0:
                try:
                    return json.loads(texte[debut : position + 1])
                except ValueError:
                    return None
    return None


def _taille(noeud):
    return 1 + sum(_taille(enfant) for enfant in noeud.get("catalogs", []))


def _marquer(noeud, connus):
    connus.add(noeud["id"])
    for enfant in noeud.get("catalogs", []):
        _marquer(enfant, connus)


def aplatir(racines):
    """{id: chemin lisible} pour tout l'arbre."""
    chemins = {}

    def descendre(noeud, parents):
        chemin = parents + [noeud["title"]]
        chemins[noeud["id"]] = chemin
        for enfant in noeud.get("catalogs", []):
            descendre(enfant, chemin)

    for racine in racines:
        descendre(racine, [])
    return chemins


# --------------------------------------------------------------------------
# Le classement des annonces par catégorie
# --------------------------------------------------------------------------

def classer_par_arbre(vinted, racines, chemins, profondeur_max=3):
    """Parcours descendant : une requête par catégorie non vide.

    Vinted ne donne pas la catégorie d'une annonce, mais accepte de filtrer le
    dressing par catégorie. On interroge donc l'arbre de haut en bas, en ne
    descendant que là où il y a quelque chose. Compter une centaine de requêtes
    et une vingtaine de minutes : à ne faire qu'une fois.
    """
    classement, front = {}, [racine["id"] for racine in racines]
    enfants = {}

    def recenser(noeud):
        enfants[noeud["id"]] = [petit["id"] for petit in noeud.get("catalogs", [])]
        for petit in noeud.get("catalogs", []):
            recenser(petit)

    for racine in racines:
        recenser(racine)

    vus = set()
    while front:
        suivant = []
        for catalogue in front:
            if catalogue in vus or len(chemins.get(catalogue, [])) > profondeur_max:
                continue
            vus.add(catalogue)
            url = (
                f"{BASE}/api/v2/wardrobe/{MEMBRE}/items"
                f"?page=1&per_page=96&order=relevance&catalog_ids={catalogue}"
            )
            reponse = vinted.get(url)
            trouves = [article["id"] for article in reponse.get("items", [])]
            if not trouves:
                continue
            print(
                f"  {' > '.join(chemins[catalogue])} : {len(trouves)}",
                file=sys.stderr,
            )
            for article in trouves:
                ancien = classement.get(article)
                if ancien is None or len(chemins[catalogue]) > len(chemins[ancien]):
                    classement[article] = catalogue
            suivant.extend(enfants.get(catalogue, []))
        front = suivant
    return classement


FIL = re.compile(r'/catalog/(\d+)-[^"?]*\?referrer=item-crumbs')


def classer_une(vinted, article_id):
    """Catégorie d'une annonce, lue dans le fil d'Ariane de sa page.

    Une requête par annonce : réservé aux nouveautés, quelques-unes par semaine.
    """
    html = vinted.get(f"{BASE}/items/{article_id}", json_attendu=False)
    catalogues = FIL.findall(html)
    return int(catalogues[-1]) if catalogues else None


# --------------------------------------------------------------------------
# Ce que l'app attend
# --------------------------------------------------------------------------

GENRES = [
    ("Vêtements pour filles", "Fille"),
    ("Vêtements pour garçons", "Garçon"),
    ("Femmes", "Femme"),
    ("Hommes", "Homme"),
]

# Les tailles bébé et enfant, dans l'ordre où on grandit — Vinted les rend
# sous des libellés qui ne se trient pas tout seuls.
ORDRE_TAILLES = [
    "Prématuré, jusqu'à 44cm",
    "Naissance / 44 cm",
    "Jusqu'à 1 mois / 50 cm",
    "0-3 mois, 38 cm",
    "1-3 mois / 56 cm",
    "3-6 mois / 62 cm",
    "3-6 mois, 42 cm",
    "6-9 mois / 68 cm",
    "9-12 mois / 74 cm",
    "12-18 mois / 80 cm",
    "1-2 ans, 49 cm",
    "18-24 mois / 86 cm",
    "24-36 mois / 92 cm",
    "3 ans / 98 cm",
    "4 ans / 104 cm",
    "5 ans / 110 cm",
    "6 ans / 116 cm",
    "7 ans / 122 cm",
    "8 ans / 128 cm",
    "9 ans / 134 cm",
    "10 ans / 140 cm",
    "11 ans / 146 cm",
    "12 ans / 152 cm",
    "13 ans / 158 cm",
    "14 ans / 164 cm",
    "XS",
    "S",
    "M",
    "L",
    "XL",
]


def genre_de(chemin):
    for motif, genre in GENRES:
        if motif in chemin:
            return genre
    return ""


def rang_taille(taille):
    if taille in ORDRE_TAILLES:
        return ORDRE_TAILLES.index(taille)
    if taille.isdigit():  # pointures
        return 1000 + int(taille)
    return 2000


def enrichir(articles, classement, chemins):
    for article in articles:
        catalogue = classement.get(article["id"])
        chemin = chemins.get(catalogue, []) if catalogue else []
        article["categorie_id"] = catalogue or 0
        article["categorie"] = " > ".join(chemin)
        article["rayon"] = chemin[0] if chemin else ""
        article["type"] = chemin[-1] if chemin else ""
        article["genre"] = genre_de(article["categorie"])
        article["rang_taille"] = rang_taille(article["taille"])
    return articles


def index_precedent():
    """Les articles du relevé précédent, tels qu'ils étaient."""
    if not SORTIE.exists():
        return []
    return json.loads(SORTIE.read_text(encoding="utf-8")).get("articles", [])


def fusionner(articles, anciens):
    """Garde ce qui a quitté le profil au lieu de l'oublier.

    Flavie masque souvent ses annonces, et l'API publique ne renvoie que ce qui
    est en ligne : sans mémoire, un article masqué s'évanouirait de l'app avec
    son emplacement de rangement — juste au moment où l'on cherche où il est.

    Depuis un profil public, impossible de distinguer vendu, masqué et
    supprimé : on ne dit donc que « n'apparaît plus ».
    """
    aujourdhui = datetime.now(timezone.utc).date().isoformat()
    presents = {article["id"] for article in articles}

    for article in articles:
        article["en_ligne"] = True
        article["vu_le"] = aujourdhui
        article.pop("disparu_le", None)

    revenus = 0
    for ancien in anciens:
        if ancien["id"] in presents:
            if not ancien.get("en_ligne", True):
                revenus += 1
            continue
        garde = dict(ancien)
        garde["en_ligne"] = False
        garde.setdefault("disparu_le", aujourdhui)
        articles.append(garde)

    return articles, revenus


def ecrire(articles):
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    en_ligne = sum(1 for article in articles if article.get("en_ligne", True))
    index = {
        "genere_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "membre": PROFIL,
        "profil": f"{BASE}/member/{MEMBRE}-{PROFIL}",
        "total": len(articles),
        "en_ligne": en_ligne,
        "hors_ligne": len(articles) - en_ligne,
        "articles": sorted(articles, key=lambda a: -a["id"]),
    }
    SORTIE.write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return index


def classement_existant(complet):
    """Ce qu'on sait déjà : l'index précédent, ou le relevé de reconnaissance."""
    if complet:
        return {}
    if SORTIE.exists():
        ancien = json.loads(SORTIE.read_text(encoding="utf-8"))
        return {
            article["id"]: article["categorie_id"]
            for article in ancien.get("articles", [])
            if article.get("categorie_id")
        }
    if GRAINE.exists():
        graine = json.loads(GRAINE.read_text(encoding="utf-8"))
        return {
            article: int(catalogue)
            for catalogue, articles in graine["inv"].items()
            for article in articles
        }
    return {}


def main():
    options = argparse.ArgumentParser(description=__doc__)
    options.add_argument(
        "--complet",
        action="store_true",
        help="reclasse tout depuis zéro (long : ~20 min)",
    )
    options.add_argument(
        "--max-nouveautes",
        type=int,
        default=60,
        help="au-delà, on reclasse par l'arbre plutôt qu'annonce par annonce",
    )
    arguments = options.parse_args()

    vinted = Vinted()
    print("Lecture du dressing…", file=sys.stderr)
    articles = lire_dressing(vinted)

    print("Lecture de l'arbre des catégories…", file=sys.stderr)
    racines = lire_arbre(vinted)
    chemins = aplatir(racines)
    print(f"  {len(chemins)} catégories", file=sys.stderr)

    # On garde aussi le classement des articles absents : s'ils reviennent en
    # ligne, leur catégorie est déjà connue et ne coûte pas une requête.
    classement = classement_existant(arguments.complet)
    manquants = [
        article["id"] for article in articles if article["id"] not in classement
    ]

    if manquants:
        print(f"{len(manquants)} annonce(s) à classer", file=sys.stderr)
        if len(manquants) > arguments.max_nouveautes:
            classement.update(classer_par_arbre(vinted, racines, chemins))
        else:
            for numero, article_id in enumerate(manquants, 1):
                catalogue = classer_une(vinted, article_id)
                if catalogue:
                    classement[article_id] = catalogue
                    print(
                        f"  [{numero}/{len(manquants)}] {article_id} → "
                        f"{' > '.join(chemins.get(catalogue, ['?']))}",
                        file=sys.stderr,
                    )
    else:
        print("Rien de nouveau à classer.", file=sys.stderr)

    enrichir(articles, classement, chemins)

    # Après l'enrichissement : les articles repêchés du relevé précédent
    # portent déjà leur catégorie, il ne faut pas la leur reprendre.
    anciens = [] if arguments.complet else index_precedent()
    articles, revenus = fusionner(articles, anciens)

    index = ecrire(articles)
    sans = sum(1 for article in articles if not article["categorie"])
    print(
        f"\n{index['en_ligne']} annonces en ligne écrites dans {SORTIE}",
        file=sys.stderr,
    )
    if index["hors_ligne"]:
        print(
            f"{index['hors_ligne']} article(s) gardé(s) en mémoire, "
            "vendus, masqués ou retirés",
            file=sys.stderr,
        )
    if revenus:
        print(f"{revenus} article(s) revenu(s) en ligne", file=sys.stderr)
    if sans:
        print(f"{sans} sans catégorie", file=sys.stderr)


if __name__ == "__main__":
    main()
