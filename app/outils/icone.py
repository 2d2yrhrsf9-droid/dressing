#!/usr/bin/env python3
"""Dessine l'icône de l'app : un cintre blanc sur fond sarcelle.

Écrit directement le PNG, sans dépendance — il n'y a ni Pillow ni convertisseur
SVG sur la machine. Le tracé est antialiasé par sur-échantillonnage.

    python3 outils/icone.py
"""

import math
import struct
import zlib
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"

FOND = (9, 118, 129)       # sarcelle Vinted, assombri pour le contraste
TRAIT = (255, 255, 255)
ECHANTILLONS = 4           # 4×4 sous-pixels


def distance_segment(point, depart, arrivee):
    (px, py), (ax, ay), (bx, by) = point, depart, arrivee
    dx, dy = bx - ax, by - ay
    longueur = dx * dx + dy * dy
    if longueur == 0:
        return math.hypot(px - ax, py - ay)
    avance = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / longueur))
    return math.hypot(px - (ax + avance * dx), py - (ay + avance * dy))


def dans_le_cintre(x, y):
    """Vrai si le point (en coordonnées 0–1) tombe sur le tracé."""
    epaisseur = 0.030

    # Le crochet : un arc ouvert vers le bas, que la tige traverse.
    centre, rayon = (0.5, 0.295), 0.082
    ecart = abs(math.hypot(x - centre[0], y - centre[1]) - rayon)
    angle = math.degrees(math.atan2(y - centre[1], x - centre[0]))
    if ecart < epaisseur and not 40 < angle < 140:
        return True

    # La tige qui descend du crochet vers l'épaule.
    if distance_segment((x, y), (0.5, 0.295), (0.5, 0.46)) < epaisseur:
        return True

    # Les deux épaules et la barre du bas.
    for depart, arrivee in (
        ((0.5, 0.455), (0.155, 0.665)),
        ((0.5, 0.455), (0.845, 0.665)),
        ((0.155, 0.665), (0.845, 0.665)),
    ):
        if distance_segment((x, y), depart, arrivee) < epaisseur:
            return True
    return False


def rendre(cote):
    lignes = []
    for pixel_y in range(cote):
        ligne = bytearray()
        for pixel_x in range(cote):
            touche = 0
            for sous_y in range(ECHANTILLONS):
                for sous_x in range(ECHANTILLONS):
                    x = (pixel_x + (sous_x + 0.5) / ECHANTILLONS) / cote
                    y = (pixel_y + (sous_y + 0.5) / ECHANTILLONS) / cote
                    if dans_le_cintre(x, y):
                        touche += 1
            melange = touche / (ECHANTILLONS * ECHANTILLONS)
            for fond, trait in zip(FOND, TRAIT):
                ligne.append(round(fond + (trait - fond) * melange))
        lignes.append(bytes(ligne))
    return lignes


def ecrire_png(chemin, lignes, cote):
    brut = b"".join(b"\x00" + ligne for ligne in lignes)

    def bloc(nom, donnees):
        entete = nom + donnees
        return (
            struct.pack(">I", len(donnees))
            + entete
            + struct.pack(">I", zlib.crc32(entete) & 0xFFFFFFFF)
        )

    chemin.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + bloc(b"IHDR", struct.pack(">IIBBBBB", cote, cote, 8, 2, 0, 0, 0))
        + bloc(b"IDAT", zlib.compress(brut, 9))
        + bloc(b"IEND", b"")
    )


def main():
    WEB.mkdir(parents=True, exist_ok=True)
    for cote in (180, 192, 512):
        chemin = WEB / f"icone-{cote}.png"
        ecrire_png(chemin, rendre(cote), cote)
        print(f"{chemin.name} — {chemin.stat().st_size / 1024:.1f} Ko")


if __name__ == "__main__":
    main()
