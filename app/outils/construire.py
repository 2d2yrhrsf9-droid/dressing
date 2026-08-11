#!/usr/bin/env python3
"""Fond l'app en un seul fichier HTML, à envoyer ou à déposer où l'on veut.

    python3 outils/construire.py [chemin.html]
    python3 outils/construire.py --photos [chemin.html]

Le fichier produit contient la feuille de style, le script, les icônes et
l'index. Il n'a besoin de rien d'autre — sauf du réseau pour les photos, qui
restent chez Vinted.

Avec --photos, les vignettes sont embarquées elles aussi : le fichier devient
autonome pour de bon, mais passe de 400 Ko à quelques mégaoctets. C'est ce
qu'il faut pour un hébergement qui refuse les images venues d'ailleurs. Les
photos sont alors figées à la date de construction.
"""

import argparse
import base64
import concurrent.futures
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"
DEFAUT = Path(__file__).resolve().parent.parent.parent / "dressing.html"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"
LARGEUR = 160      # pixels : assez pour une vignette, et pour la fiche sur iPhone
QUALITE = 45


def en_donnees(chemin, type_mime):
    brut = base64.b64encode(chemin.read_bytes()).decode("ascii")
    return f"data:{type_mime};base64,{brut}"


def rapetisser(url, dossier, numero):
    """Télécharge une vignette et la réduit — sips est là sur tout Mac."""
    fichier = dossier / f"{numero}.jpg"
    requete = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(requete, timeout=30) as reponse:
        fichier.write_bytes(reponse.read())
    subprocess.run(
        ["sips", "-Z", str(LARGEUR), "-s", "formatOptions", str(QUALITE), str(fichier)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return en_donnees(fichier, "image/jpeg")


def embarquer_photos(index):
    """Remplace chaque vignette par l'image elle-même, en data: URI."""
    articles = index["articles"]
    with tempfile.TemporaryDirectory() as brouillon:
        dossier = Path(brouillon)
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as equipe:
            travaux = {
                equipe.submit(rapetisser, article["vignette"], dossier, numero): article
                for numero, article in enumerate(articles)
                if article.get("vignette")
            }
            faits = 0
            for travail in concurrent.futures.as_completed(travaux):
                article = travaux[travail]
                faits += 1
                try:
                    donnees = travail.result()
                except Exception as erreur:      # une photo manquante n'arrête rien
                    print(f"  photo indisponible : {article['id']} ({erreur})",
                          file=sys.stderr)
                    continue
                article["vignette"] = donnees
                # La fiche réutilise la même image : sous CSP stricte, l'originale
                # chez Vinted ne serait de toute façon pas chargée.
                article["photo"] = donnees
                if faits % 50 == 0:
                    print(f"  {faits}/{len(travaux)} photos", file=sys.stderr)
    return index


def construire(destination, photos=False, fragment=False):
    html = (WEB / "index.html").read_text(encoding="utf-8")
    css = (WEB / "app.css").read_text(encoding="utf-8")
    js = (WEB / "app.js").read_text(encoding="utf-8")
    index = json.loads((WEB / "index.json").read_text(encoding="utf-8"))
    if photos:
        print(f"Embarquement de {index['total']} photos…", file=sys.stderr)
        embarquer_photos(index)

    # Le manifeste et le service worker n'ont pas de sens hors d'un site : ils
    # supposent des fichiers voisins. On garde l'icône, qui suffit à « Sur
    # l'écran d'accueil ».
    html = re.sub(r'\s*<link rel="manifest"[^>]*>', "", html)
    html = html.replace(
        '<link rel="apple-touch-icon" href="icone-180.png">',
        f'<link rel="apple-touch-icon" href="{en_donnees(WEB / "icone-180.png", "image/png")}">',
    )
    html = html.replace(
        '<link rel="icon" href="icone-192.png">',
        f'<link rel="icon" href="{en_donnees(WEB / "icone-192.png", "image/png")}">',
    )
    html = html.replace(
        '<link rel="stylesheet" href="app.css">',
        f"<style>\n{css}\n</style>",
    )

    # </script> à l'intérieur d'un script fermerait la balise trop tôt ; le cas
    # ne se présente pas dans des titres d'annonces, mais mieux vaut l'exclure.
    donnees = json.dumps(index, ensure_ascii=False, separators=(",", ":"))
    donnees = donnees.replace("</", "<\\/")

    html = html.replace(
        '<script src="app.js"></script>',
        f'<script type="application/json" id="index-embarque">{donnees}</script>\n'
        f"<script>\n{js}\n</script>",
    )

    if fragment:
        html = extraire_corps(html, css)

    destination.write_text(html, encoding="utf-8")
    return destination


def extraire_corps(html, css):
    """Le contenu seul, sans <html> ni <head>.

    Certains hébergeurs — dont les artefacts de Claude — enveloppent eux-mêmes
    la page dans leur propre squelette et refusent qu'on fournisse le nôtre.
    """
    debut = html.index("<body>") + len("<body>")
    fin = html.index("</body>")
    return f"<style>\n{css}\n</style>\n" + html[debut:fin].strip() + "\n"


def main():
    options = argparse.ArgumentParser(description=__doc__)
    options.add_argument("destination", nargs="?", default=str(DEFAUT))
    options.add_argument("--photos", action="store_true",
                         help="embarquer aussi les vignettes (fichier de plusieurs Mo)")
    options.add_argument("--fragment", action="store_true",
                         help="sans <html> ni <head>, pour un hébergeur qui les fournit")
    options.add_argument("--remplacer", action="store_true",
                         help="autoriser l'écrasement d'un fichier existant")
    arguments = options.parse_args()

    destination = Path(arguments.destination).resolve()
    # Un fichier déjà construit est peut-être celui que quelqu'un utilise, et
    # ce dossier est synchronisé par Dropbox : on ne l'écrase pas sans le dire.
    if destination.exists() and not arguments.remplacer:
        print(f"{destination} existe déjà — laissé intact.", file=sys.stderr)
        print("Donnez un autre chemin, ou --remplacer pour l'écraser.",
              file=sys.stderr)
        return 1

    fichier = construire(destination, arguments.photos, arguments.fragment)
    poids = fichier.stat().st_size / 1024
    index = json.loads((WEB / "index.json").read_text(encoding="utf-8"))
    print(f"{fichier}")
    print(f"{index['total']} annonces — "
          + (f"{poids / 1024:.1f} Mo" if poids > 1024 else f"{poids:.0f} Ko"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
