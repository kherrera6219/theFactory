# Object store: MinIO → SeaweedFS

Document version: 2026.09.27
Status: Implemented (compose default); local data migration is an operator step
Audience: Maintainers and operators

## Why

Weekly Qualification failed on 2026-09-14 and 2026-09-21 before the canary ran:

```
pull access denied for minio/minio, repository does not exist
```

This was not a pinning mistake. Four facts, all checked on 2026-09-27:

| Fact | Evidence |
|---|---|
| The `minio/minio` Docker Hub repository no longer exists | Hub API `object not found`; `docker manifest inspect` denied |
| `github.com/minio/minio` is **archived** | GitHub API `archived=true` |
| Its 2026 advisories are fixed only in commercial AIStor releases | CVE-2026-41145 / CVE-2026-40344 (HIGH, *unauthenticated object write*), CVE-2026-34204, CVE-2026-42600: the patched tags do not exist in the public repo |
| The service holds COMPLIANCE-mode, legal-hold audit artifacts | `object_store.put_audit_report` |

An unauthenticated-write bug in the store that holds the audit trail is not
something to re-pin and live with. The server was replaced.

## Choice: SeaweedFS 4.47, pinned by digest

Candidates were chosen by running the same Object Lock conformance probe against
each. The probe exercises exactly what `object_store.py` relies on, plus the two
properties that make a lock a lock:

| Check | MinIO (baseline) | SeaweedFS 4.47 | VersityGW 1.8.0 |
|---|---|---|---|
| `create_bucket(ObjectLockEnabledForBucket)` | PASS | PASS | PASS |
| lock configuration reads back `Enabled` | PASS | PASS | PASS |
| `put_object` COMPLIANCE + legal hold | PASS | PASS | PASS |
| legal hold / retention read back | PASS | PASS | PASS |
| **delete of a locked version refused** | PASS | PASS | PASS |
| **shortening COMPLIANCE retention refused** | PASS | PASS | PASS |
| list, get, presigned GET | PASS | PASS | PASS |
| unlocked bucket → `ObjectLockConfigurationNotFoundError` | PASS | PASS | PASS |
| lock + refusal survive a container restart | — | PASS | not tested |

SeaweedFS was chosen over VersityGW for maturity and scale-out (it is a
distributed store, not a gateway over a POSIX directory). Both are Apache-2.0,
which also removes MinIO's AGPL from the stack. RustFS was not evaluated to
completion; it is the youngest of the three.

## What changed

| Before | After |
|---|---|
| service `minio` | service `object-store` (network alias `minio` kept so an old `.env` still resolves) |
| `minio/minio:RELEASE.2025-09-07T16-13-09Z` | `chrislusf/seaweedfs:4.47@sha256:ce9e796f…` |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | the server reads `OBJECT_STORAGE_ACCESS_KEY` / `OBJECT_STORAGE_SECRET_KEY` — the same values the orchestrator signs with, so they cannot drift |
| dev defaults `minioadmin` / `minioadmin123` | `factory-object-store` / `CHANGE_ME_local_dev_object_store_secret`; production refuses both old and new defaults and any `CHANGE_ME*` secret |
| `MINIO_HOST_BIND` / `MINIO_HOST_PORT` / console `:9001` | `OBJECT_STORE_HOST_BIND` / `OBJECT_STORE_HOST_PORT`; no web console |
| volume `minio-data` | volume `object-store-data`; `minio-data` is **no longer declared**, so `down -v` cannot delete the pre-migration evidence |

The S3 API, port 9000, the bucket names and every orchestrator code path are
unchanged. `OBJECT_STORAGE_ENDPOINT` defaults to `http://object-store:9000`.

## Migrating an existing local stack

The old volume is MinIO's on-disk format; SeaweedFS cannot read it directly. The
objects are copied over S3 by `scripts/migrate_object_store.py`, which:

- only ever **reads** the source;
- is a **dry run** unless `--execute` is given;
- recreates each object with the **same** retention mode, retain-until date and
  legal hold, then reads it back and verifies bytes and lock state;
- refuses to copy locked objects into a destination bucket without Object Lock;
- never overwrites different bytes at the destination, and is idempotent;
- takes credentials only from `MIGRATE_SOURCE_*` / `MIGRATE_DEST_*` environment
  variables.

Steps (do not run while a mission batch is in flight):

1. Leave the running `deploy-minio-1` container up; it still serves the old data
   on `127.0.0.1:9000`.
2. Start the new store beside it on another host port:
   `OBJECT_STORE_HOST_PORT=9010 docker compose --env-file .env -f deploy/docker-compose.yaml up -d object-store`
3. Dry run, then execute:

   ```
   MIGRATE_SOURCE_ACCESS_KEY=<old MINIO_ROOT_USER> MIGRATE_SOURCE_SECRET_KEY=<old MINIO_ROOT_PASSWORD> \
   MIGRATE_DEST_ACCESS_KEY=<OBJECT_STORAGE_ACCESS_KEY> MIGRATE_DEST_SECRET_KEY=<OBJECT_STORAGE_SECRET_KEY> \
   python scripts/migrate_object_store.py --source-endpoint http://127.0.0.1:9000 \
     --dest-endpoint http://127.0.0.1:9010 --bucket <OBJECT_STORAGE_BUCKET> [--execute]
   ```

   Repeat for any other bucket (e.g. the pre-2026-08-05 unlocked
   `mission-audit-artifacts`, the rollback bucket).
4. In `.env`: point `OBJECT_STORAGE_ENDPOINT` at `http://object-store:9000`,
   delete the `MINIO_*` lines, and unset `OBJECT_STORE_HOST_PORT`.
5. Stop and remove the old container (`docker rm -f deploy-minio-1`) and bring
   the stack up. **Keep the `deploy_minio-data` volume** until the retention
   dates of the objects it holds have passed.

Live-verified on 2026-09-27 against throwaway containers: two COMPLIANCE objects
(one with legal hold) copied with identical retain-until dates and hold status,
deletes refused on the destination, a second run skipped both as identical.
