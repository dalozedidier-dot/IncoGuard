# FluxGuard

Workflows quick-wins (objectif: <10–15% flakes) dans `.github/workflows/blank.yml`:
- `runs-on: ubuntu-22.04`
- retry automatique `nick-fields/retry@v3` (3 tentatives)
- libère du disque via `jlumbroso/free-disk-space@v1.3.1`
- debug avant/après (df, free, ImageOS, runner-version)
- `continue-on-error: true` temporaire sur le smoke (monitoring non bloquant)
