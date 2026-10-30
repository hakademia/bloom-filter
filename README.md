# Bloom Filter — Interactive Demo

> Visual and interactive demonstration of a from-scratch Bloom Filter, with PostgreSQL as the source of truth and a real-time interface showcasing bit-by-bit double hashing.

A community project developed within **Hakademia**.

![Bloom Filter Interactive Dashboard](assets/Minimal%20Bloom%20Filter%20Dashboard.png)

## Overview

A Bloom Filter is a space-efficient probabilistic data structure used to test whether an element is a member of a set. It answers the question "has this item been seen before?" ultra-fast and using very little memory — with a controllable probability of false positives.

This project demonstrates:
- How the filter is built from scratch in Python (BLAKE2b + double hashing)
- How PostgreSQL serves as the exact ground-truth verifier when the filter says "maybe"
- How parameters `n`, `p`, `k`, and `m` influence each other
- How false positives visually manifest on the bit array

**Who is it for?** Developers, students, or anyone who wants to learn Bloom Filters through hands-on practice.

## Features

- Real-time bit array visualization on every keystroke (300ms debounce)
- Step-by-step double hashing decomposition: `h1 + i × h2 mod m` for each hash position
- Interactive configuration panel: sliders for `n`, `p`, and manual override for `k`
- Exact mathematical formulas computed live for `m` and `k`
- 4 clear verdict states: ✅ Absent / 🟣 Confirmed / ⚠️ False positive / ❓ Pending
- **Dual database engine**: PostgreSQL (Docker) with automatic fallback to local SQLite (`bloom.db`) if Docker is offline
- **Live performance metrics**: Real-time micro-benchmarks (Bloom lookup in µs vs DB query in ms, tracking avoided queries)
- Clean and lightweight sample dataset (`dataset/users_sample.csv` with 2,500 rows) with auto-seeding

## Architecture

```
index.html  ──(fetch)──►  server.py (FastAPI)  ──►  Bloom Filter (in-memory)
                                │                         ▲
                                ├──────────────►  PostgreSQL (Docker)
                                │                 or SQLite (local)
                                └──────────────►  (source of truth)
```

On startup:
1. `server.py` connects to PostgreSQL if available, or initializes local SQLite (`bloom.db`)
2. If the database is empty, it automatically populates from `dataset/users_sample.csv`
3. The Bloom Filter is rebuilt in memory using streamed batch loading
4. Every query checks the filter first (microseconds): if absent, the SQL query is skipped entirely!

## Getting started

### Requirements

- Python 3.10+
- *(Optional)* Docker Desktop to run PostgreSQL (if not installed, local SQLite takes over seamlessly with zero configuration)
- A modern web browser (Chrome, Firefox, Edge, Safari)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/hakademia/bloom-filter.git
cd bloom-filter

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. (Optional) Start PostgreSQL with Docker
docker-compose up -d

# 4. Seed sample data into the database (auto-detects PostgreSQL or SQLite)
python seed.py --limit 1000

# 5. Start the API server
python server.py
```

### Usage

```bash
# Open the web interface in your browser
# Double-click index.html or open via VS Code Live Server

# Test the Bloom Filter standalone (without DB)
python bloom_filter.py

# Reload data with custom options
python seed.py --limit 2500 --db auto
```

### Available API Endpoints

| Route | Method | Description |
|---|---|---|
| `/hashes?text=xxx` | GET | Real-time hash bit positions |
| `/check` | POST | Check presence (Bloom filter + DB verification) |
| `/insert` | POST | Insert into both Bloom filter and DB |
| `/configure` | POST | Reconfigure parameters n, p, k |
| `/state` | GET | Full bit array snapshot + filter statistics |
| `/reset` | DELETE | Reset and wipe both filter and DB |

## Project credits

**Original creator:** [@AaronDAmin](https://github.com/AaronDAmin) (Aaron Vyaleveka)  
**Maintained by:** [Project maintainers](AUTHORS.md)  
**Community:** [Hakademia](https://github.com/hakademia)

This repository is hosted within Hakademia. Hosting alone does not determine copyright ownership or authorship. See [AUTHORS.md](AUTHORS.md) for individual credits.

## Contributing

Contributions are welcome! Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening an issue or pull request.

## License

This project is licensed under the [MIT License](LICENSE).
