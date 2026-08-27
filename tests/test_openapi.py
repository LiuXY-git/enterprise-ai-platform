from backend.app.main import app


def test_openapi_metadata() -> None:
    schema = app.openapi()
    info = schema["info"]

    assert info["title"] == "Enterprise AI Platform"
    assert info["summary"] == "企业知识库与 RAG API"
    assert info["version"] == "1.0.0"

    tags = {tag["name"]: tag["description"] for tag in schema["tags"]}

    assert set(tags) == {
        "system",
        "chat",
        "documents",
        "rag",
        "knowledge",
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
        ("/upload", "post"): "上传并索引文档",
        ("/rag/query", "post"): "检索相关文档片段",
        ("/rag/answer", "post"): "生成带来源引用的 RAG 回答",
        ("/retrieval", "post"): "为 Dify 检索外部知识",
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
