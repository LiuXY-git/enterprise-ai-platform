"""A named, parameterized monthly SELECT over an application-selected demo DB."""

import argparse
import json
import math
import sqlite3
import time
from contextlib import closing, contextmanager
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

APPLICATION_ID = 6501
MAX_DB_BYTES = 5 * 1024 * 1024
QUERY_ID = "monthly_paid_sales_v1"
DATA_FILE = Path(__file__).with_name("sales-data.json")
SCHEMA = """
CREATE TABLE sales_orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    order_date TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK(amount_cents BETWEEN 0 AND 1000000000),
    status TEXT NOT NULL CHECK(status IN ('paid','cancelled','refunded'))
) STRICT;
CREATE INDEX sales_period_idx ON sales_orders(status, order_date, customer_id);
PRAGMA application_id=6501;
PRAGMA user_version=1;
"""
COLUMNS = (
    ("order_id", "TEXT"),
    ("customer_id", "TEXT"),
    ("order_date", "TEXT"),
    ("amount_cents", "INTEGER"),
    ("status", "TEXT"),
)
WHERE = """status = 'paid' AND order_date >= ? AND order_date < ?
AND (? IS NULL OR customer_id = ?)"""
SUMMARY_SQL = (
    "SELECT COUNT(*), COALESCE(SUM(amount_cents), 0) FROM sales_orders WHERE " + WHERE
)
DETAIL_SQL = (
    "SELECT order_id, customer_id, order_date, amount_cents, status FROM sales_orders WHERE "
    + WHERE
    + " ORDER BY order_date, order_id LIMIT ?"
)


class SalesError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SalesQuery(Contract):
    year: int = Field(ge=2020, le=2100, description="明确年份；不自行推断本月")
    month: int = Field(ge=1, le=12, description="月份，1到12")
    customer_id: str | None = Field(default=None, pattern=r"^C[0-9]{3}$")
    limit: int = Field(
        default=5, ge=1, le=20, description="明细最多条数，不限制全月汇总"
    )

    def period(self):
        start = date(self.year, self.month, 1)
        end = date(self.year + (self.month == 12), self.month % 12 + 1, 1)
        return start.isoformat(), end.isoformat()


class Order(Contract):
    order_id: str = Field(pattern=r"^SO-[0-9]{3,8}$")
    customer_id: str = Field(pattern=r"^C[0-9]{3}$")
    order_date: str
    amount_cents: int = Field(ge=0, le=1_000_000_000)
    status: Literal["paid", "cancelled", "refunded"]

    @field_validator("order_date")
    @classmethod
    def valid_date(cls, value):
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("invalid_date")
        return value


class Function(Contract):
    name: Literal["query_monthly_sales"]
    arguments: str = Field(min_length=1, max_length=2048)


class Call(Contract):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    type: Literal["function"]
    function: Function


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("non_standard_json_constant")


def validate_call(value):
    try:
        call = Call.model_validate(value)
        query = SalesQuery.model_validate(
            json.loads(
                call.function.arguments,
                object_pairs_hook=unique_object,
                parse_constant=reject_constant,
            )
        )
        return call, query
    except (ValueError, TypeError, RecursionError):
        raise SalesError("invalid_tool_arguments_or_call") from None


def tool_definitions():
    return [
        {
            "type": "function",
            "function": {
                "name": "query_monthly_sales",
                "description": "只读查询虚构销售库某月已支付订单的全量销售额与有限明细；不接受SQL或数据库路径。",
                "parameters": SalesQuery.model_json_schema(),
            },
        }
    ]


def create_demo(path: Path):
    """Explicit setup only: refuse to overwrite any existing file."""
    source = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    orders = [Order.model_validate(row).model_dump() for row in source["orders"]]
    path = path.resolve()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb"):
            pass
    except FileExistsError:
        raise SalesError("database_already_exists") from None
    except OSError:
        raise SalesError("database_setup_failed") from None
    try:
        with closing(sqlite3.connect(path)) as conn, conn:
            conn.executescript(SCHEMA)
            conn.executemany(
                "INSERT INTO sales_orders VALUES (:order_id,:customer_id,:order_date,:amount_cents,:status)",
                orders,
            )
    except sqlite3.Error:
        raise SalesError("database_setup_failed") from None


def read_authorizer(action, arg1, arg2, database, trigger):
    if trigger is not None:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_SELECT:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ and database == "main" and arg1 == "sales_orders":
        if arg2 in {name for name, _ in COLUMNS} | {""}:
            return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION and arg2 in {"count", "sum", "coalesce"}:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


class QueryBudget:
    def __init__(self, max_steps=100_000, timeout_seconds=0.5):
        if type(max_steps) is not int or not 1 <= max_steps <= 100_000:
            raise ValueError("invalid_query_budget")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(
            timeout_seconds, bool
        ):
            raise ValueError("invalid_query_timeout")
        if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 0.5:
            raise ValueError("invalid_query_timeout")
        self.max_steps = max_steps
        self.steps = 0
        self.interval = min(100, max_steps)
        self.deadline = time.monotonic() + timeout_seconds
        self.exceeded = False

    def check(self):
        self.steps += self.interval
        self.exceeded = (
            self.steps >= self.max_steps or time.monotonic() >= self.deadline
        )
        return int(self.exceeded)

    def ensure_time(self):
        if time.monotonic() >= self.deadline:
            self.exceeded = True
            raise SalesError("query_budget_exceeded")


@contextmanager
def open_readonly(path: Path, budget: QueryBudget):
    try:
        resolved = path.resolve()
        if not resolved.is_file():
            raise SalesError("database_missing")
        if resolved.stat().st_size > MAX_DB_BYTES:
            raise SalesError("database_too_large")
        with closing(
            sqlite3.connect(resolved.as_uri() + "?mode=ro", uri=True, timeout=0.2)
        ) as conn:
            conn.execute("PRAGMA query_only=ON")
            conn.execute("PRAGMA trusted_schema=OFF")
            conn.set_progress_handler(budget.check, budget.interval)
            # Both aggregate and detail queries see one consistent read snapshot.
            conn.execute("BEGIN")
            identity = conn.execute("PRAGMA application_id").fetchone()[0]
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            kind = conn.execute(
                "SELECT type FROM sqlite_master WHERE name='sales_orders'"
            ).fetchone()
            columns = tuple(
                (r[1], r[2]) for r in conn.execute("PRAGMA table_info(sales_orders)")
            )
            if (
                identity != APPLICATION_ID
                or version != 1
                or kind != ("table",)
                or columns != COLUMNS
            ):
                raise SalesError("database_schema_invalid")
            conn.set_authorizer(read_authorizer)
            budget.ensure_time()
            yield conn
            budget.ensure_time()
    except sqlite3.Error as exc:
        if (
            budget.exceeded
            or getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_INTERRUPT
        ):
            raise SalesError("query_budget_exceeded") from None
        raise SalesError("database_query_failed") from None
    except OSError:
        raise SalesError("database_unavailable") from None


class SalesTool:
    def __init__(self, database: Path, *, max_steps=100_000, timeout_seconds=0.5):
        self.database = database
        self.max_steps = max_steps
        self.timeout_seconds = timeout_seconds

    def query(self, parameters: dict) -> dict:
        try:
            args = SalesQuery.model_validate(parameters)
        except (ValueError, TypeError, RecursionError):
            raise SalesError("invalid_query_parameters") from None
        start, end = args.period()
        values = (start, end, args.customer_id, args.customer_id)
        budget = QueryBudget(self.max_steps, self.timeout_seconds)
        with open_readonly(self.database, budget) as conn:
            count, total = conn.execute(SUMMARY_SQL, values).fetchone()
            raw_rows = conn.execute(DETAIL_SQL, (*values, args.limit)).fetchall()
        try:
            if type(count) is not int or not 0 <= count <= 100_000:
                raise ValueError
            if type(total) is not int or not 0 <= total <= 100_000_000_000_000:
                raise ValueError
            rows = [
                Order.model_validate(
                    dict(zip((n for n, _ in COLUMNS), row, strict=True))
                ).model_dump()
                for row in raw_rows
            ]
            if (
                len(rows) != min(count, args.limit)
                or sum(r["amount_cents"] for r in rows) > total
            ):
                raise ValueError
        except (ValueError, TypeError):
            raise SalesError("invalid_database_result") from None
        return {
            "source": "day65-fictional-sales",
            "query_id": QUERY_ID,
            "period": {"start": start, "end_exclusive": end},
            "customer_id": args.customer_id,
            "order_status": "paid",
            "currency": "CNY",
            "data_status": "ok" if count else "no_data",
            "order_count": count,
            "total_cents": total,
            "total_yuan": f"{total // 100}.{total % 100:02d}",
            "orders": rows,
            "rows_returned": len(rows),
            "truncated": count > len(rows),
            "read_only": True,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    init = commands.add_parser("init-demo", help="Create a NEW fictional SQLite file")
    init.add_argument("--db", type=Path, required=True)
    query = commands.add_parser(
        "query", help="Execute one fixed SELECT template without a model"
    )
    query.add_argument("--db", type=Path, required=True)
    query.add_argument("--year", type=int, required=True)
    query.add_argument("--month", type=int, required=True)
    query.add_argument("--customer-id")
    query.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    try:
        if args.operation == "init-demo":
            create_demo(args.db)
            result = {"status": "demo_created", "fictional": True, "orders": 7}
        else:
            result = SalesTool(args.db).query(
                {
                    "year": args.year,
                    "month": args.month,
                    "customer_id": args.customer_id,
                    "limit": args.limit,
                }
            )
    except SalesError as exc:
        print(json.dumps({"status": "rejected", "error": exc.code}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
