"""Disposable disk-backed rows and exact arithmetic for reporting."""

import base64
import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal, localcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID
from typing import Any, Callable


def exact_add(left, right):
    if not left.is_finite() or not right.is_finite():
        return left + right
    with localcontext() as context:
        context.prec = (
            max(left.adjusted(), right.adjusted(), 0)
            - min(left.as_tuple().exponent, right.as_tuple().exponent, 0)
            + 2
        )
        return left + right


class DecimalSum:
    def __init__(self):
        self.value = None

    def step(self, value):
        if value is not None:
            number = Decimal(value)
            self.value = (
                number if self.value is None else exact_add(self.value, number)
            )

    def finalize(self):
        return None if self.value is None else str(self.value)


class DecimalMax(DecimalSum):
    def step(self, value):
        if value is not None:
            number = Decimal(value)
            if (
                self.value is None
                or number.is_nan()
                or (not self.value.is_nan() and number > self.value)
            ):
                self.value = number


def fields(definition):
    return dict(
        part.strip().split(" ", 1)
        for part in re.split(r",\s*(?![^()]*\))", definition)
    )


def encode(value):
    """A typed envelope for output rows, without global adapter registrations."""
    if isinstance(value, Decimal):
        return ["decimal", str(value)]
    if isinstance(value, datetime):
        return ["datetime", value.isoformat()]
    if isinstance(value, date):
        return ["date", value.isoformat()]
    if isinstance(value, UUID):
        return ["uuid", str(value)]
    if isinstance(value, bytes):
        return ["bytes", base64.b64encode(value).decode()]
    if isinstance(value, (list, tuple)):
        return ["list", [encode(item) for item in value]]
    if isinstance(value, dict):
        return ["dict", {key: encode(item) for key, item in value.items()}]
    if value is None or isinstance(value, (str, int, float, bool)):
        return ["scalar", value]
    raise TypeError(f"Unsupported report value type: {type(value).__name__}")


def decode(value):
    kind, item = value
    converters: dict[str, Callable[[str], Any]] = {
        "decimal": Decimal,
        "date": date.fromisoformat,
        "datetime": datetime.fromisoformat,
        "uuid": UUID,
        "bytes": base64.b64decode,
    }
    if kind == "list":
        return [decode(element) for element in item]
    if kind == "dict":
        return {key: decode(element) for key, element in item.items()}
    return converters[kind](item) if kind in converters else item


def restore(value, kind):
    if value is None:
        return None
    if kind.startswith("numeric"):
        return Decimal(value)
    if kind == "date":
        return date.fromisoformat(value)
    if kind in ("integer", "bigint"):
        return int(value)
    if kind == "array":
        return json.loads(value)
    return value


class DiskRows:
    """Repeatable row iteration; never retain the complete result in RAM."""

    def __init__(self, store, name, columns):
        self.store, self.name, self.columns = store, name, columns

    def __iter__(self):
        cursor = self.store.con.execute(
            f'SELECT payload FROM "{self.name}" ORDER BY rowid'
        )
        try:
            for (payload,) in cursor:
                yield decode(json.loads(payload))
        finally:
            if not self.store.closed:
                cursor.close()

    def __len__(self):
        return self.store.con.execute(
            f'SELECT count(*) FROM "{self.name}"'
        ).fetchone()[0]

    def __eq__(self, other):
        from itertools import zip_longest

        sentinel = object()
        return all(
            left == right
            for left, right in zip_longest(self, other, fillvalue=sentinel)
        )


class TupleRows:
    def __init__(self, rows):
        self.rows = rows

    def __iter__(self):
        return (tuple(row.values()) for row in self.rows)

    def __len__(self):
        return len(self.rows)

    def __eq__(self, other):
        from itertools import zip_longest

        sentinel = object()
        return all(
            left == right
            for left, right in zip_longest(self, other, fillvalue=sentinel)
        )


class Store:
    def __init__(self, directory=None):
        self.closed = False
        self.directory = TemporaryDirectory(
            prefix="koku-daily-", dir=directory
        )
        self.path = Path(self.directory.name) / "staging.db"
        try:
            self.con = sqlite3.connect(self.path)
            for pragma in (
                "journal_mode=DELETE",
                "synchronous=OFF",
                "locking_mode=EXCLUSIVE",
                "temp_store=FILE",
                "cache_size=-16384",
                "cache_spill=ON",
            ):
                self.con.execute("PRAGMA " + pragma)
            self.con.create_aggregate("decimal_sum", 1, DecimalSum)
            self.con.create_aggregate("decimal_max", 1, DecimalMax)
            self.con.create_function(
                "md5", 1, lambda value: hashlib.md5(value.encode()).hexdigest()
            )
            self.schemas = {}
        except BaseException:
            self.directory.cleanup()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        if not self.closed:
            self.con.close()
            self.closed = True
            self.directory.cleanup()

    @contextmanager
    def attempt(self):
        self.con.execute("SAVEPOINT attempt")
        try:
            yield
        except BaseException:
            # SQLITE_FULL may already have rolled back the entire transaction.
            if self.con.in_transaction:
                self.con.execute("ROLLBACK TO attempt")
                self.con.execute("RELEASE attempt")
            raise
        else:
            self.con.execute("RELEASE attempt")

    def create(self, name, schema):
        self.schemas[name] = schema
        # Identifiers are repository-owned descriptors, never external input.
        columns = ", ".join(
            f'"{key}" '
            + ("INTEGER" if kind in ("integer", "bigint") else "TEXT")
            for key, kind in schema.items()
        )
        self.con.execute(f'CREATE TABLE "{name}" ({columns})')
        self.con.commit()

    def insert(self, name, rows):
        schema = self.schemas[name]

        def values(row):
            for key, kind in schema.items():
                value = row.get(key)
                if kind.startswith("numeric") and isinstance(value, float):
                    raise TypeError(
                        "Floating-point values cannot stage exact numeric columns"
                    )
                if value is not None:
                    if isinstance(value, (Decimal, UUID)):
                        value = str(value)
                    elif isinstance(value, date):
                        value = value.isoformat()
                    elif kind == "array":
                        value = json.dumps(value)
                yield value

        marks = ",".join("?" for _ in schema)
        self.con.executemany(
            f'INSERT INTO "{name}" VALUES ({marks})',
            (tuple(values(row)) for row in rows),
        )

    def select(self, sql, schema):
        cursor = self.con.execute(sql)
        columns = [item[0] for item in cursor.description]

        def rows():
            try:
                for row in cursor:
                    yield {
                        key: restore(value, schema.get(key, "text"))
                        for key, value in zip(columns, row)
                    }
            finally:
                cursor.close()

        return columns, rows()

    def overlay(self, name, rows):
        with self.attempt():
            for row in rows:
                self.con.execute(
                    f'DELETE FROM "{name}" WHERE date = ?',
                    (row["date"].isoformat(),),
                )
                self.insert(name, [row])

    def output(self, name, columns, rows):
        self.con.execute(f'CREATE TABLE "{name}" (payload TEXT NOT NULL)')
        self.con.executemany(
            f'INSERT INTO "{name}" VALUES (?)',
            ((json.dumps(encode(row)),) for row in rows),
        )
        return DiskRows(self, name, columns)


class ReportBundle(dict):
    def __init__(self, store):
        super().__init__()
        self.store = store

    def close(self):
        self.store.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
