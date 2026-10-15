# Evidence — COST-8395 (Tier 3)

- Spec approval: obtained. The user replied **"go ahead"** to `SPEC.md` on
  2026-10-15. The approved specification was saved in commit `e86e8a9`.
- Tested source: `fcaaf1d2e41baf8a0b48051443b29a38c1fd2031` on
  `mpovolny/cost-8395`, in `/private/tmp/koku-daily-cost-8395`.
- This report was written after that run; its later commit adds evidence prose
  only. No application or checker source changed after the final run.
- Entry point: `bash tools/gauntlet.sh`. Bootstrap with Python 3.11 and
  `.venv/bin/python tools/bootstrap.py`; the runtime lock is `Pipfile.lock`,
  complete development versions are in `requirements-dev.lock`, and hook
  versions are pinned in `.pre-commit-config.yaml`.
- Toolchain: Python 3.11.15, pytest 9.0.3, coverage 7.14.1, diff-cover 9.7.1,
  mypy 1.18.2, Hypothesis 6.140.3, pytest-randomly 4.0.1, pre-commit 4.6.2,
  Black 26.5.1, flake8 7.3.0, gitleaks 8.30.1, Docker 29.5.3.
- PostgreSQL: 16.13 primary and physical standby, image
  `postgres@sha256:5d143123fdf80462d1778cd4f24b9f7ca13c87174bca19141fb194c5a1ebca59`.
- Final log: `.cache/final-gauntlet.log`; machine-readable layer manifest:
  `.cache/gauntlet.json`. These generated files are recreated by the entry point.
- Independent verification: **not performed**, as declared in the spec.

## What changed

The job now creates a separately configured RO engine. Tenant discovery, schema
reads, metadata joins, and aggregation execute in read-only transactions on RO.
Every tenant query completes and releases its transaction before the next tenant
or retry delay. Python retains intermediate rows, and typed, bound JSON recordsets
let RO perform the final report queries without temporary tables. The explicit
SQL casts reproduce the former staging-table conversions.

RW is opened only for final daily-total upserts, using one INSERT per batch,
transaction-local statement/lock timeouts, and independent commits. History is
read from RO and overlaid with this run's values so the monthly report does not
depend on those new writes having replayed. Confirmed recovery conflicts retry
up to three times by default; exhausted tenants are logged and skipped, and an
incomplete run does not persist aggregate daily totals. Unrelated errors fail
the job. Existing delivery code and the production dependency lock are unchanged.

No production database, app-interface configuration, deployment, Jira issue,
remote branch, or PR was changed by this work.

## Final fresh gauntlet

All ten expected layers completed successfully from the clean source commit.
The source-state check identified the same commit before and after mutation.

| Layer | Command, as persisted in `tools/gauntlet.py` | Actual result |
| --- | --- | --- |
| Databases | `docker compose -f tests/postgres-compose.yaml up -d --wait` | Primary and physical standby healthy; tests confirm their recovery roles |
| Tests and suite health | `coverage run --branch --source=kokudaily -m pytest -q -s --randomly-seed=8395 --tb=short` | **64 passed in 16.28 seconds**, seed 8395; zero failures |
| Static types | `mypy --check-untyped-defs --ignore-missing-imports --disable-error-code=import-untyped` on six changed production modules | **No issues found in 6 source files**; third-party packages without stubs remain untyped |
| Lint and format | `pre-commit run --all-files` | All eight hooks passed; frozen legacy SQL fixtures excluded from formatting |
| Changed-line coverage | `coverage xml`, then `diff-cover coverage.xml --compare-branch=5b0cbda --fail-under=100` | **225/225 changed Python lines covered; 0 missing; 100%** |
| Checker controls and mutation | `python -m tools.negative_controls`; `python -m tools.mutation_check` | Five core mutants executed and rejected, **5/5 killed**; controls below also rejected their known-bad cases |
| Real CLI execution | `python -m tools.run_local_reports` | Actual `job.py` generated **40 CSV reports**, created the ZIP archive, and persisted **77 daily dates** on the disposable primary; external delivery disabled |
| Scaled memory | `python -m tools.memory_probe --tenants 100`, then `--tenants 500` | Measurements below; this is a measurement layer, not a production memory guarantee |
| Dependencies and licenses | `python -m tools.dependency_audit` | **46 installed distributions** queried against PyPI advisory data; **0 advisory findings**, **0 newly vulnerable versions**. License metadata recorded; new development packages have MIT/BSD/Apache/MPL declarations. Unchanged runtime package app-common-python lacks license metadata |
| Secrets | `gitleaks git --redact --no-banner --log-opts=5b0cbda..HEAD` | **4 commits**, approximately **222,227 bytes** scanned; **no leaks found** |

The two Hypothesis property tests passed inside the full suite. They exercise
exact Decimal/NULL aggregation through real PostgreSQL and date-overlay
precedence, idempotence, and input-order independence. Both use an example limit
of 100; per-example statistics were not captured in the final log, so no actual
example-count claim is made.

Branch coverage was collected. The two new execution modules `replica.py` and
`reports.py` each have 100% statement and branch coverage. Overall package
coverage is 76%, including unchanged delivery code that is not exercised by
the unit coverage process. The enforced constraint is changed Python lines;
the SQL checks below are separate integration evidence, not SQL line coverage.

## Spec to test mapping

All test paths below are in `tests/`.

| Approved scenario or invariant | Executable evidence | Status |
| --- | --- | --- |
| 1. Independent RO/RW configuration, explicit RO endpoint, special password characters | `test_config.py::test_ro_environment_inherits_only_credentials_not_host`, `test_clowder_writer_and_explicit_reader`; `test_engine.py::test_ro_endpoint_is_required_before_engine_creation`, `test_separate_ro_url_preserves_special_password_characters` | pass |
| 2. RO routing and read-only enforcement; preserve shared TLS behavior | `test_reports.py::test_read_only_run_never_connects_writer_and_repeats`; `test_postgres_reports.py::test_all_reports_match_legacy_on_standby_with_wal_paused`, `test_read_only_transaction_rejects_writes_on_primary_too`; `test_engine.py::test_tls_options_apply_to_both_engines` | pass |
| 3. Active paths work without temporary tables | `test_all_reports_match_legacy_on_standby_with_wal_paused` executes all active reports on a physical standby and checks the RO SQL trace for writes/DDL | pass |
| 4. Short, completed transactions and fully consumed results; stable cutoff | `test_replica.py::test_reads_are_read_only_fully_consumed_and_committed`, `test_missing_schema_is_checked_in_same_short_transaction`; `test_reports.py::test_active_setup_captures_one_cutoff_for_all_tenants_and_reports` asserts one cutoff query and identical bindings across tenants and reports | pass |
| 5. Bounded recovery-conflict retries, rollback, no duplicate publication, delay outside transaction | `test_conflict_rolls_back_before_retry_and_publishes_once` covers codes 40001, 57014, and 57P01 and asserts a new connection request per attempt; `test_unrelated_errors_propagate_without_retry`; `test_postgres_reports.py::test_real_recovery_conflict_rolls_back_and_retry_succeeds` reproduces a real WAL-replay/DDL conflict | pass; real session-termination limit below |
| 6. Exhaustion is visible; other tenants continue; no partial aggregate persistence | `test_exhausted_conflicts_are_explicit_and_bounded`; `test_exhausted_schema_retries_continue_but_never_persist_partial_totals` | pass |
| 7. Existing values, schemas, exclusions, rounding, JSON, currencies, NULLs, CSVs, and ordering | `test_all_reports_match_legacy_on_standby_with_wal_paused`: **40 reports, 65 rows** compared with the unchanged baseline SQL; `test_typed_intermediate_conversion_matches_postgres_insert`; both property tests | pass on the fixed fixture |
| 8. Bounded final writes, local timeouts, rollback, idempotence, retained history | `test_final_writes_are_bounded_and_set_local_timeouts`, `test_batch_is_one_statement_so_timeout_covers_whole_batch`, `test_failed_final_write_rolls_back_and_propagates`; `test_writer_lock_timeout_and_atomic_batch_rollback`, `test_upserts_preserve_history_and_enforce_timeout` | pass |
| 9. Replica lag does not hide this run's new daily totals; no RW history scans | The full parity test pauses WAL replay, removes current dates from RO, verifies current totals in output, and checks RW SQL contains only timeout settings and final INSERTs; overlay unit/property tests | pass |
| 10. Disabled schedules, filters, repeat invocations, no ordinary-read writer transaction | `test_disabled_daily_and_weekly_tasks_do_no_setup`, `test_filters_skip_reports_without_database_queries`, `test_read_only_run_never_connects_writer_and_repeats`; fixture parity verifies return values and CSVs | pass |
| 11. Both scheduled jobs receive RO settings and write limits; Clowder remains RW source | `test_deployment_wires_ro_and_writer_limits_to_both_jobs`, `test_clowder_writer_and_explicit_reader`; `docs/read-replica-reporting.md` describes required endpoint/secret wiring | pass statically; live deployment unverified |
| Preserve safe schema validation and bound values | Original `test_setup_runner.py` validation tests; `test_unsafe_schema_rejected_before_connect`, `test_intermediates_are_bound_and_preserve_numeric_and_null`, serialization/operational-settings error tests | pass |
| No schema migrations, runtime dependency change, or listener behavior change | Source diff and capability review; unchanged `Pipfile`/`Pipfile.lock`; no listener code in this repository | pass |

The compatibility guarantee is for configured schedules and existing report
outputs. Enabling daily work still performs its setup/persistence even when
`filter_target` excludes the monthly totals output, matching the previous job.

## Mutation and checker trust

| Plausible bug | Main behavioral suite | Property suite alone |
| --- | --- | --- |
| RO transaction changed to READ WRITE | killed | killed by real standby numeric property |
| Recovery conflicts propagated instead of retried | killed | survived: properties do not test retries |
| Current daily rows omitted from history overlay | killed | killed |
| Report reader routed to the primary engine | killed | survived: properties do not test orchestration routing |
| Partial inputs allowed to overwrite persisted totals | killed | survived: properties do not test persistence policy |

Each mutant ran in a new Python process with a unique, nonexistent bytecode
cache prefix and bytecode writing disabled. Before pytest started, the child
verified the mutated module's source hash and absence of a bytecode cache and
printed its execution marker. Only pytest exit 1 with a named behavioral test
failure counted as a kill; collection/internal errors failed the checker.
Original file contents were restored in `finally` and checked. Individual logs
and the result map are in `.cache/mutations/`.

The home-grown checker controls rejected missing/duplicate mutation anchors,
dirty source, and an incomplete layer manifest. Temporarily removing each guard
made its control test fail. Separate temporary changes proved the shared-cutoff
assertion, TLS assertion, and existing port-fallback regression test fail when
their behavior changes.
Gitleaks rejected a synthetic access-key pattern, and diff-cover rejected an XML
report with zero hits. These controls demonstrate those specific failure paths;
they do not establish that the checkers recognize every possible violation.

## Memory results and rollout limits

The local memory probe includes all six intermediate datasets and serialization
of the three datasets consumed by daily totals. It uses fresh Python processes
and process peak RSS, normalized to MiB on macOS.

| Simulated tenants | Days | Nodes/tenant | Intermediate rows | Retained peak RSS | Serialized peak RSS | Bound JSON payload |
| --- | --- | --- | --- | --- | --- | --- |
| 100 | 90 | 100 | 75,300 | 147.3 MiB | **194.7 MiB** | 24.0 MiB |
| 500 | 90 | 100 | 376,500 | 579.0 MiB | **805.3 MiB** | 122.2 MiB |

**This implementation is not demonstrated to fit production within 2 GiB.**
The probe excludes database-driver buffers, full output copies, PostgreSQL's
own query memory, and the real tenant/node distribution. Larger deployments
can require substantially more RAM. The current design retains intermediates
in memory; it has no spill-to-disk mechanism or hard process-memory budget.
Production sizing, reducing the retained dataset scope, or a separately reviewed
disk-backed design remains necessary before rollout if representative sizing
approaches the pod limit. No production-sized upper bound is claimed.

Other assurance boundaries:

- Production RO hostname, credentials/SELECT permissions, network access, RDS
  TLS connections, and app-interface rendering were not verified live. The
  ClowdApp template requires `DATABASE_RO_HOST`; documentation explains the
  deployment prerequisite.
- Real standby statement cancellation was reproduced. A server-terminated
  recovery-conflict session was not separately reproduced; reconnect behavior
  relies on SQLAlchemy/psycopg2 connection invalidation and opening a new read
  connection per attempt.
- The cutoff test uses a fixed January 31 boundary and verifies one capture and
  identical cutoff bindings across multiple tenants and report setups. The
  complete database parity run did not actually span midnight.
- Per-tenant transactions do not provide a global snapshot while ingestion
  and replication continue. Concurrent writers to persisted totals are not
  coordinated by this change. `Forbid` prevents overlap within each CronJob,
  not overlap between the two separately scheduled jobs.
- PyPI advisory checking covers the 46 distributions in the application/test
  environment. It does not separately audit each pre-commit hook's isolated
  transitive environment. Hook repositories and versions are pinned.
- No independent verifier agent was used. The builder authored the application,
  tests, and evidence; human spec approval and the executable checks reduce
  different risks but do not establish absolute correctness.

## Failures encountered and resolved

- Baseline before implementation: **8 tests passed**. Thirteen new execution
  contracts failed against explicit stubs; nine configuration/engine cases then
  failed against the old behavior. The orchestration regression failed because
  it connected to RW for an ordinary read report. A later batch test failed
  because DBAPI executemany did not bound the entire batch with one timeout.
- PostgreSQL fixtures initially lacked columns required by legacy reports; the
  fixture schema was completed without changing production expectations. A
  real integration failure exposed incorrect key-metrics dataset naming; the
  production mapping was corrected and full parity then passed.
- Docker could not execute a bind-mounted initialization script on this host;
  the disposable primary now receives its test-only replication rules through
  its container entrypoint.
- The repository's flake8 hook was unavailable in its configured hook repository,
  and import sorting disagreed with Black about blank lines after module
  docstrings. The setup repairs preserve both lint checks; frozen reference SQL
  remains byte-for-byte baseline content.
- The TLS regression test originally mocked global `os.stat` too broadly,
  causing pytest error rendering to crash under its negative control. Its mock
  now intercepts only the certificate path; assertions are unchanged and the
  TLS mutant produces the expected behavioral test failure.
- Final spec-to-evidence review identified a missing direct assertion of the
  new runner's single-cutoff behavior. A boundary-value test, a corresponding
  negative control, and explicit recovery-code cases were added before the
  final clean-source gauntlet; implementation behavior was unchanged.
- The first dependency audit rejected pytest 8.4.2, pip 26.1, and setuptools
  82.0.1. The pinned isolated toolchain was advanced to fixed versions; the final
  audit found zero advisories. Initial restricted-network/Docker access required
  elevated execution for the already approved setup and checks.

No gauntlet layer was silently skipped. Independent verification and live
production checks were outside this run; their limits are stated above. No
production-ready memory claim or deployment claim is made.
