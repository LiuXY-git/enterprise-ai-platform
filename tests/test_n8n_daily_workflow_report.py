import json
from pathlib import Path

WORKFLOW_PATH = (
    Path(__file__).parents[1] / "n8n" / "workflows" / "w6d40-daily-workflow-report.json"
)


def load_workflow() -> dict:
    return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))


def node_by_name(workflow: dict, name: str) -> dict:
    return next(node for node in workflow["nodes"] if node["name"] == name)


def test_daily_report_workflow_is_portable_and_inactive() -> None:
    workflow = load_workflow()
    serialized = json.dumps(workflow)

    assert workflow["active"] is False
    assert workflow["pinData"] == {}
    assert not {"id", "versionId", "meta"} & workflow.keys()
    assert all("webhookId" not in node for node in workflow["nodes"])
    assert all("credentials" not in node for node in workflow["nodes"])
    assert "openAiApi" not in serialized
    assert "instanceId" not in serialized


def test_daily_report_workflow_has_expected_nodes_and_triggers() -> None:
    workflow = load_workflow()
    schedule = node_by_name(workflow, "Daily Report Schedule")
    webhook = node_by_name(workflow, "Manual Report Replay")

    assert workflow["name"] == "W6D40 - Daily Workflow Report"
    assert len(workflow["nodes"]) == 7
    assert schedule["parameters"]["rule"]["interval"] == [{"triggerAtHour": 18}]
    assert webhook["parameters"]["httpMethod"] == "POST"
    assert webhook["parameters"]["path"] == "w6d40-daily-workflow-report"
    assert webhook["parameters"]["responseMode"] == "lastNode"


def test_daily_report_workflow_connections_reference_existing_nodes() -> None:
    workflow = load_workflow()

    for source, connection_types in workflow["connections"].items():
        assert node_by_name(workflow, source)
        for outputs in connection_types.values():
            for output in outputs:
                for target in output:
                    assert node_by_name(workflow, target["node"])

    model_targets = workflow["connections"]["DashScope Qwen Chat Model"]
    assert model_targets["ai_languageModel"][0][0]["node"] == (
        "Generate Daily Report Summary"
    )


def test_report_context_validates_real_dates_and_timezone() -> None:
    workflow = load_workflow()
    code = node_by_name(workflow, "Prepare Report Context")["parameters"]["jsCode"]

    assert "Asia/Shanghai" in code
    assert "isValidDate" in code
    assert "parsed.toISOString().slice(0, 10) === value" in code
    assert "report_date must be a valid YYYY-MM-DD date" in code
    assert "manual_replay" in code
    assert "schedule" in code


def test_fixed_runs_and_aggregation_contract_are_stable() -> None:
    workflow = load_workflow()
    loader = node_by_name(workflow, "Load Fixed Workflow Runs")["parameters"]["jsCode"]
    aggregator = node_by_name(workflow, "Aggregate Daily Metrics")["parameters"][
        "jsCode"
    ]

    assert loader.count("mail-report-") == 9
    assert "selectedRuns" in loader
    assert "run.report_date === context.report_date" in loader
    for field in {
        "total_runs",
        "succeeded_runs",
        "failed_runs",
        "success_rate",
        "average_elapsed_time",
        "total_tokens",
        "category_distribution",
        "failed_event_ids",
    }:
        assert field in aggregator
    assert "totalRuns > 0" in aggregator
    assert "toFixed(2)" in aggregator


def test_native_llm_chain_uses_qwen_and_guarded_prompt() -> None:
    workflow = load_workflow()
    chain = node_by_name(workflow, "Generate Daily Report Summary")
    model = node_by_name(workflow, "DashScope Qwen Chat Model")
    prompt = chain["parameters"]["text"]

    assert chain["type"] == "@n8n/n8n-nodes-langchain.chainLlm"
    assert prompt.startswith("={{")
    assert not prompt.startswith("=={{")
    assert "不得补造任何数字" in prompt
    assert "无执行数据，不适用" in prompt
    assert "无法据此评估系统稳定性" in prompt
    assert model["type"] == "@n8n/n8n-nodes-langchain.lmChatOpenAi"
    assert model["parameters"]["model"]["value"] == "qwen3.7-plus"
    assert model["parameters"]["responsesApiEnabled"] is False
    assert model["parameters"]["options"] == {
        "maxTokens": 1000,
        "temperature": 0.2,
    }
