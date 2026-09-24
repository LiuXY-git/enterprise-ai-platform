"""Reuse the three reviewed tools with application-owned scope and resources."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for day in (64, 65, 66, 67):
    sys.path.insert(0, str(ROOT / f"experiments/day{day}"))
import knowledge_tool as knowledge  # noqa: E402
import sales_sql as sales  # noqa: E402
import weather_api as weather  # noqa: E402

SQL = "query_monthly_sales"
KNOWLEDGE = "search_knowledge"
WEATHER = "get_weather_forecast"
NAMES = (SQL, KNOWLEDGE, WEATHER)
MODULES = {SQL: sales, KNOWLEDGE: knowledge, WEATHER: weather}
SAFE_ERRORS = {
    "database_missing",
    "database_too_large",
    "database_schema_invalid",
    "database_query_failed",
    "database_unavailable",
    "invalid_database_result",
    "query_budget_exceeded",
    "invalid_query_parameters",
    "embedding_cache_missing",
    "knowledge_store_missing",
    "knowledge_collection_missing",
    "retrieval_failed",
    "retrieval_timeout",
    "retrieval_response_too_large",
    "invalid_retrieval_result",
    "weather_data_unavailable",
    "api_invalid_response",
    "invalid_clock",
    "api_elapsed_budget_exceeded",
    "api_invalid_content_type",
    "api_unexpected_compression",
    "api_response_too_large",
    "api_timeout",
    "api_network_error",
}


class OrchestrationError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def scope_for(case):
    if case not in {
        "full",
        "no_sales",
        "weather_timeout",
        "knowledge_empty",
        "sql_error",
    }:
        raise ValueError("unknown_case")
    return {
        "sales": {
            "year": 2026,
            "month": 7 if case == "no_sales" else 9,
            "customer_id": None,
            "limit": 2,
        },
        "weather": {"city": "shanghai", "days": 1},
    }


def definitions(names=NAMES):
    return [MODULES[name].tool_definitions()[0] for name in names]


class Registry:
    def __init__(self, bindings, scope):
        if set(bindings) != set(NAMES):
            raise ValueError("all_three_tools_required")
        self.bindings = dict(bindings)
        self.scope = json.loads(json.dumps(scope))

    def validate(self, raw):
        try:
            name = raw["function"]["name"]
            if name not in MODULES:
                raise ValueError
            call, args = MODULES[name].validate_call(raw)
            params = args.model_dump()
        except (ValueError, TypeError, KeyError, RecursionError):
            raise OrchestrationError("invalid_tool_call_or_arguments") from None
        if name == SQL and params != self.scope["sales"]:
            raise OrchestrationError("tool_arguments_out_of_scope")
        if name == WEATHER and params != self.scope["weather"]:
            raise OrchestrationError("tool_arguments_out_of_scope")
        return call.model_dump(), params

    def execute(self, name, params):
        try:
            value = self.bindings[name].query(params)
            serialized = json.dumps(value, ensure_ascii=False, allow_nan=False)
            if not isinstance(value, dict) or len(serialized) > 12000:
                raise ValueError
            # The adapters already validate their complete result. Verify routing
            # fields too, so a broken application binding cannot advance the graph.
            if name == SQL:
                count = value["order_count"]
                if (
                    type(count) is not int
                    or count < 0
                    or value["data_status"] != ("ok" if count else "no_data")
                ):
                    raise ValueError
            if name == KNOWLEDGE:
                rows = value["evidence"]
                if not isinstance(rows, list) or value["returned_count"] != len(rows):
                    raise ValueError
                labels = [row["citation"] for row in rows]
                if labels != [f"K{i + 1}" for i in range(len(rows))] or len(rows) > 5:
                    raise ValueError
            return {"status": "ok", "result": value}
        except (
            sales.SalesError,
            knowledge.KnowledgeError,
            weather.WeatherError,
        ) as exc:
            code = exc.code
            if not isinstance(code, str) or (
                code not in SAFE_ERRORS
                and not re.fullmatch(r"api_http_[1-5][0-9]{2}", code)
            ):
                code = "tool_execution_failed"
            return {"status": "error", "error": code}
        except Exception:
            return {"status": "error", "error": "tool_execution_failed"}

    @property
    def api_network_requests(self):
        return getattr(self.bindings[WEATHER], "network_requests", 0)


def make_registry(database, case, *, live=False):
    if live and case != "full":
        raise ValueError("only_full_case_supports_live")
    sql = sales.SalesTool(
        database if case != "sql_error" else database.with_name("missing.sqlite")
    )
    search = (
        knowledge.HubRetriever("hub-demo")
        if live
        else knowledge.FixtureRetriever(
            "empty" if case == "knowledge_empty" else "supported"
        )
    )
    weather_tool = (
        weather.WeatherTool()
        if live
        else weather.fixture_tool(
            failure="timeout" if case == "weather_timeout" else None
        )
    )
    return Registry(
        {
            SQL: sql,
            KNOWLEDGE: knowledge.KnowledgeTool(
                search, backend_label="hub-demo" if live else "fixture"
            ),
            WEATHER: weather_tool,
        },
        scope_for(case),
    )
