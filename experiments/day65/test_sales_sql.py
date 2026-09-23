"""Execute real SQLite operations on temporary fictional databases only."""

import hashlib
import json
import sqlite3
from contextlib import closing

import pytest
import sales_sql
from sales_sql import (
    QueryBudget,
    SalesError,
    SalesQuery,
    SalesTool,
    create_demo,
    open_readonly,
    tool_definitions,
    validate_call,
)


@pytest.fixture
def database(tmp_path):
    # Spaces, Unicode and # exercise URI escaping on Windows.
    path = tmp_path / "销售 data #1.sqlite"
    create_demo(path)
    return path


def params(**changes):
    return {"year": 2026, "month": 9, "customer_id": None, "limit": 2, **changes}


def call(arguments=None, **changes):
    result = {
        "id": "call_sales",
        "type": "function",
        "function": {
            "name": "query_monthly_sales",
            "arguments": json.dumps(params()) if arguments is None else arguments,
        },
    }
    result.update(changes)
    return result


def test_monthly_sum_is_not_limited_by_detail_limit(database):
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    result = SalesTool(database).query(params())
    assert result["order_count"] == 4
    assert result["total_cents"] == 300000 and result["total_yuan"] == "3000.00"
    assert result["rows_returned"] == 2 and result["truncated"] is True
    assert [row["order_id"] for row in result["orders"]] == ["SO-001", "SO-002"]
    assert sum(row["amount_cents"] for row in result["orders"]) == 205000
    assert result["period"] == {"start": "2026-09-01", "end_exclusive": "2026-10-01"}
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before


def test_customer_filter_and_paid_status(database):
    result = SalesTool(database).query(params(customer_id="C001", limit=5))
    assert result["order_count"] == 2 and result["total_yuan"] == "1550.00"
    assert result["truncated"] is False
    assert {r["customer_id"] for r in result["orders"]} == {"C001"}
    assert SalesTool(database).query(params(customer_id="C002"))["total_cents"] == 85000


@pytest.mark.parametrize("changes", [{"month": 7}, {"customer_id": "C999"}])
def test_empty_is_valid_no_data_not_a_database_error(database, changes):
    result = SalesTool(database).query(params(**changes))
    assert result["data_status"] == "no_data" and result["total_cents"] == 0
    assert result["order_count"] == 0 and result["orders"] == []
    assert result["truncated"] is False


@pytest.mark.parametrize(
    "changes",
    [
        {"year": True},
        {"year": "2026"},
        {"year": 2026.0},
        {"year": 2019},
        {"year": 2101},
        {"month": 0},
        {"month": 13},
        {"month": False},
        {"month": "9"},
        {"limit": 0},
        {"limit": 21},
        {"limit": True},
        {"limit": 1.5},
        {"customer_id": "C001' OR 1=1--"},
        {"customer_id": "../data"},
        {"customer_id": ["C001"]},
        {"customer_id": 1},
        {"customer_id": ""},
        {"sql": "DROP TABLE sales_orders"},
        {"db": "secrets.sqlite"},
        {"status": "cancelled"},
    ],
)
def test_bad_parameters_fail_before_database_open(monkeypatch, tmp_path, changes):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid arguments reached SQLite")

    monkeypatch.setattr(sales_sql.sqlite3, "connect", forbidden)
    with pytest.raises(SalesError, match="^invalid_query_parameters$"):
        SalesTool(tmp_path / "missing.sqlite").query(params(**changes))


@pytest.mark.parametrize("field", ["year", "month"])
def test_missing_required_parameter_is_rejected(database, field):
    query = params()
    del query[field]
    with pytest.raises(SalesError, match="invalid_query_parameters"):
        SalesTool(database).query(query)


@pytest.mark.parametrize(
    "raw",
    [
        "not JSON",
        "[]",
        "null",
        '{"year":2026,"year":2025,"month":9}',
        '{"year":2026,"month":NaN}',
        '{"year":2026,"month":Infinity}',
        " " * 2049,
    ],
)
def test_invalid_tool_json_is_rejected(raw):
    with pytest.raises(SalesError, match="invalid_tool_arguments_or_call"):
        validate_call(call(raw))


@pytest.mark.parametrize(
    "change",
    [
        {"id": ""},
        {"id": "bad/id"},
        {"id": "x" * 129},
        {"type": "shell"},
        {"sql": "SELECT 1"},
        {"function": {"name": "execute_sql", "arguments": "{}"}},
    ],
)
def test_invalid_tool_identity_is_rejected(change):
    with pytest.raises(SalesError):
        validate_call(call(**change))


@pytest.mark.parametrize(
    "year,month,expected",
    [
        (2024, 2, ("2024-02-01", "2024-03-01")),
        (2026, 12, ("2026-12-01", "2027-01-01")),
        (2100, 12, ("2100-12-01", "2101-01-01")),
    ],
)
def test_date_range_handles_leap_year_and_december(year, month, expected):
    assert SalesQuery(year=year, month=month).period() == expected


def test_schema_never_accepts_sql_or_database_path():
    definition = tool_definitions()[0]["function"]
    assert definition["name"] == "query_monthly_sales"
    schema = definition["parameters"]
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {"year", "month", "customer_id", "limit"}


def test_no_overwrite_and_missing_database_not_created(database, tmp_path):
    before = database.read_bytes()
    with pytest.raises(SalesError, match="database_already_exists"):
        create_demo(database)
    assert database.read_bytes() == before
    missing = tmp_path / "absent.sqlite"
    with pytest.raises(SalesError, match="database_missing"):
        SalesTool(missing).query(params())
    assert not missing.exists()


@pytest.mark.parametrize("kind", ["corrupt", "unmarked", "wrong_version", "view"])
def test_incompatible_database_rejected_without_path_leak(database, tmp_path, kind):
    if kind == "corrupt":
        database.write_bytes(b"not a sqlite file")
    else:
        with closing(sqlite3.connect(database)) as conn, conn:
            if kind == "unmarked":
                conn.execute("PRAGMA application_id=0")
            elif kind == "wrong_version":
                conn.execute("PRAGMA user_version=2")
            else:
                conn.execute("DROP TABLE sales_orders")
                conn.execute("CREATE VIEW sales_orders AS SELECT 1 AS order_id")
    with pytest.raises(SalesError) as error:
        SalesTool(database).query(params())
    assert error.value.code in {"database_schema_invalid", "database_query_failed"}
    assert str(tmp_path) not in str(error.value)


def test_oversized_database_rejected(tmp_path):
    path = tmp_path / "large.sqlite"
    with path.open("wb") as output:
        output.truncate(sales_sql.MAX_DB_BYTES + 1)
    with pytest.raises(SalesError, match="database_too_large"):
        SalesTool(path).query(params())


@pytest.mark.parametrize(
    "statement",
    [
        "DELETE FROM sales_orders",
        "UPDATE sales_orders SET amount_cents=0",
        "CREATE TABLE evil(x)",
        "DROP TABLE sales_orders",
        "ATTACH DATABASE ':memory:' AS another",
        "PRAGMA query_only=OFF",
        "SELECT name FROM sqlite_master",
        "SELECT randomblob(100)",
        "SELECT load_extension('not-a-library')",
    ],
)
def test_authorizer_denies_unapproved_operations(database, statement):
    before = database.read_bytes()
    with pytest.raises(SalesError, match="database_query_failed"):
        with open_readonly(database, QueryBudget()) as conn:
            conn.execute(statement).fetchall()
    assert database.read_bytes() == before


def test_uri_mode_is_readonly_even_without_authorizer_or_query_only(database):
    before = database.read_bytes()
    with pytest.raises(SalesError, match="database_query_failed"):
        with open_readonly(database, QueryBudget()) as conn:
            conn.set_authorizer(None)
            conn.execute("PRAGMA query_only=OFF")
            conn.execute("DELETE FROM sales_orders")
    assert database.read_bytes() == before


def test_vm_budget_interrupts_actual_query(database):
    with pytest.raises(SalesError, match="query_budget_exceeded"):
        SalesTool(database, max_steps=1).query(params())


def test_elapsed_budget_interrupts_actual_query(database, monkeypatch):
    ticks = iter([0.0, 1.0, 1.0, 1.0])
    monkeypatch.setattr(sales_sql.time, "monotonic", lambda: next(ticks, 1.0))
    with pytest.raises(SalesError, match="query_budget_exceeded"):
        SalesTool(database, max_steps=100_000).query(params())


def test_locked_database_is_error_not_zero_sales(database):
    with closing(sqlite3.connect(database)) as lock:
        lock.execute("BEGIN EXCLUSIVE")
        try:
            with pytest.raises(SalesError, match="database_query_failed"):
                SalesTool(database).query(params())
        finally:
            lock.rollback()


def test_connection_closes_even_when_query_fails(database, monkeypatch):
    monkeypatch.setattr(
        sales_sql, "SUMMARY_SQL", "SELECT not_a_column FROM sales_orders"
    )
    with pytest.raises(SalesError):
        SalesTool(database).query(params())
    renamed = database.with_suffix(".moved")
    database.rename(renamed)
    renamed.rename(database)


def test_existing_demo_data_is_really_read_not_a_hardcoded_total(database):
    with closing(sqlite3.connect(database)) as conn, conn:
        conn.execute(
            "UPDATE sales_orders SET amount_cents=120001 WHERE order_id='SO-001'"
        )
    assert SalesTool(database).query(params())["total_yuan"] == "3000.01"


def test_tool_json_defaults_are_explicit_after_validation():
    _, query = validate_call(call('{"year":2026,"month":9}'))
    assert query.model_dump() == params(limit=5)


def test_bad_database_row_is_rejected(database):
    with closing(sqlite3.connect(database)) as conn, conn:
        conn.execute(
            "UPDATE sales_orders SET customer_id='bad-id' WHERE order_id='SO-001'"
        )
    with pytest.raises(SalesError, match="invalid_database_result"):
        SalesTool(database).query(params())
