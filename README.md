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
- 4 états de verdict : ✅ absent / 🟣 confirmé / ⚠️ faux positif / ❓ peut-être
- PostgreSQL comme index exact pour confirmer ou infirmer le filtre
- Chargement de ~5 000 usernames réels depuis un CSV au démarrage

## Architecture

```
index.html  ──(fetch)──►  server.py (FastAPI)  ──►  Bloom Filter (mémoire)
                                │                         ▲
                                └──────────────►  PostgreSQL (Docker)
                                                    (source de vérité)
```

Au démarrage :
1. `seed.py` charge `dataset/users.csv` dans PostgreSQL
2. `server.py` reconstruit le Bloom Filter en mémoire depuis la DB
3. Chaque requête passe d'abord par le filtre, puis par la DB si nécessaire

## Getting started

### Requirements

- Python 3.10+
- Docker Desktop
- Un navigateur moderne (Chrome, Firefox, Edge)

### Installation

```bash
# 1. Cloner le repo
git clone https://github.com/hakademia/bloom-filter.git
cd bloom-filter

# 2. Installer les dépendances Python
pip install -r requirements.txt

# 3. Lancer PostgreSQL
docker-compose up -d

# 4. Charger les données dans la DB (une seule fois)
python seed.py

# 5. Lancer le serveur
python server.py
```

### Usage

```bash
# Ouvrir l'interface dans le navigateur
# (double-clic sur index.html ou ouvrir via un serveur local)

# Tester le Bloom Filter seul (sans DB)
python bloom_filter.py

# Recharger les données si la DB est vide
python seed.py
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
