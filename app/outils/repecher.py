#!/usr/bin/env python3
"""Repêche dans l'historique git les articles disparus avant la mémoire.

L'indexeur ne garde trace des articles absents que depuis qu'on le lui a
demandé. Ceux qui avaient déjà quitté le profil manquent à l'appel — or les
relevés précédents dorment dans les commits du dépôt.

    python3 outils/repecher.py            montre ce qui serait repêché
    python3 outils/repecher.py --ecrire   l'ajoute à l'index

À n'utiliser qu'une fois, pour rattraper le retard.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "web" / "index.json"
SUIVI = "app/web/index.json"


def relevés_passés():
    """Chaque version de l'index vue par git, de la plus ancienne à la plus récente."""
    journal = subprocess.run(
        ["git", "log", "--format=%H %ad", "--date=format:%Y-%m-%d", "--", SUIVI],
        cwd=RACINE.parent, capture_output=True, text=True, check=True,
    ).stdout.split("\n")

    for ligne in reversed([l for l in journal if l.strip()]):
        commit, jour = ligne.split(" ", 1)
        contenu = subprocess.run(
            ["git", "show", f"{commit}:{SUIVI}"],
            cwd=RACINE.parent, capture_output=True, text=True,
        )
        if contenu.returncode != 0:
            continue
        try:
            yield jour.strip(), json.loads(contenu.stdout)["articles"]
        except (ValueError, KeyError):
            continue


def main():
    options = argparse.ArgumentParser(description=__doc__)
    options.add_argument("--ecrire", action="store_true",
                         help="ajouter les repêchés à l'index")
    arguments = options.parse_args()

    index = json.loads(SORTIE.read_text(encoding="utf-8"))
    connus = {article["id"] for article in index["articles"]}

    # Le dernier jour où chaque article a été vu, et son état à ce moment-là.
    oubliés = {}
    for jour, articles in relevés_passés():
        for article in articles:
            if article["id"] in connus:
                continue
            oubliés[article["id"]] = (jour, article)

    if not oubliés:
        print("Rien à repêcher.", file=sys.stderr)
        return 0

    repêchés = []
    for jour, article in oubliés.values():
        garde = dict(article)
        garde["en_ligne"] = False
        garde["vu_le"] = jour
        garde.setdefault("disparu_le", jour)
        garde.pop("recherche", None)
        repêchés.append(garde)

    print(f"{len(repêchés)} article(s) retrouvé(s) dans l'historique :",
          file=sys.stderr)
    for garde in sorted(repêchés, key=lambda a: a["titre"])[:8]:
        print(f"  {garde['titre'][:58]} — {garde['taille'] or 'sans taille'}",
              file=sys.stderr)
    if len(repêchés) > 8:
        print(f"  … et {len(repêchés) - 8} autres", file=sys.stderr)

    if not arguments.ecrire:
        print("\n(essai seulement — relancez avec --ecrire pour les ajouter)",
              file=sys.stderr)
        return 0

    index["articles"] = sorted(index["articles"] + repêchés,
                               key=lambda a: -a["id"])
    index["total"] = len(index["articles"])
    index["hors_ligne"] = sum(
        1 for a in index["articles"] if not a.get("en_ligne", True))
    index["en_ligne"] = index["total"] - index["hors_ligne"]
    SORTIE.write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")
    print(f"\nIndex à {index['en_ligne']} en ligne "
          f"et {index['hors_ligne']} hors ligne.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
