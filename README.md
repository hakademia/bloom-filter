# Bloom Filter — Demo Interactive

> Démonstration visuelle et interactive d'un Bloom Filter from scratch, avec PostgreSQL comme source de vérité et une interface temps réel qui montre le double hashing bit par bit.

A community project developed within **Hakademia**.

## Overview

Un Bloom Filter est une structure de données probabiliste qui répond à la question "est-ce que cet élément a déjà été vu ?" de façon ultra-rapide et en très peu de mémoire — mais avec une possibilité de faux positifs.

Ce projet démontre concrètement :
- comment le filtre est construit from scratch en Python (BLAKE2b + double hashing)
- comment PostgreSQL sert de vérificateur exact quand le filtre dit "peut-être"
- comment les paramètres `n`, `p`, `k` et `m` s'influencent mutuellement
- comment un faux positif se produit visuellement sur le bit array

**Pour qui ?** Développeurs, étudiants, ou toute personne qui veut comprendre les Bloom Filters par la pratique.

## Features

- Visualisation du bit array en temps réel à chaque frappe (debounce 300ms)
- Décomposition du double hashing : `h1 + i × h2 mod m` pour chaque position
- Panneau de configuration interactif : sliders pour `n`, `p`, override de `k`
- Formules `m` et `k` calculées en direct avec les équations exactes
- 4 états de verdict : ✅ absent / 🟣 confirmé / ⚠️ faux positif / ❓ en attente
- **Double moteur DB** : PostgreSQL (Docker) avec bascule automatique vers SQLite local (`bloom.db`) si Docker est éteint
- **Métriques en direct** : Micro-benchmarks temps réel (temps Bloom en µs vs temps DB en ms, détection des requêtes évitées)
- Échantillon de données propre et léger (`dataset/users_sample.csv` de 2 500 entrées) avec auto-seeding

## Architecture

```
index.html  ──(fetch)──►  server.py (FastAPI)  ──►  Bloom Filter (mémoire)
                                │                         ▲
                                ├──────────────►  PostgreSQL (Docker)
                                │                 ou SQLite (local)
                                └──────────────►  (source de vérité)
```

Au démarrage :
1. `server.py` se connecte à PostgreSQL si disponible, ou initialise SQLite (`bloom.db`)
2. Si la base est vide, elle est automatiquement peuplée depuis `dataset/users_sample.csv`
3. Le Bloom Filter est reconstruit en mémoire en streaming par lots
4. Chaque requête passe d'abord par le filtre (quelques microsecondes) : si absent, la requête SQL est évitée !

## Getting started

### Requirements

- Python 3.10+
- *(Optionnel)* Docker Desktop pour exécuter PostgreSQL (si non installé, SQLite local prend le relais sans configuration)
- Un navigateur moderne (Chrome, Firefox, Edge)

### Installation

```bash
# 1. Cloner le repo
git clone https://github.com/hakademia/bloom-filter.git
cd bloom-filter

# 2. Installer les dépendances Python
pip install -r requirements.txt

# 3. (Optionnel) Lancer PostgreSQL avec Docker
docker-compose up -d

# 4. Charger les données dans la DB (auto-détecte PostgreSQL ou SQLite)
python seed.py --limit 1000

# 5. Lancer le serveur API
python server.py
```

### Usage

```bash
# Ouvrir l'interface dans le navigateur
# Double-clic sur index.html ou ouvrir via Live Server

# Tester le Bloom Filter seul (sans DB)
python bloom_filter.py

# Recharger les données (options personnalisées)
python seed.py --limit 2500 --db auto
```

### API disponible

| Route | Méthode | Description |
|---|---|---|
| `/hashes?text=xxx` | GET | Positions de hash en temps réel |
| `/check` | POST | Vérifie présence (bloom + DB) |
| `/insert` | POST | Insère dans le filtre + DB |
| `/configure` | POST | Reconfigure n, p, k |
| `/state` | GET | Bit array complet + stats |
| `/reset` | DELETE | Vide le filtre et la DB |

## Project credits

**Original creator:** [@your-github-username](https://github.com/your-github-username)  
**Maintained by:** [Project maintainers](AUTHORS.md)  
**Community:** [Hakademia](https://github.com/hakademia)

This repository is hosted within Hakademia. Hosting alone does not determine copyright ownership or authorship. See [AUTHORS.md](AUTHORS.md) for individual credits.

## Contributing

Contributions are welcome! Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening an issue or pull request.

## License

This project is licensed under the [MIT License](LICENSE).
