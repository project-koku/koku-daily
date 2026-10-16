# Read replica reporting

Tenant discovery, tenant scans, metadata joins, and report aggregation use the
RO engine. Each schema's complete result is fetched inside its own read-only
transaction; the connection is returned before the next schema or retry delay.
Python retains intermediate rows. PostgreSQL on RO performs final joins and
aggregations using typed, bound JSON recordsets; no temporary tables are created.
Explicit casts preserve the old staging-table rounding and column types.

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
(`koku-db-ro` in Stage). Both scheduled jobs read `DATABASE_RO_HOST` and
`DATABASE_RO_PORT` from that secret's `db.host` and `db.port` keys. This follows
Koku's existing replica configuration without hardcoding the generated hostname.
Clowder's primary username, password and database name are shared by both
connections. Ensure network access and SELECT privileges on the replica. The
existing Clowder database configuration supplies RW access for final upserts.
The replica secret is required; applying code alone does not establish or verify
live replica wiring.

## Operational settings

| Variable | Default | Meaning |
| --- | --- | --- |
| REPLICA_RETRY_ATTEMPTS | 3 | Total attempts per replica read for confirmed recovery conflicts |
| REPLICA_RETRY_DELAY | 1 | Seconds between attempts, outside any transaction |
| REPORT_STATEMENT_TIMEOUT_MS | 5000 | Transaction-local RW statement timeout |
| REPORT_LOCK_TIMEOUT_MS | 1000 | Transaction-local RW lock timeout |

Retry attempts, ports, and timeouts must be positive integers; delay
must be finite and nonnegative. Cutoff, tenant discovery, totals aggregation,
history and final report reads use the same bounded recovery retries. Each failed
read transaction rolls back and releases its connection before the retry delay.
Exhausting retries on these global reads fails the job; no empty result is
substituted. Totals already committed before a later report failure remain saved. Only database errors whose code and server
diagnostic identify a recovery conflict are retried. User cancellations and
other SQL/connectivity failures propagate. A canceled schema publishes no rows
until a complete read succeeds. A schema exhausting its retries is logged as
incomplete, subsequent schemas continue, and aggregate daily persistence is
suppressed to avoid replacing complete historical totals with partial inputs.
Affected report output can be partial; operators must inspect the incomplete-run
logs. Schemas absent before their query are logged and skipped as before.

All-customer monthly totals overlay this run's daily values onto historical rows
read from RO. This avoids waiting for the new upserts to replay and prevents
double counting stale values for the same dates. It does not provide a single
snapshot across all tenants or hide unrelated replication lag in historical
data. The intermediate datasets occupy Python memory; measure the job with
representative tenant counts before production rollout.

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
