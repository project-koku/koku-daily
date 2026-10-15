# Read replica reporting

Tenant discovery, tenant scans, metadata joins, and report aggregation use the
RO engine. Each schema's complete result is fetched inside its own read-only
transaction; the connection is returned before the next schema or retry delay.
Python retains intermediate rows. PostgreSQL on RO performs final joins and
aggregations using typed, bound JSON recordsets; no temporary tables are created.
Explicit casts preserve the old staging-table rounding and column types.

The RW engine is acquired only to upsert final rows into the existing
`public.__customer_total_data`. No table migration is required. Each batch
commits independently and can be rerun idempotently after failure. A failed batch
rolls back and fails the job; earlier committed batches remain. Historical dates
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
only. Before deploying this version, app-interface must supply the actual replica
hostname as the `DATABASE_RO_HOST` ClowdApp template parameter and ensure network
access and SELECT privileges for the reporting user on the replica. Both scheduled
jobs receive the RO endpoint. An optional `koku-daily-ro-secret` with `username`
and `password` keys supplies separate RO credentials; otherwise Clowder's primary
credentials are inherited. The existing Clowder database configuration continues
to supply RW access for final upserts. The template requires the RO hostname;
applying code alone does not establish or verify live replica wiring.

## Operational settings

| Variable | Default | Meaning |
| --- | --- | --- |
| REPLICA_RETRY_ATTEMPTS | 3 | Total attempts per schema for confirmed recovery conflicts |
| REPLICA_RETRY_DELAY | 1 | Seconds between attempts, outside any transaction |
| REPORT_WRITE_BATCH_SIZE | 100 | Maximum daily rows per RW transaction |
| REPORT_STATEMENT_TIMEOUT_MS | 5000 | Transaction-local RW statement timeout |
| REPORT_LOCK_TIMEOUT_MS | 1000 | Transaction-local RW lock timeout |

Retry attempts, batch size, ports, and timeouts must be positive integers; delay
must be finite and nonnegative. Only database errors whose code and server
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

The original SQL under `tests/fixtures/legacy_sql` is a fixed baseline for output
comparison. Integration checks run both SQL paths against the same fixture,
including paused WAL replay, recovery conflicts, and lock contention.
