# Read replica reporting

Tenant discovery, tenant scans, metadata reads, and ordinary report queries use
RO PostgreSQL transactions. Server-side cursors fetch at most 500 rows per batch
into a disposable SQLite database on the pod's writable filesystem. Each tenant
attempt has its own SQLite savepoint: a failed read leaves no staged rows before
retrying. The PostgreSQL transaction closes before any retry delay.

Reports over staged data use local SQLite queries, with exact Decimal sum/max
functions instead of SQLite floating-point arithmetic. Numeric inputs use TEXT
affinity; a schema codec restores Decimal values and dates without global adapter
registrations. Cost-model JSON remains nullable raw text, preserving SQL NULL,
JSON null and exact JSON numbers. Source-query casts still preserve the former
PostgreSQL temporary-table rounding and column types. The parity suite compares
local report queries with the original PostgreSQL implementation.

No PostgreSQL temporary tables or whole-dataset JSON parameters are used. Output
rows stay on disk, CSV writing and Parquet conversion stream, and `job.py` closes
the report bundle after delivery (including failure) to remove its scratch files.

The RW engine is acquired only to upsert final rows into the existing
`public.__customer_total_data`. No table migration is required. All calculated dates
are upserted in one statement within one transaction, preserving the previous
all-or-nothing write behavior. A failure rolls back the complete totals write
and fails the job; rerunning is idempotent. Historical dates
outside the newly calculated range remain intact.

## Connections and deployment

`DATABASE_RO_HOST` is required. There is no inferred hostname or automatic RW
fallback. `DATABASE_RO_PORT` defaults to the primary port. `DATABASE_RO_USER`,
`DATABASE_RO_PASSWORD`, and `DATABASE_RO_NAME` default to the corresponding
primary settings, which come from Clowder when enabled or `DATABASE_*` otherwise.
Set those RO variables to use separate credentials or a separate database name.
Each read transaction explicitly runs `SET TRANSACTION READ ONLY`, including
development environments where an explicit RO endpoint points at a primary.

Both engines use the configured RDS CA when Clowder supplies it, otherwise the
existing `/etc/ssl/certs/server.pem`, with `sslmode=verify-full` when present.
URLs are constructed with SQLAlchemy's URL API so special password characters
are preserved, and parameter values are hidden from SQLAlchemy exception output.
Do not log environment dumps or connection URLs.

The locked app-common-python database configuration supplies a primary endpoint
only. Before deploying this version, app-interface must supply the existing RDS
replica secret name as the `KOKU_READ_ONLY_DB` ClowdApp template parameter
(default `koku-db-ro`, matching Stage). The default lets Bonfire process the
template without an additional parameter; it does not create a replica secret.
Override it when the replica secret has a different name. Both scheduled jobs read `DATABASE_RO_HOST` and
`DATABASE_RO_PORT` from that secret's `db.host` and `db.port` keys. This follows
Koku's existing replica configuration without hardcoding the generated hostname.
Clowder's primary username, password and database name are shared by both
connections. Ensure network access and SELECT privileges on the replica. The
existing Clowder database configuration supplies RW access for final upserts.
The replica secret and both keys are required when a job starts; an ephemeral
environment must provide them before invoking the reporting job. There is no
primary fallback. Applying code alone does not establish or verify live replica
wiring.

## Operational settings

| Variable | Default | Meaning |
| --- | --- | --- |
| REPLICA_RETRY_ATTEMPTS | 3 | Total attempts per replica read for confirmed recovery conflicts |
| REPLICA_RETRY_DELAY | 1 | Seconds between attempts, outside any transaction |
| REPORT_STATEMENT_TIMEOUT_MS | 5000 | Transaction-local RW statement timeout |
| REPORT_LOCK_TIMEOUT_MS | 1000 | Transaction-local RW lock timeout |
| REPORT_STAGING_DIR | Python temporary directory, normally `/tmp` | Parent of a unique disposable run directory |

Retry attempts, ports, and timeouts must be positive integers; delay
must be finite and nonnegative. Cutoff, tenant discovery, metadata, history and
direct report reads use the same bounded recovery retries. Each failed
read transaction rolls back and releases its connection before the retry delay.
Exhausting retries on these global reads fails the job; no empty result is
substituted. Only database errors whose code and server diagnostic identify a
recovery conflict are retried. User cancellations and other SQL/connectivity
failures propagate. A canceled schema contributes no rows until its read succeeds.
A schema exhausting retries is logged as incomplete; remaining schemas are still
scanned, and completeness is tracked separately for each setup dataset.

Only cloud costs, OCP costs and OCP infrastructure inputs control daily totals
persistence. If any is incomplete, the totals aggregation and upsert are skipped.
Failures in tags or weekly node/cost-model inputs do not suppress an otherwise
complete atomic totals write. However, any incomplete required setup causes
`IncompleteReportInputs` before CSV generation, so `job.py` exits unsuccessfully
without email, S3, Prometheus or Pushgateway delivery. Partial current totals are
never overlaid onto historical values. Complete totals already committed before
an unrelated input or later reporting failure remain saved. Schemas absent before
their query are logged and skipped as before.

All-customer monthly totals overlay this run's daily values onto historical rows
read from RO. This avoids waiting for the new upserts to replay and prevents
double counting stale values for the same dates. It does not provide a single
snapshot across all tenants or hide unrelated replication lag in historical
data.

## Scratch storage and memory

Default container `/tmp` is sufficient; no PVC, additional volume, or deployment
change is required. `REPORT_STAGING_DIR` optionally selects another existing,
writable parent and sets `TMPDIR` and `SQLITE_TMPDIR` before SQLite work. An invalid
configured directory fails rather than falling back. Run directories are unique;
abandoned databases are never reused. SQLite uses a 16 MiB page-cache target,
file-backed temporary work, cache spilling, DELETE journaling and exclusive
locking. Durability syncs are disabled because scratch is rebuilt after failure;
transaction rollback remains enabled. Disk-full and other SQLite errors fail the
job and block delivery; previously committed valid totals may remain.

The page-cache target is not a pod memory cap. Linux file cache also counts toward
cgroup memory and can be reclaimed. Email attachment encoding and the Prometheus
registry retain their existing memory costs. Production capacity must account for
SQLite, its journal and sort files, CSV, Parquet, ZIP and other container files;
the writable layer is node-local ephemeral storage, subject to available node
capacity and disk-pressure eviction when no storage request/limit is configured.
Synthetic pod measurements are recorded separately from real tenant sizing.

## Local checks

Install the runtime dependencies from `Pipfile.lock` in a Python 3.11 environment,
then install the test dependencies and run the suite:

```sh
python -m pip install pytest==9.0.3 hypothesis==6.140.3
docker compose -f tests/postgres-compose.yaml up -d --wait
python -m pytest -q
docker compose -f tests/postgres-compose.yaml down
```

The integration harness uses disposable PostgreSQL
16 primary and physical standby containers with host ports 25435/25436 bound to
127.0.0.1. It never uses production database credentials or delivery services.
The fixtures contain test data only. `docker compose -f tests/postgres-compose.yaml
down` removes the temporary containers; their databases live in tmpfs.

Only SQL modified by this change has an original copy under
`tests/fixtures/legacy_sql`. The parity harness explicitly selects these frozen
queries and shares unchanged queries from `kokudaily/sql`; missing frozen files
fail rather than falling back. This compares the old staging logic with the new
replica path without duplicating every report query. Integration checks cover
paused WAL replay, recovery conflicts, and lock contention. Future query changes
need a baseline fixture if they are to be checked against their prior behavior.
