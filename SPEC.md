# SPEC — COST-8395: compute daily reports on the read replica

Status: awaiting human approval; no implementation changes made.

## Contract and setup plan

- Tier 3: production database concurrency and financial report correctness.
- Worktree: `/private/tmp/koku-daily-cost-8395`, branch `mpovolny/cost-8395`,
  based on `5b0cbda4de193a58a9c86ecf9ac756745804f024`.
- Maintain independent RO and RW SQLAlchemy engines. All tenant discovery,
  tenant scans, metadata joins, and report aggregation run on RO. RW is used
  only for bounded upserts of the final daily totals.
- Require an explicitly configured RO endpoint. Missing RO configuration or
  failed RO connectivity must not silently route reporting to RW.
- Use the existing PostgreSQL driver and runtime libraries. No new runtime
  dependencies are planned. Preserve TLS verification for both connections.
- Add a worktree-local Python 3.11 virtual environment using the existing
  dependency lock. Do not change the user's other virtual environments.
- Development-only tools: pytest (test execution), coverage and diff-cover
  (enforced changed-line coverage), mypy (types), Hypothesis (properties),
  pytest-randomly (order dependence), and existing pre-commit hooks (style).
  Pin their versions in `requirements-dev.txt`. Use manual mutation instead
  of adding a mutation framework.
- Add gauntlet files by path: `tools/gauntlet.sh`, `tools/mutation_check.py`,
  `tools/source_state.py`, `tests/conftest.py`, `tests/test_config.py`,
  `tests/test_engine.py`, `tests/test_reports.py`,
  `tests/test_report_properties.py`, `tests/test_postgres_reports.py`,
  `tests/fixtures/legacy_sql/` (unchanged reference SQL),
  `tests/fixtures/postgres.sql`, `tests/postgres-compose.yaml`,
  `requirements-dev.txt`, and `EVIDENCE.md`. Extend the existing
  `tests/test_setup_runner.py`.
- Use disposable local PostgreSQL primary and physical standby containers for
  integration and recovery-conflict checks. These tests must never use production
  database credentials. Record container image and tool versions in evidence.
- At spec approval, commit this specification; commit subsequent green
  checkpoints locally. No push, PR, app-interface mutation, deployment,
  production report execution, email, S3 upload, or Prometheus push is included.
- Update application configuration, SQL, `.env.example`, deployment template,
  README and operational docs as needed. Document required app-interface wiring
  separately; do not invent a replica endpoint or assume it is already deployed.

## Failure model

| Failure | Required check |
| --- | --- |
| Tenant reads accidentally use RW | Connection-routing assertions and independent database SQL traces |
| Replica rejects temporary-table writes | Execute report paths on a physical standby with read-only transactions |
| Long transactions retain tenant locks | One transaction per schema; assert no transaction remains open during processing, CSV output, or retry delay |
| Recovery cancellation contaminates later schemas | Real PostgreSQL cancellation/rollback tests plus bounded retry unit tests |
| Retry duplicates results | Publish a schema's rows only after its entire read succeeds |
| Python conversion changes money or SQL NULL behavior | Legacy SQL parity fixtures and Decimal/NULL property tests |
| Replica lag hides newly written totals | Combine RO history with this run's final rows before generating monthly totals |
| Partial or blocked final writes damage historical totals | Small idempotent upserts, statement/lock timeouts, rollback tests, and no deletion of history |
| Exhausted schema retries silently overwrite complete totals with partial totals | Explicit incomplete-run logs; suppress aggregate persistence when required inputs are incomplete |
| Missing RO settings overload RW | Fail configuration validation before report queries; prohibit automatic RW fallback |
| Shared mutable report configuration breaks repeat runs | Two runs in one process produce equivalent outputs and execute setup independently |

## Executable acceptance scenarios

1. **Separate RO and RW configuration.** Explicit RO host/port and optional
   separate RO credentials resolve independently from RW in environment and
   Clowder modes. Shared credentials may be inherited explicitly by configuration.
   Passwords with URL-special characters work. Missing RO host produces a clear
   configuration error without disclosing credentials or running a report.

2. **Route all report reads to RO.** With distinct traced engines, every enabled
   daily, weekly, and ordinary report performs discovery, schema reads, metadata
   joins, and aggregation on RO. RO transactions explicitly enforce read-only
   access. RW traces contain no tenant scans or intermediate table operations.
   Engines preserve the existing TLS certificate validation behavior.

3. **Replace active temporary-table setup with read-only queries.** Each enabled
   schema query returns rows into Python. Metadata joins and aggregations execute
   on RO using bound intermediate values or equivalent read-only SQL; there is no
   CREATE TEMP, INSERT into staging tables, or DO loop on the active path. Existing
   inactive customer-size reporting remains disabled.

4. **One completed read transaction per schema.** Given org1 and org2, fetching
   org1's complete result ends its transaction before org2 starts. Discovery,
   cutoff capture, and final report queries also end their own transactions before
   Python processing or file output. One stable cutoff is captured for the run.
   SQL results are fully consumed before closing their transactions.

5. **Bounded recovery-conflict retry.** A schema canceled specifically by standby
   recovery conflict is rolled back and retried, at most three total attempts,
   with a configurable delay outside the transaction. A successful retry
   contributes its rows exactly once. A lost connection caused by a confirmed
   recovery conflict reconnects before retry. Unrelated cancellation, SQL errors,
   authentication errors, and connectivity failures retain fail-fast behavior.
   Logs identify schema and attempt without logging credentials or row contents.

6. **Exhausted retries are visible and isolated.** If org1 exhausts recovery
   retries, log its omission and continue org2. Mark affected outputs incomplete
   in logs; do not upsert all-customer totals from incomplete required inputs.
   A schema absent during discovery/existence checking is logged and skipped,
   preserving the existing missing-schema behavior. Other database errors are
   not converted into silent skips.

7. **Preserve report values.** On a fixed multi-tenant PostgreSQL fixture, compare
   all enabled reports against unmodified baseline SQL. Compare columns, row
   multisets, CSV values, and report return structure, with identical ordering
   where the baseline specifies ORDER BY. Cover exclusions, empty tenants,
   unused/active cost models, JSON values, multiple currencies, Decimal precision,
   NULLs, overlapping dates, and monthly SUM versus MAX semantics. A physical
   standby must execute the new read path successfully.

8. **Only final bounded writes on RW.** Daily totals are upserted with bound
   parameters into the existing `public.__customer_total_data`. Commit at most
   100 date rows per transaction, with transaction-local statement timeout
   5 seconds and lock timeout 1 second, configurable with validated positive
   values. A failed batch rolls back and propagates failure. Repeating successful
   writes is idempotent, and dates outside this run remain untouched. No RW
   connection or transaction remains open during tenant computation or retries.

9. **Handle replica lag without RW history scans.** Given historical January
   rows on RO and newly computed February rows not yet replayed to RO, the monthly
   report includes January and the current February values once. Current rows
   replace stale RO rows for matching dates; unmodified historical dates remain.
   No history query runs on RW. Concurrent writes by another application are not
   part of the parity guarantee; document the replica consistency boundary.

10. **Preserve scheduling and repeatability.** Daily disabled/weekly disabled
    runs skip corresponding computation and persistence. Namespace and target
    filters, filenames, columns, CSV generation, and returned data remain
    compatible. Two invocations in one process do not reuse stale task status or
    leak report selections. Read-only reports never acquire an RW transaction.

11. **Deployment configuration is concrete and documented.** Both scheduled
    report jobs receive RO configuration, while preserving their RW configuration.
    Tests cover the supported Clowder config shape and explicit environment
    overrides. Documentation identifies necessary app-interface endpoint/secret
    wiring, explains that rollout requires it, and shows retry and timeout knobs
    without credentials. No claim of live deployment is made from template tests.

## Invariants and scope limits

- Preserve tenant validation and parameter binding; reject hostile schema names.
- No migrations, production database writes, production load tests, or changes to
  Kafka/listener partition creation behavior.
- No tenant scans, temporary-table materialization, or report computation on RW.
- Preserve decimal precision, SQL NULL semantics, existing tenant exclusions,
  historical totals, and external report interfaces.
- Bounded retries apply to confirmed recovery conflicts; they do not hide general
  database failures or retry forever.
- Local fixture parity demonstrates fixed-input equivalence, not an identical
  snapshot across production tenants while ingestion and WAL replay continue.
- Large intermediate Python datasets are a memory risk. Exercise a scaled local
  fixture and record peak memory and row counts; production-scale guarantees
  require representative operational data not yet provided.

## Gauntlet and evidence plan

- Existing baseline: `python -m unittest discover -s tests -v`: 8 passed using
  the existing Koku virtual environment; fresh-worktree tooling is not installed
  yet. The final run will use the worktree's own environment.
- Observe each new behavioral test fail before implementation; for a preserved
  behavior already green, prove sensitivity with a temporary real bug.
- Run the full unit/property/integration suite, mypy for changed Python modules,
  lint/format hooks, and enforced 100% changed Python line coverage with branch
  coverage reported. Document any unsupported SQL coverage separately; SQL parity
  and standby execution are required checks.
- Manual mutation: persist 3–5 plausible faults in the routing, transaction,
  retry, duplicate-result, and final-write paths; prove each mutation executes
  and its tests reject it. Restore and verify the source state after each.
- Hypothesis properties cover exact numeric/NULL aggregation and replacement of
  current totals over historical dates, including idempotence and input ordering.
- Run randomized test order with recorded seed; attempt hostile schema values,
  ambiguous cancellation errors, empty results, repeated runs, and lock contention.
- Real execution invokes report generation on the disposable primary/standby
  fixture without external delivery side effects. Check transaction boundaries
  and final rows directly; reproduce recovery conflict where local PostgreSQL
  allows it and distinguish real conflicts from injected boundary errors.
- Audit added development dependencies and scan the diff for secrets; record
  actual toolchain versions, commands, final source commit, and spec-to-test
  mapping in `EVIDENCE.md`. `tools/gauntlet.sh` is the reproducible entry point.
- Independent fresh-agent verification: not planned; record `not performed`
  with its confidence limit. The normal gauntlet and explicit adversarial pass
  remain required.
- Any unavailable layer is reported as unavailable, not passed. Material changes
  to behavior or this contract require a visible spec revision and renewed approval.

## Revisions

- Initial draft: includes the user's requirement for both connections and RO
  computation, plus recovery conflict isolation and persisted-history parity.
