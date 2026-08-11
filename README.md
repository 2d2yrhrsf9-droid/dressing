# Le dressing

Une petite app pour l'iPhone de Flavie, qui permet de fouiller ses annonces
Vinted comme Vinted ne le permet pas : par taille, par genre, par type de
vêtement, par marque, et en croisant tout cela.

Vinted n'offre, sur une page de membre, qu'un filtre par catégorie. Pas de
recherche par taille, pas de recherche textuelle dans son propre dressing,
aucun croisement. Or l'essentiel du stock est du vêtement de bébé, où la
question posée est presque toujours la même : « qu'est-ce qu'il me reste en
6-9 mois pour un garçon ? »

## Ce que ça fait

- **Chercher** — un champ de recherche sur le titre, la marque et la
  catégorie, plus des filtres cumulables : genre, taille, type, marque, état,
  rayon. Chaque option affiche le nombre d'articles derrière elle, calculé en
  tenant compte des autres filtres déjà posés.
- **Tailles** — un tableau d'ensemble, taille par taille et genre par genre.
  Toucher un nombre bascule sur la liste correspondante.
- **Rangement** — sur chaque article, un emplacement libre (« carton 3 »,
  « penderie du bas ») pour retrouver l'objet quand il se vend. Vinted n'a rien
  de tel. Ces notes restent **dans le téléphone** ; l'écran « À propos » permet
  de les exporter.
- **Hors réseau** — une fois ouverte, l'app fonctionne sans connexion :
  l'index et les photos déjà vues sont conservés dans le téléphone.

L'app ne modifie rien sur Vinted. Pour changer un prix ou une description, il
faut toujours passer par l'application Vinted.

## Comment c'est fait

    indexeur.py   →   web/index.json   →   l'app dans le navigateur

`indexeur.py` interroge l'API publique de Vinted et écrit un fichier `index.json`
que l'app se contente de lire. Cette séparation n'est pas un choix
d'architecture, c'est une contrainte : **l'API Vinted ne renvoie aucun en-tête
CORS**, donc du JavaScript ne peut pas l'interroger depuis un navigateur. Il
faut un programme hors navigateur pour aller chercher les annonces.

Le profil étant public, aucun compte ni mot de passe n'est nécessaire : une
visite de la page d'accueil suffit à obtenir les cookies de session.

Deux choses ne figurent pas dans la réponse de l'API : la catégorie et le genre.
On les obtient en filtrant le dressing catalogue par catalogue, de haut en bas
de l'arbre Vinted (`--complet`, une centaine de requêtes, une vingtaine de
minutes). Ce classement n'est fait qu'une fois ; ensuite l'indexeur ne s'occupe
que des nouveautés, en lisant le fil d'Ariane de leur annonce.

Vinted limite fortement le débit des requêtes ; l'indexeur ralentit et reprend
tout seul.

## Usage

    python3 app/indexeur.py              # met l'index à jour
    python3 app/indexeur.py --complet    # reclasse tout depuis zéro
    python3 app/outils/servir.py         # essayer l'app sur ce Mac
    python3 app/outils/icone.py          # redessiner l'icône

Aucune dépendance : bibliothèque standard de Python uniquement.

`servir.py` affiche aussi l'adresse à taper sur l'iPhone quand il est sur le
même réseau Wi-Fi — pratique pour essayer, mais ce Mac doit alors rester
allumé.

## Installer sur l'iPhone

L'app doit être servie par une adresse web : iOS n'installe pas sur l'écran
d'accueil un fichier posé dans le téléphone. Une fois la page ouverte dans
Safari : bouton **Partager**, puis **Sur l'écran d'accueil**.

Le fichier `.github/workflows/indexer.yml` permet de tout faire tenir sur
GitHub : les pages sont publiées par GitHub Pages, et l'indexeur est relancé
chaque nuit par GitHub Actions. Rien ne tourne alors à la maison. Attention,
la page serait publique — le dressing l'est déjà sur Vinted, mais les
emplacements de rangement, eux, ne quittent jamais le téléphone.

## Le dossier

    app/indexeur.py         construit l'index depuis Vinted
    app/outils/servir.py    petit serveur local pour essayer
    app/outils/icone.py     dessine les icônes PNG
    app/web/                l'app : index.html, app.css, app.js, sw.js
    app/web/index.json      l'index (produit, mais versionné : c'est ce que
                            l'app lit une fois déployée)
    reconnaissance/         le relevé du premier classement, gardé comme
                            amorce pour éviter de refaire les 20 minutes
