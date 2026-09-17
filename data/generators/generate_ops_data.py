#!/usr/bin/env python
"""
GenAI Enterprise Lab
Module 1 — Synthetic Operations Data Generator

Generates deterministic, referentially consistent operations data for the
AI Ops Investigator.

Profiles are defined in:
    data/generators/module1_profiles.json

Examples:
    python data/generators/generate_ops_data.py --profile ci --reset
    python data/generators/generate_ops_data.py --profile dev --reset
    python data/generators/generate_ops_data.py --profile benchmark --reset

The generator:
- streams large tables into PostgreSQL using COPY
- avoids loading the 10M-log benchmark dataset into RAM
- preserves referential integrity
- injects deterministic operational anomalies and root causes
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Sequence

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "data" / "generators" / "module1_profiles.json"

DOMAINS = [
    "Finance",
    "Claims",
    "Sales",
    "Risk",
    "Operations",
    "Customer",
    "Compliance",
    "Executive",
    "IT",
    "Marketing",
]

APP_PREFIXES = [
    "Finance_Dashboard",
    "Claims_Analytics",
    "Sales_Performance",
    "Risk_Monitoring",
    "Executive_KPI",
    "Customer_360",
    "Operations_Control",
    "Compliance_Reporting",
    "IT_Service_Monitor",
    "Marketing_Insights",
]

SOURCE_TYPES = [
    "POSTGRESQL",
    "SQLSERVER",
    "ORACLE",
    "FILE",
    "API",
    "S3",
    "SFTP",
]

NODE_NAMES = ["QLIK-NODE-01", "QLIK-NODE-02", "QLIK-NODE-03", "QLIK-NODE-04"]

ROOT_CAUSE_MESSAGES = {
    "DB_TIMEOUT": (
        "Database connection timeout",
        "Database connection could not be established before timeout",
    ),
    "NETWORK_TIMEOUT": (
        "Network timeout while reaching remote service",
        "Remote endpoint did not respond within the configured timeout",
    ),
    "DISK_SATURATION": (
        "Disk saturation detected",
        "Insufficient temporary disk capacity for reload workload",
    ),
    "AUTH_FAILURE": (
        "Authentication failure",
        "Credentials rejected by upstream data source",
    ),
    "SOURCE_UNAVAILABLE": (
        "Data source unavailable",
        "Upstream data source is not accepting connections",
    ),
    "FILE_MISSING": (
        "Expected input file missing",
        "Scheduled input file was not present at reload time",
    ),
    "DEPENDENCY_FAILURE": (
        "Upstream dependency failure",
        "Required upstream dependency did not complete successfully",
    ),
    "MEMORY_EXHAUSTION": (
        "Memory exhaustion",
        "Reload process exceeded available engine memory",
    ),
    "LONG_RUNNING_QUERY": (
        "Long-running query timeout",
        "Source query exceeded the maximum execution time",
    ),
    "SCHEDULER_FAILURE": (
        "Scheduler failure",
        "Scheduled reload could not be dispatched correctly",
    ),
}

GENERIC_LOG_MESSAGES = [
    ("INFO", "Scheduler", "Reload execution initialized"),
    ("INFO", "Engine", "Application metadata loaded"),
    ("INFO", "Connector", "Preparing data source connection"),
    ("INFO", "Engine", "Loading source table metadata"),
    ("INFO", "Engine", "Executing extraction step"),
    ("DEBUG", "Engine", "Processing reload batch"),
    ("INFO", "Engine", "Transformations in progress"),
    ("INFO", "Engine", "Persisting intermediate result"),
    ("DEBUG", "Engine", "Memory checkpoint completed"),
    ("INFO", "Engine", "Finalizing data model"),
    ("INFO", "Engine", "Validating output"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate synthetic operations data for Module 1."
    )
    parser.add_argument(
        "--profile",
        required=True,
        choices=["ci", "dev", "benchmark", "stress"],
        help="Generation profile.",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Path to module1_profiles.json.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing ops data before generation.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50_000,
        help="Maximum rows held in memory before COPY (default: 50000).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration and print target counts without inserting data.",
    )
    return parser.parse_args()


def load_config(path: Path, profile_name: str) -> tuple[dict, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data[profile_name], data["generation_rules"]


def load_database_settings() -> dict:
    load_dotenv(ROOT / ".env")

    required = ["POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError(
            f"Missing database environment variables: {', '.join(missing)}"
        )

    return {
        "dbname": os.environ["POSTGRES_DB"],
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
        "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
    }


def connect(settings: dict, *, autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(**settings, autocommit=autocommit)


def check_schema(conn: psycopg.Connection) -> None:
    required = [
        "ops.applications",
        "ops.data_sources",
        "ops.application_dependencies",
        "ops.reload_jobs",
        "ops.reload_logs",
        "ops.incidents",
        "ops.incident_events",
        "ops.jira_tickets",
    ]
    with conn.cursor() as cur:
        for table in required:
            cur.execute("SELECT to_regclass(%s)", (table,))
            if cur.fetchone()[0] is None:
                raise RuntimeError(
                    f"Required table {table} does not exist. "
                    "Run database/migrations/001_module1_ops_schema.sql first."
                )


def ops_has_data(conn: psycopg.Connection) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM ops.applications LIMIT 1
            )
            OR EXISTS (
                SELECT 1 FROM ops.reload_jobs LIMIT 1
            )
            OR EXISTS (
                SELECT 1 FROM ops.reload_logs LIMIT 1
            )
            """
        )
        return bool(cur.fetchone()[0])


def reset_ops(conn: psycopg.Connection) -> None:
    print("Resetting existing Module 1 data...")
    with conn.cursor() as cur:
        cur.execute(
            """
            TRUNCATE TABLE
                ops.jira_tickets,
                ops.incident_events,
                ops.incidents,
                ops.reload_logs,
                ops.reload_jobs,
                ops.application_dependencies,
                ops.data_sources,
                ops.applications
            RESTART IDENTITY CASCADE
            """
        )
    conn.commit()


def copy_rows(
    conn: psycopg.Connection,
    copy_sql: str,
    rows: Iterable[Sequence],
) -> int:
    count = 0
    with conn.cursor() as cur:
        with cur.copy(copy_sql) as cp:
            for row in rows:
                cp.write_row(row)
                count += 1
    conn.commit()
    return count


def chunked_copy(
    conn: psycopg.Connection,
    copy_sql: str,
    rows: Iterable[Sequence],
    batch_size: int,
    label: str,
    expected_total: int,
) -> int:
    batch: list[Sequence] = []
    total = 0
    started = time.perf_counter()

    for row in rows:
        batch.append(row)
        if len(batch) >= batch_size:
            total += copy_rows(conn, copy_sql, batch)
            batch.clear()
            report_progress(label, total, expected_total, started)

    if batch:
        total += copy_rows(conn, copy_sql, batch)
        report_progress(label, total, expected_total, started)

    return total


def report_progress(label: str, current: int, total: int, started: float) -> None:
    elapsed = max(time.perf_counter() - started, 0.001)
    rate = current / elapsed
    pct = (current / total * 100) if total else 100.0
    remaining = max(total - current, 0)
    eta = remaining / rate if rate > 0 else 0
    print(
        f"{label:<22} {current:>12,}/{total:<12,} "
        f"{pct:6.2f}%  {rate:>10,.0f} rows/s  ETA {eta:>7.0f}s",
        flush=True,
    )


def weighted_choice(rng: random.Random, weights: dict[str, float]) -> str:
    keys = list(weights)
    values = list(weights.values())
    return rng.choices(keys, weights=values, k=1)[0]


def deterministic_rng(seed: int, key: int, salt: int = 0) -> random.Random:
    return random.Random((seed * 1_000_003) + (key * 97_409) + salt)


def root_cause_for_reload(reload_id: int, seed: int, rules: dict) -> str:
    rng = deterministic_rng(seed, reload_id, 777)
    return weighted_choice(rng, rules["root_cause_distribution"])


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def random_timestamp(
    rng: random.Random,
    start: datetime,
    end: datetime,
    *,
    scheduled_bias: bool = False,
) -> datetime:
    total_days = max((end.date() - start.date()).days, 1)
    day_offset = rng.randrange(total_days)
    day = start + timedelta(days=day_offset)

    if scheduled_bias:
        hour = rng.choices(
            [1, 2, 3, 4, 5, 6, 7, 8, 12, 18, 22],
            weights=[2, 3, 5, 10, 18, 20, 16, 8, 4, 3, 2],
            k=1,
        )[0]
    else:
        hour = rng.randrange(24)

    return day.replace(
        hour=hour,
        minute=rng.randrange(60),
        second=rng.randrange(60),
        microsecond=0,
    )


def generate_applications(profile: dict) -> Iterable[tuple]:
    count = profile["applications"]
    start = parse_dt(profile["period_start"])
    created = start - timedelta(days=180)
    rng = random.Random(profile["seed"] + 10)

    for app_id in range(1, count + 1):
        if app_id <= len(APP_PREFIXES):
            name = APP_PREFIXES[app_id - 1]
        else:
            domain = DOMAINS[(app_id - 1) % len(DOMAINS)]
            name = f"{domain}_Analytics_{app_id:03d}"

        domain = DOMAINS[(app_id - 1) % len(DOMAINS)]
        criticality = rng.choices(
            ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            weights=[12, 38, 35, 15],
            k=1,
        )[0]
        sla_hour = rng.choice([6, 7, 8, 9])
        sla_minute = rng.choice([0, 15, 30, 45])
        sla_time = f"{sla_hour:02d}:{sla_minute:02d}:00"

        yield (
            app_id,
            name,
            domain,
            f"{domain} Business Owner {((app_id - 1) % 12) + 1:02d}",
            f"BI Platform Engineer {((app_id - 1) % 18) + 1:02d}",
            criticality,
            sla_time,
            "Europe/Paris",
            True,
            created,
            created,
        )


def generate_data_sources(profile: dict) -> Iterable[tuple]:
    count = profile["data_sources"]
    start = parse_dt(profile["period_start"])
    created = start - timedelta(days=240)
    rng = random.Random(profile["seed"] + 20)

    for source_id in range(1, count + 1):
        source_type = SOURCE_TYPES[(source_id - 1) % len(SOURCE_TYPES)]
        env = rng.choices(
            ["DEV", "TEST", "REC", "PROD"],
            weights=[5, 8, 12, 75],
            k=1,
        )[0]
        criticality = rng.choices(
            ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            weights=[10, 35, 40, 15],
            k=1,
        )[0]

        yield (
            source_id,
            f"DS_{source_type}_{source_id:03d}",
            source_type,
            f"{source_type.lower()}-{source_id:03d}.enterprise.local",
            env,
            criticality,
            True,
            created,
            created,
        )


def build_dependencies(profile: dict) -> list[tuple]:
    app_count = profile["applications"]
    source_count = profile["data_sources"]
    target = profile["application_dependencies"]
    max_pairs = app_count * source_count

    if target > max_pairs:
        raise ValueError(
            f"Requested {target} dependencies but only {max_pairs} unique pairs exist."
        )

    rng = random.Random(profile["seed"] + 30)
    pairs: set[tuple[int, int]] = set()

    # Ensure every application has at least one dependency where possible.
    for app_id in range(1, min(app_count, target) + 1):
        source_id = ((app_id * 7) % source_count) + 1
        pairs.add((app_id, source_id))

    while len(pairs) < target:
        pairs.add((rng.randint(1, app_count), rng.randint(1, source_count)))

    rows: list[tuple] = []
    created = parse_dt(profile["period_start"]) - timedelta(days=120)

    for dependency_id, (app_id, source_id) in enumerate(sorted(pairs), 1):
        dep_type = rng.choices(
            ["PRIMARY", "SECONDARY", "OPTIONAL"],
            weights=[55, 35, 10],
            k=1,
        )[0]
        critical_path = dep_type == "PRIMARY" or rng.random() < 0.20
        rows.append(
            (
                dependency_id,
                app_id,
                source_id,
                dep_type,
                critical_path,
                True,
                created,
            )
        )

    return rows


def dependency_map(dependencies: list[tuple]) -> dict[int, list[int]]:
    result: dict[int, list[int]] = defaultdict(list)
    for row in dependencies:
        _, app_id, source_id, *_ = row
        result[app_id].append(source_id)
    return dict(result)


def generate_reload_jobs(profile: dict, rules: dict) -> Iterable[tuple]:
    total = profile["reload_jobs"]
    app_count = profile["applications"]
    start = parse_dt(profile["period_start"])
    end = parse_dt(profile["period_end"])
    seed = profile["seed"]

    failure_rate = rules["reload_failure_rate"]
    sla_rate = rules["sla_breach_rate"]

    for reload_id in range(1, total + 1):
        rng = deterministic_rng(seed, reload_id, 100)
        app_id = ((reload_id * 31) % app_count) + 1
        started_at = random_timestamp(rng, start, end, scheduled_bias=True)

        failure_draw = rng.random()
        if failure_draw < failure_rate:
            status = "FAILED"
        elif failure_draw < failure_rate + 0.008:
            status = "CANCELLED"
        elif failure_draw < failure_rate + 0.015:
            status = "SKIPPED"
        else:
            status = "SUCCESS"

        if status == "SUCCESS":
            duration = max(30, int(rng.lognormvariate(5.7, 0.55)))
            rows_loaded = int(rng.lognormvariate(13.0, 1.0))
        elif status == "FAILED":
            duration = max(20, int(rng.lognormvariate(5.1, 0.60)))
            rows_loaded = rng.choice([0, 0, 0, int(rng.lognormvariate(10.5, 1.0))])
        elif status == "CANCELLED":
            duration = max(10, int(rng.lognormvariate(4.5, 0.5)))
            rows_loaded = 0
        else:
            duration = rng.randint(1, 10)
            rows_loaded = 0

        ended_at = started_at + timedelta(seconds=duration)
        trigger = rng.choices(
            ["SCHEDULED", "MANUAL", "API", "DEPENDENCY"],
            weights=[84, 7, 4, 5],
            k=1,
        )[0]
        attempt_number = rng.choices([1, 2, 3], weights=[90, 8, 2], k=1)[0]
        sla_breached = rng.random() < sla_rate

        yield (
            reload_id,
            app_id,
            started_at,
            ended_at,
            status,
            duration,
            rows_loaded,
            trigger,
            rng.choice(NODE_NAMES),
            attempt_number,
            sla_breached,
            started_at,
        )


def generic_log_row(
    *,
    log_id: int,
    reload_id: int,
    logged_at: datetime,
    index: int,
    data_source_id: int | None,
    correlation_id: uuid.UUID,
) -> tuple:
    level, component, message = GENERIC_LOG_MESSAGES[index % len(GENERIC_LOG_MESSAGES)]
    return (
        log_id,
        reload_id,
        logged_at,
        level,
        component,
        message,
        None,
        data_source_id if component == "Connector" else None,
        correlation_id,
    )


def log_rows_for_job(
    *,
    reload_id: int,
    app_id: int,
    started_at: datetime,
    ended_at: datetime,
    status: str,
    n_logs: int,
    seed: int,
    rules: dict,
    deps: dict[int, list[int]],
    starting_log_id: int,
) -> Iterable[tuple]:
    rng = deterministic_rng(seed, reload_id, 200)
    app_sources = deps.get(app_id) or []
    data_source_id = (
        app_sources[(reload_id * 13) % len(app_sources)] if app_sources else None
    )
    correlation_id = uuid.UUID(
        int=((reload_id << 64) ^ (seed * 1_000_003)) % (1 << 128)
    )

    duration_seconds = max(int((ended_at - started_at).total_seconds()), 1)
    root_cause = root_cause_for_reload(reload_id, seed, rules)

    for i in range(n_logs):
        if n_logs == 1:
            logged_at = started_at
        else:
            fraction = i / (n_logs - 1)
            logged_at = started_at + timedelta(seconds=duration_seconds * fraction)

        log_id = starting_log_id + i

        if i == 0:
            yield (
                log_id,
                reload_id,
                logged_at,
                "INFO",
                "Scheduler",
                "Reload started",
                None,
                None,
                correlation_id,
            )
            continue

        if status == "FAILED" and i == max(n_logs - 3, 1):
            short_message, _ = ROOT_CAUSE_MESSAGES[root_cause]
            yield (
                log_id,
                reload_id,
                logged_at,
                "WARN",
                "Database" if root_cause in {"DB_TIMEOUT", "LONG_RUNNING_QUERY"} else "Connector",
                short_message,
                root_cause,
                data_source_id,
                correlation_id,
            )
            continue

        if status == "FAILED" and i == max(n_logs - 2, 1):
            yield (
                log_id,
                reload_id,
                logged_at,
                "ERROR",
                "Engine",
                "Reload step failed after upstream error",
                root_cause,
                data_source_id,
                correlation_id,
            )
            continue

        if i == n_logs - 1:
            if status == "SUCCESS":
                yield (
                    log_id,
                    reload_id,
                    logged_at,
                    "INFO",
                    "Engine",
                    "Reload completed successfully",
                    None,
                    None,
                    correlation_id,
                )
            elif status == "FAILED":
                yield (
                    log_id,
                    reload_id,
                    logged_at,
                    "ERROR",
                    "Engine",
                    "Reload aborted",
                    "RELOAD_ABORTED",
                    None,
                    correlation_id,
                )
            elif status == "CANCELLED":
                yield (
                    log_id,
                    reload_id,
                    logged_at,
                    "WARN",
                    "Scheduler",
                    "Reload cancelled",
                    "RELOAD_CANCELLED",
                    None,
                    correlation_id,
                )
            else:
                yield (
                    log_id,
                    reload_id,
                    logged_at,
                    "INFO",
                    "Scheduler",
                    "Reload skipped",
                    None,
                    None,
                    correlation_id,
                )
            continue

        # Occasional non-fatal warnings in successful runs.
        if status == "SUCCESS" and rng.random() < 0.015:
            yield (
                log_id,
                reload_id,
                logged_at,
                "WARN",
                "Engine",
                "Transient latency detected; processing continued",
                "TRANSIENT_LATENCY",
                data_source_id,
                correlation_id,
            )
            continue

        yield generic_log_row(
            log_id=log_id,
            reload_id=reload_id,
            logged_at=logged_at,
            index=i,
            data_source_id=data_source_id,
            correlation_id=correlation_id,
        )


def generate_reload_logs(
    settings: dict,
    profile: dict,
    rules: dict,
    deps: dict[int, list[int]],
    batch_size: int,
) -> int:
    total_jobs = profile["reload_jobs"]
    total_logs = profile["reload_logs"]
    seed = profile["seed"]

    base = total_logs // total_jobs
    remainder = total_logs % total_jobs

    select_sql = """
        SELECT
            reload_id,
            application_id,
            started_at,
            ended_at,
            status
        FROM ops.reload_jobs
        ORDER BY reload_id
    """

    copy_sql = """
        COPY ops.reload_logs (
            log_id,
            reload_id,
            logged_at,
            level,
            component,
            message,
            error_code,
            data_source_id,
            correlation_id
        ) FROM STDIN
    """

    print(
        f"Reload-log distribution: {base} logs/job"
        + (f" +1 for first {remainder:,} jobs" if remainder else "")
    )

    total_inserted = 0
    next_log_id = 1
    batch: list[tuple] = []
    started = time.perf_counter()

    with connect(settings) as read_conn, connect(settings) as write_conn:
        with read_conn.cursor(name="reload_job_stream") as cur:
            cur.itersize = 5_000
            cur.execute(select_sql)

            for reload_id, app_id, started_at, ended_at, status in cur:
                n_logs = base + (1 if reload_id <= remainder else 0)

                for row in log_rows_for_job(
                    reload_id=reload_id,
                    app_id=app_id,
                    started_at=started_at,
                    ended_at=ended_at,
                    status=status,
                    n_logs=n_logs,
                    seed=seed,
                    rules=rules,
                    deps=deps,
                    starting_log_id=next_log_id,
                ):
                    batch.append(row)

                    if len(batch) >= batch_size:
                        total_inserted += copy_rows(write_conn, copy_sql, batch)
                        batch.clear()
                        report_progress(
                            "reload_logs",
                            total_inserted,
                            total_logs,
                            started,
                        )

                next_log_id += n_logs

            if batch:
                total_inserted += copy_rows(write_conn, copy_sql, batch)
                report_progress(
                    "reload_logs",
                    total_inserted,
                    total_logs,
                    started,
                )

    return total_inserted


def fetch_failed_reloads(
    conn: psycopg.Connection,
    limit: int,
) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                reload_id,
                application_id,
                started_at,
                ended_at
            FROM ops.reload_jobs
            WHERE status = 'FAILED'
            ORDER BY reload_id
            LIMIT %s
            """,
            (limit,),
        )
        return list(cur.fetchall())


def generate_incidents(
    profile: dict,
    rules: dict,
    failed_reloads: list[tuple],
) -> list[tuple]:
    total = profile["incidents"]
    app_count = profile["applications"]
    start = parse_dt(profile["period_start"])
    end = parse_dt(profile["period_end"])
    seed = profile["seed"]

    rows: list[tuple] = []
    # Correlate the configured share of FAILED reloads to incidents,
    # capped by the total number of incident rows requested.
    correlated_target = min(
        total,
        int(round(len(failed_reloads) * rules["failed_reload_incident_rate"])),
    )

    for incident_id in range(1, total + 1):
        rng = deterministic_rng(seed, incident_id, 300)

        if incident_id <= correlated_target:
            reload_id, app_id, started_at, ended_at = failed_reloads[incident_id - 1]
            linked_reload_id = reload_id
            root_cause = root_cause_for_reload(reload_id, seed, rules)
            opened_at = started_at + timedelta(minutes=rng.randint(1, 10))
            description = (
                f"Reload {reload_id} failed for application {app_id}; "
                f"technical investigation required."
            )
        else:
            linked_reload_id = None
            app_id = ((incident_id * 17) % app_count) + 1
            opened_at = random_timestamp(rng, start, end)
            root_cause = weighted_choice(rng, rules["root_cause_distribution"])
            description = (
                f"Operational degradation detected for application {app_id}."
            )

        severity = rng.choices(
            ["SEV1", "SEV2", "SEV3", "SEV4"],
            weights=[4, 16, 45, 35],
            k=1,
        )[0]
        resolved = rng.random() < 0.86
        status = "CLOSED" if resolved else rng.choice(["OPEN", "INVESTIGATING"])
        closed_at = (
            opened_at + timedelta(minutes=rng.randint(20, 24 * 60))
            if resolved
            else None
        )

        _, root_detail = ROOT_CAUSE_MESSAGES[root_cause]

        rows.append(
            (
                incident_id,
                app_id,
                linked_reload_id,
                opened_at,
                closed_at,
                severity,
                status,
                root_cause,
                description,
                root_detail if resolved else None,
                rng.choice(["MONITORING", "USER", "SCHEDULER", "AGENT"]),
                opened_at,
                closed_at or opened_at,
            )
        )

    return rows


def generate_incident_events(profile: dict, incidents: list[tuple]) -> Iterable[tuple]:
    total = profile["incident_events"]
    incident_count = len(incidents)
    base = total // incident_count
    remainder = total % incident_count
    event_id = 1

    event_types = [
        "DETECTED",
        "TRIAGED",
        "INVESTIGATION_UPDATE",
        "MITIGATION",
        "RESOLVED",
    ]

    for idx, incident in enumerate(incidents, 1):
        incident_id = incident[0]
        opened_at = incident[3]
        closed_at = incident[4]
        n_events = base + (1 if idx <= remainder else 0)
        end_time = closed_at or (opened_at + timedelta(hours=4))
        duration = max((end_time - opened_at).total_seconds(), 60)

        for i in range(n_events):
            fraction = i / max(n_events - 1, 1)
            occurred_at = opened_at + timedelta(seconds=duration * fraction)
            event_type = event_types[min(i, len(event_types) - 1)]
            yield (
                event_id,
                incident_id,
                occurred_at,
                event_type,
                "OPS_AUTOMATION" if i == 0 else "OPS_TEAM",
                f"{event_type.replace('_', ' ').title()} event for incident {incident_id}",
                occurred_at,
            )
            event_id += 1


def generate_jira(profile: dict, incidents: list[tuple]) -> Iterable[tuple]:
    total = min(profile["jira_tickets"], len(incidents))
    seed = profile["seed"]

    for ticket_id in range(1, total + 1):
        incident = incidents[ticket_id - 1]
        incident_id = incident[0]
        opened_at = incident[3]
        closed_at = incident[4]
        severity = incident[5]
        rng = deterministic_rng(seed, ticket_id, 400)

        priority = {
            "SEV1": "P1",
            "SEV2": "P2",
            "SEV3": "P3",
            "SEV4": "P4",
        }[severity]

        resolved = closed_at is not None
        status = "CLOSED" if resolved else rng.choice(["OPEN", "IN_PROGRESS", "BLOCKED"])
        updated_at = closed_at or (opened_at + timedelta(hours=rng.randint(1, 72)))

        yield (
            ticket_id,
            f"OPS-{ticket_id:06d}",
            incident_id,
            opened_at,
            updated_at,
            priority,
            status,
            f"ops.engineer{((ticket_id - 1) % 25) + 1:02d}",
            f"Investigate incident {incident_id}",
            "Incident resolved after root-cause remediation" if resolved else None,
        )


def print_target(profile_name: str, profile: dict) -> None:
    print(f"\nProfile: {profile_name}")
    print("=" * 58)
    for key in [
        "applications",
        "data_sources",
        "application_dependencies",
        "reload_jobs",
        "reload_logs",
        "incidents",
        "incident_events",
        "jira_tickets",
    ]:
        print(f"{key:<28} {profile[key]:>15,}")
    print("=" * 58)
    print(f"{'total rows':<28} {sum(profile[k] for k in profile if isinstance(profile[k], int) and k != 'seed'):>15,}")


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).resolve()
    profile, rules = load_config(config_path, args.profile)
    print_target(args.profile, profile)

    if args.dry_run:
        print("\nDry run complete. No database changes made.")
        return 0

    settings = load_database_settings()

    with connect(settings) as conn:
        check_schema(conn)

        if ops_has_data(conn):
            if not args.reset:
                raise RuntimeError(
                    "The ops schema already contains data. "
                    "Re-run with --reset to replace it."
                )
            reset_ops(conn)

    dependencies = build_dependencies(profile)
    dep_map = dependency_map(dependencies)

    with connect(settings) as conn:
        print("\nLoading dimensions...")

        chunked_copy(
            conn,
            """
            COPY ops.applications (
                application_id, application_name, domain,
                business_owner, technical_owner, criticality,
                sla_time, sla_timezone, active, created_at, updated_at
            ) FROM STDIN
            """,
            generate_applications(profile),
            args.batch_size,
            "applications",
            profile["applications"],
        )

        chunked_copy(
            conn,
            """
            COPY ops.data_sources (
                data_source_id, data_source_name, source_type,
                host_name, environment, criticality, active,
                created_at, updated_at
            ) FROM STDIN
            """,
            generate_data_sources(profile),
            args.batch_size,
            "data_sources",
            profile["data_sources"],
        )

        chunked_copy(
            conn,
            """
            COPY ops.application_dependencies (
                dependency_id, application_id, data_source_id,
                dependency_type, critical_path, active, created_at
            ) FROM STDIN
            """,
            dependencies,
            args.batch_size,
            "dependencies",
            profile["application_dependencies"],
        )

        print("\nLoading reload jobs...")

        chunked_copy(
            conn,
            """
            COPY ops.reload_jobs (
                reload_id, application_id, started_at, ended_at,
                status, duration_seconds, rows_loaded, trigger_type,
                node_name, attempt_number, sla_breached, created_at
            ) FROM STDIN
            """,
            generate_reload_jobs(profile, rules),
            args.batch_size,
            "reload_jobs",
            profile["reload_jobs"],
        )

    print("\nLoading high-volume reload logs...")
    inserted_logs = generate_reload_logs(
        settings,
        profile,
        rules,
        dep_map,
        args.batch_size,
    )

    with connect(settings) as conn:
        # At most one incident can be linked to each failed reload in this
        # synthetic model, so fetching up to the total incident count is enough.
        failed_reloads = fetch_failed_reloads(conn, profile["reload_jobs"])
        incidents = generate_incidents(profile, rules, failed_reloads)
        linked_incidents = sum(1 for row in incidents if row[2] is not None)
        print(
            f"Incident/reload links: {linked_incidents:,} / "
            f"{len(failed_reloads):,} failed reloads "
            f"({(100.0 * linked_incidents / len(failed_reloads)) if failed_reloads else 0:.2f}%)"
        )

        print("\nLoading incidents...")

        chunked_copy(
            conn,
            """
            COPY ops.incidents (
                incident_id, application_id, reload_id, opened_at, closed_at,
                severity, status, category, description,
                root_cause, detected_by, created_at, updated_at
            ) FROM STDIN
            """,
            incidents,
            args.batch_size,
            "incidents",
            profile["incidents"],
        )

        chunked_copy(
            conn,
            """
            COPY ops.incident_events (
                event_id, incident_id, occurred_at,
                event_type, source, message, created_at
            ) FROM STDIN
            """,
            generate_incident_events(profile, incidents),
            args.batch_size,
            "incident_events",
            profile["incident_events"],
        )

        chunked_copy(
            conn,
            """
            COPY ops.jira_tickets (
                ticket_id, jira_key, incident_id,
                created_at, updated_at, priority,
                status, assignee, summary, resolution
            ) FROM STDIN
            """,
            generate_jira(profile, incidents),
            args.batch_size,
            "jira_tickets",
            min(profile["jira_tickets"], profile["incidents"]),
        )

    print("\nGeneration complete.")
    print(f"Profile:        {args.profile}")
    print(f"Reload logs:    {inserted_logs:,}")
    print(f"Seed:           {profile['seed']}")
    print("Data is deterministic for the same profile + seed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nGeneration cancelled by user.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(
            f"\nERROR [{type(exc).__name__}]: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)
