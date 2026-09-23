"""Day 67: bounded GET requests to a fixed public weather endpoint."""

import argparse
import json
import math
import time
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

ENDPOINT = "https://api.open-meteo.com/v1/forecast"
SOURCE = "https://open-meteo.com/"
LOCAL_ZONE = timezone(timedelta(hours=8))
FIXTURE_NOW = datetime(2026, 9, 23, 0, 0, tzinfo=UTC)
MAX_BYTES = 65536
ELAPSED_BUDGET = 15.0
CITIES = {
    "beijing": ("北京", 39.9042, 116.4074),
    "shanghai": ("上海", 31.2304, 121.4737),
    "guangzhou": ("广州", 23.1291, 113.2644),
}
FIELDS = ["temperature_2m_max", "temperature_2m_min", "precipitation_probability_max"]


class WeatherError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class WeatherArguments(Contract):
    city: Literal["beijing", "shanghai", "guangzhou"]
    days: int = Field(default=1, ge=1, le=3)


class Function(Contract):
    name: Literal["get_weather_forecast"]
    arguments: str = Field(min_length=1, max_length=1024)


class Call(Contract):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    type: Literal["function"]
    function: Function


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError("non_standard_number")


def parse_json(value):
    return json.loads(
        value, object_pairs_hook=unique_object, parse_constant=invalid_constant
    )


def validate_call(value):
    try:
        call = Call.model_validate(value)
        return call, WeatherArguments.model_validate(
            parse_json(call.function.arguments)
        )
    except (ValueError, TypeError, RecursionError):
        raise WeatherError("invalid_tool_call_or_arguments") from None


def tool_definitions():
    return [
        {
            "type": "function",
            "function": {
                "name": "get_weather_forecast",
                "description": "查询北京(beijing)、上海(shanghai)、广州(guangzhou)从当地今天开始1至3天的天气预报。只有city和days参数，不接受URL、凭据或任意城市。",
                "parameters": WeatherArguments.model_json_schema(),
            },
        }
    ]


def number(value, low, high):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise ValueError("invalid_number")
    return value


def normalize(payload, args, requested_at):
    """Validate geographic, temporal, unit and parallel-array consistency."""
    try:
        if not isinstance(payload, dict) or payload.get("error"):
            raise ValueError
        _, latitude, longitude = CITIES[args.city]
        lat = number(payload["latitude"], -90, 90)
        lon = number(payload["longitude"], -180, 180)
        if abs(lat - latitude) > 0.5 or abs(lon - longitude) > 0.5:
            raise ValueError
        if (
            payload["timezone"] != "Asia/Shanghai"
            or type(payload["utc_offset_seconds"]) is not int
            or payload["utc_offset_seconds"] != 28800
        ):
            raise ValueError
        units, daily = payload["daily_units"], payload["daily"]
        if not isinstance(units, dict) or not isinstance(daily, dict):
            raise ValueError
        if any(
            units.get(key) != expected
            for key, expected in {
                "time": "iso8601",
                FIELDS[0]: "°C",
                FIELDS[1]: "°C",
                FIELDS[2]: "%",
            }.items()
        ):
            raise ValueError
        for key in ["time", *FIELDS]:
            if not isinstance(daily.get(key), list) or len(daily[key]) != args.days:
                raise ValueError
        start = requested_at.astimezone(LOCAL_ZONE).date()
        days = []
        for index in range(args.days):
            raw_day = daily["time"][index]
            if (
                not isinstance(raw_day, str)
                or raw_day != (start + timedelta(days=index)).isoformat()
            ):
                raise ValueError
            date.fromisoformat(raw_day)
            values = [daily[key][index] for key in FIELDS]
            if any(value is None for value in values):
                raise WeatherError("weather_data_unavailable")
            high, low = number(values[0], -100, 60), number(values[1], -100, 60)
            probability = number(values[2], 0, 100)
            if low > high:
                raise ValueError
            days.append(
                {
                    "date": raw_day,
                    "temperature_min_c": low,
                    "temperature_max_c": high,
                    "precipitation_probability_max_percent": probability,
                }
            )
        return {
            "city": args.city,
            "city_name": CITIES[args.city][0],
            "timezone": "Asia/Shanghai",
            "forecast_days": days,
            "source": "Open-Meteo",
            "source_url": SOURCE,
            "requested_at_utc": requested_at.astimezone(UTC).isoformat(),
            "data_kind": "forecast_not_observation",
            "attribution": "Weather data by Open-Meteo (CC BY 4.0)",
            "returned_grid": {"latitude": lat, "longitude": lon},
        }
    except WeatherError:
        raise
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError):
        raise WeatherError("api_invalid_response") from None


class WeatherTool:
    """Transport and clocks are application-owned test seams, never model arguments."""

    def __init__(self, *, transport=None, now=None, monotonic=None):
        self.transport = transport
        self.now = now or (lambda: datetime.now(UTC))
        self.monotonic = monotonic or time.monotonic
        self.request_attempts = 0
        self.network_requests = 0

    def query(self, parameters):
        try:
            args = WeatherArguments.model_validate(parameters)
        except (ValueError, TypeError):
            raise WeatherError("invalid_query_parameters") from None
        requested_at = self.now()
        if not isinstance(requested_at, datetime) or requested_at.tzinfo is None:
            raise WeatherError("invalid_clock")
        _, latitude, longitude = CITIES[args.city]
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": ",".join(FIELDS),
            "forecast_days": args.days,
            "timezone": "Asia/Shanghai",
            "temperature_unit": "celsius",
        }
        started = self.monotonic()

        def check_elapsed():
            if self.monotonic() - started > ELAPSED_BUDGET:
                raise WeatherError("api_elapsed_budget_exceeded")

        try:
            with httpx.Client(
                transport=self.transport,
                follow_redirects=False,
                trust_env=False,
                timeout=httpx.Timeout(10.0, connect=5.0, pool=5.0),
            ) as client:
                self.request_attempts += 1
                self.network_requests += int(self.transport is None)
                with client.stream(
                    "GET",
                    ENDPOINT,
                    params=params,
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "identity",
                    },
                ) as response:
                    check_elapsed()
                    if response.status_code != 200:
                        raise WeatherError(f"api_http_{response.status_code}")
                    if (
                        response.headers.get("content-type", "")
                        .split(";")[0]
                        .strip()
                        .lower()
                        != "application/json"
                    ):
                        raise WeatherError("api_invalid_content_type")
                    if (
                        response.headers.get("content-encoding", "identity").lower()
                        != "identity"
                    ):
                        raise WeatherError("api_unexpected_compression")
                    length = response.headers.get("content-length")
                    if length is not None:
                        if not length.isascii() or not length.isdigit():
                            raise WeatherError("api_invalid_response")
                        if int(length) > MAX_BYTES:
                            raise WeatherError("api_response_too_large")
                    content = bytearray()
                    for chunk in response.iter_bytes(chunk_size=4096):
                        check_elapsed()
                        content.extend(chunk)
                        if len(content) > MAX_BYTES:
                            raise WeatherError("api_response_too_large")
                    check_elapsed()
                    payload = parse_json(bytes(content))
        except WeatherError:
            raise
        except httpx.TimeoutException:
            raise WeatherError("api_timeout") from None
        except httpx.RequestError:
            raise WeatherError("api_network_error") from None
        except (ValueError, TypeError, RecursionError, UnicodeError):
            raise WeatherError("api_invalid_response") from None
        result = normalize(payload, args, requested_at)
        result["data_mode"] = "mock_http" if self.transport is not None else "live_api"
        return result


def fixture_payload(city="beijing", days=1):
    _, lat, lon = CITIES[city]
    return {
        "latitude": lat,
        "longitude": lon,
        "timezone": "Asia/Shanghai",
        "utc_offset_seconds": 28800,
        "daily_units": {
            "time": "iso8601",
            FIELDS[0]: "°C",
            FIELDS[1]: "°C",
            FIELDS[2]: "%",
        },
        "daily": {
            "time": [
                (FIXTURE_NOW.date() + timedelta(days=i)).isoformat()
                for i in range(days)
            ],
            FIELDS[0]: [25.0, 26.0, 24.0][:days],
            FIELDS[1]: [18.0, 19.0, 17.0][:days],
            FIELDS[2]: [20, 40, 70][:days],
        },
    }


def fixture_tool(*, failure=None):
    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("synthetic timeout", request=request)
        if failure == "rate_limit":
            return httpx.Response(429, json={"reason": "synthetic rate limit"})
        city = next(
            key
            for key, (_, lat, _) in CITIES.items()
            if float(request.url.params["latitude"]) == lat
        )
        return httpx.Response(
            200, json=fixture_payload(city, int(request.url.params["forecast_days"]))
        )

    return WeatherTool(transport=httpx.MockTransport(handler), now=lambda: FIXTURE_NOW)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", choices=list(CITIES), default="beijing")
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument(
        "--live-api",
        action="store_true",
        help="Make one real public API request without an LLM",
    )
    args = parser.parse_args()
    tool = WeatherTool() if args.live_api else fixture_tool()
    try:
        value = tool.query({"city": args.city, "days": args.days})
        result = {"status": "completed", "result": value}
    except WeatherError as exc:
        result = {"status": "rejected", "error": exc.code}
    result.update(
        api_request_attempts=tool.request_attempts,
        api_network_requests=tool.network_requests,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
