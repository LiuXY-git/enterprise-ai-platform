from backend.app.main import app


def test_openapi_metadata() -> None:
    schema = app.openapi()
    info = schema["info"]

    assert info["title"] == "Enterprise AI Platform"
    assert info["summary"] == "企业知识库、RAG 与工作流自动化 API"
    assert info["version"] == "1.0.0"

    tags = {tag["name"]: tag["description"] for tag in schema["tags"]}

    assert set(tags) == {
        "system",
        "chat",
        "dify",
        "documents",
        "rag",
        "knowledge",
        "workflows",
        "crm",
        "integrations",
    }
    assert tags["rag"] == "知识库检索和带来源回答接口。"
    assert tags["knowledge"] == "Dify 外部知识库检索与集成接口。"


def test_api_documentation_urls() -> None:
    assert app.docs_url == "/docs"
    assert app.redoc_url == "/redoc"
    assert app.openapi_url == "/openapi.json"


def test_all_operations_have_summaries() -> None:
    schema = app.openapi()

    expected_operations = {
        ("/health", "get"): "检查服务运行状态",
        ("/chat", "post"): "发送聊天消息",
        ("/dify/workflow", "post"): "调用 Dify 企业咨询工作流",
        ("/upload", "post"): "上传并索引文档",
        ("/rag/query", "post"): "检索相关文档片段",
        ("/rag/answer", "post"): "生成带来源引用的 RAG 回答",
        ("/retrieval", "post"): "为 Dify 检索外部知识",
        ("/workflow-runs/start", "post"): "登记工作流运行",
        ("/workflow-runs/{run_id}/result", "patch"): ("保存工作流处理结果"),
        (
            "/workflow-runs/executions/{n8n_execution_id}/failure",
            "patch",
        ): "保存 n8n 执行失败",
        ("/workflow-runs", "get"): "按日期查询工作流记录",
        ("/workflow-runs/{run_id}", "get"): "查询单条工作流记录",
        ("/crm/customers/{customer_id}", "put"): "新增或更新 CRM 客户",
        ("/crm/customers/{customer_id}", "get"): "查询 CRM 客户",
        ("/crm/followups", "post"): "创建 CRM 跟进记录",
        ("/crm/followups/{followup_id}", "get"): "查询 CRM 跟进记录",
        ("/crm/customers/{customer_id}/followups", "get"): (
            "查询客户跟进记录"
        ),
        ("/integrations/feishu/messages", "post"): ("通过飞书机器人发送文本消息"),
        ("/integrations/wecom/messages", "post"): "通过企业微信自建应用发送文本消息",
    }

    for (path, method), expected_summary in expected_operations.items():
        operation = schema["paths"][path][method]

        assert operation["summary"] == expected_summary
        assert operation["description"]


def test_openapi_contains_field_and_error_documentation() -> None:
    schema = app.openapi()
    schemas = schema["components"]["schemas"]

    rag_request = schemas["RagQueryRequest"]["properties"]

    assert rag_request["question"]["description"]
    assert rag_request["question"]["examples"] == ["当前项目版本是多少？"]
    assert rag_request["top_k"]["default"] == 3
    assert rag_request["top_k"]["minimum"] == 1
    assert rag_request["top_k"]["maximum"] == 10

    upload_responses = schema["paths"]["/upload"]["post"]["responses"]
    answer_responses = schema["paths"]["/rag/answer"]["post"]["responses"]
    retrieval_responses = schema["paths"]["/retrieval"]["post"]["responses"]

    assert "400" in upload_responses
    assert "415" in upload_responses
    assert "500" in upload_responses
    assert "503" in answer_responses

    assert "401" in retrieval_responses
    assert "404" in retrieval_responses
    assert "422" in retrieval_responses
    assert "503" in retrieval_responses


def test_feishu_message_openapi_contract() -> None:
    schema = app.openapi()
    operation = schema["paths"]["/integrations/feishu/messages"]["post"]

    assert operation["tags"] == ["integrations"]
    assert {"200", "422", "503"} <= operation["responses"].keys()

    model = schema["components"]["schemas"]["FeishuTextMessageRequest"]

    assert set(model["required"]) == {
        "text",
        "idempotency_key",
    }
    assert "receive_id" not in model["properties"]
    assert model["additionalProperties"] is False


def test_wecom_message_openapi_contract() -> None:
    schema = app.openapi()
    operation = schema["paths"]["/integrations/wecom/messages"]["post"]
    assert operation["summary"] == "通过企业微信自建应用发送文本消息"
    assert operation["tags"] == ["integrations"]
    assert {"200", "422", "503"} <= operation["responses"].keys()
    assert "delivery_unknown" in operation["responses"]["503"]["description"]

    models = schema["components"]["schemas"]
    request_model = models["WeComTextMessageRequest"]
    assert set(request_model["required"]) == {"text", "request_id"}
    assert set(request_model["properties"]) == {"text", "request_id"}
    assert request_model["additionalProperties"] is False
    assert "2048" in request_model["properties"]["text"]["description"]

    response_model = models["WeComMessageResponse"]
    assert response_model["properties"]["attempts"]["maximum"] == 2
    assert "message_id" not in response_model["required"]


def test_crm_openapi_contract() -> None:
    schema = app.openapi()
    operation = schema["paths"]["/crm/followups"]["post"]

    assert operation["tags"] == ["crm"]
    assert {"200", "404", "409", "422"} <= operation["responses"].keys()

    models = schema["components"]["schemas"]
    request_model = models["CRMFollowupCreateRequest"]
    assert request_model["additionalProperties"] is False
    assert {
        "customer",
        "run_id",
        "event_id",
        "requirement_snapshot",
        "analysis",
        "priority",
        "review_status",
        "review_reasons",
    } <= set(request_model["required"])
    assert "notification_status" not in request_model["properties"]
    assert "notification_recipient" not in request_model["properties"]
    assert "model_api_key" not in request_model["properties"]

    customer_model = models["CRMCustomerUpsertRequest"]
    assert customer_model["additionalProperties"] is False
    assert set(customer_model["required"]) == {
        "customer_id",
        "company_name",
        "sales_owner",
    }

    analysis_model = models["CRMFollowupAnalysis"]
    assert analysis_model["additionalProperties"] is False
    assert analysis_model["properties"]["needs"]["minItems"] == 1
    assert analysis_model["properties"]["needs"]["maxItems"] == 5
    assert analysis_model["properties"]["risk_flags"]["maxItems"] == 5


def test_wecom_lifecycle_is_lazy_and_resets_cache(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from backend.app import main as main_module
    from backend.app.routers import wecom as wecom_router

    def missing_config():
        raise RuntimeError("未配置 WECOM_CORP_ID")

    # Lifecycle verification must not touch a real database or send real requests.
    monkeypatch.setattr(main_module, "init_database", lambda: None)
    monkeypatch.setattr(main_module, "configure_logging", lambda: None)
    monkeypatch.setattr(wecom_router, "get_wecom_config", missing_config)

    app.state.wecom_cache = object()
    with TestClient(app) as client:
        assert app.state.wecom_cache is None
        assert client.get("/openapi.json").status_code == 200
        response = client.post(
            "/integrations/wecom/messages",
            json={"text": "测试消息", "request_id": "day45-lifecycle-001"},
        )
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "wecom_unavailable"
        app.state.wecom_cache = object()

    assert app.state.wecom_cache is None
