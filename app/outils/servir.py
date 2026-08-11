#!/usr/bin/env python3
"""Sert le dossier web/ en local, pour essayer l'app.

    python3 outils/servir.py [port]

Affiche aussi l'adresse à taper sur l'iPhone quand il est sur le même réseau
Wi-Fi que ce Mac. Sans dépendance.
"""

import http.server
import os
import socket
import socketserver
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"


class Silencieux(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".webmanifest": "application/manifest+json",
        ".json": "application/json",
    }

    def end_headers(self):
        # Pas de cache côté navigateur : c'est le service worker qui gère la
        # persistance, et pendant la mise au point on veut voir ses changements.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format, *arguments):
        pass


def adresse_locale():
    prise = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        prise.connect(("8.8.8.8", 80))
        return prise.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        prise.close()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8137
    os.chdir(WEB)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), Silencieux) as serveur:
        print(f"Sur ce Mac      : http://localhost:{port}/")
        print(f"Sur l'iPhone    : http://{adresse_locale()}:{port}/")
        print("Ctrl+C pour arrêter.")
        sys.stdout.flush()
        serveur.serve_forever()


if __name__ == "__main__":
    main()
