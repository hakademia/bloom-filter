# Contributing to Bloom Filter Demo

Thank you for contributing to a Hakademia community project!

## Before you start

1. Read the README and check existing issues and pull requests.
2. For substantial changes, open an issue first to discuss the approach.
3. Be respectful, constructive, and welcoming in discussions and reviews.
4. Never commit passwords, API keys, personal data, or other secrets.
5. Ne jamais committer le fichier `dataset/users.csv` s'il contient des données personnelles réelles.

## Development workflow

1. Fork the repository or create a branch if you have write access.
2. Use a descriptive branch name, such as `feat/add-parser` or `fix/login-error`.
3. Make focused changes and include tests or documentation when relevant.
4. Write clear commits explaining what changed.
5. Open a pull request using the provided template.
6. Address review feedback before merging.

## Commit conventions

Ce projet suit le format **Conventional Commits** :

```
<type>(<scope>): <description courte>

Types : feat | fix | docs | refactor | chore
Scope : filter | server | frontend | db | seed | config

Exemples :
  feat(filter): add k override support
  fix(server): rebuild bloom filter from DB on startup
  docs(readme): add installation instructions
  chore(db): add seed script for CSV loading
```

## Branch naming

```
feat/<description>   → nouvelle fonctionnalité
fix/<description>    → correction de bug
docs/<description>   → documentation uniquement
refactor/<description> → refactoring sans changement de comportement
```

## Pull request expectations

- Explain the purpose and scope of the change.
- Link any related issue.
- Explain how you tested the change.
- Include screenshots for UI changes where helpful.
- Keep unrelated changes in separate pull requests.

## Recognition

We preserve the original creator's attribution and acknowledge maintainers and contributors in [AUTHORS.md](AUTHORS.md) and Git history. If you believe credits are missing or inaccurate, open an issue or contact a maintainer.

## Licensing contributions

By submitting a contribution, you agree that it may be distributed under this repository's stated license. Only contribute code and other material you have the right to submit.
