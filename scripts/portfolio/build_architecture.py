"""Build the Day 100 SVG architecture assets using only the Python standard library.

Run from any directory: python scripts/portfolio/build_architecture.py <new-output-dir>
These diagrams document verified call paths, not runtime health or measured quality.
"""

import argparse
from html import escape
from pathlib import Path

FONT = "'Microsoft YaHei', 'Noto Sans CJK SC', Arial, sans-serif"
INK, MUTED, BLUE, GREEN, PURPLE = "#162b42", "#52677f", "#2463a5", "#17766b", "#7551a2"


class Diagram:
    def __init__(self, title, subtitle, height, description):
        self.height = height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="{height}" '
            f'viewBox="0 0 1600 {height}" role="img" aria-labelledby="title desc">',
            f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>',
            "<defs>",
            *[
                f'<marker id="arrow-{name}" viewBox="0 0 10 10" refX="9" refY="5" '
                f'markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
                f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{color}"/></marker>'
                for name, color in (
                    ("blue", BLUE),
                    ("green", GREEN),
                    ("purple", PURPLE),
                )
            ],
            "</defs>",
            f'<g font-family="{FONT}">',
            f'<rect width="1600" height="{height}" fill="#f7f9fc"/>',
        ]
        self.text(48, 56, title, 34, weight="700")
        self.text(48, 94, subtitle, 20, MUTED)

    def text(self, x, y, value, size=21, color=INK, weight="400"):
        self.parts.append(
            f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
            f'font-weight="{weight}">{escape(value)}</text>'
        )

    def panel(self, x, y, w, h, title, color=BLUE, fill="#edf4fc", heading_offset=24):
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" '
            f'fill="{fill}" stroke="{color}" stroke-opacity=".25"/>'
        )
        self.text(x + heading_offset, y + 36, title, 23, color, "700")

    def card(self, name, x, y, w, h, title, lines, color=BLUE, fill="#ffffff"):
        self.parts.append(
            f'<g data-card="{escape(name)}">'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" '
            f'fill="{fill}" stroke="{color}" stroke-opacity=".5"/>'
            f'<rect x="{x}" y="{y + 16}" width="4" height="{h - 32}" rx="2" fill="{color}"/>'
        )
        self.text(x + 20, y + 35, title, 24, color, "700")
        for i, line in enumerate(lines):
            self.text(x + 20, y + 66 + 28 * i, line, 20, MUTED)
        self.parts.append("</g>")

    def arrow(self, points, color="blue"):
        raw = " ".join(f"{x},{y}" for x, y in points)
        value = {"blue": BLUE, "green": GREEN, "purple": PURPLE}[color]
        self.parts.append(
            f'<polyline points="{raw}" fill="none" stroke="{value}" stroke-width="2.5" '
            f'stroke-linejoin="round" marker-end="url(#arrow-{color})"/>'
        )

    def save(self, path):
        path.write_text(
            "\n".join(self.parts + ["</g>", "</svg>"]) + "\n", encoding="utf-8"
        )


def topology():
    d = Diagram(
        "Enterprise AI Platform · 系统架构",
        "Day 100 / Week 15     按代码展示部署与调用主路径；箭头表示调用或数据访问，返回值从略。",
        1250,
        "上半部分为三个 Docker Compose 服务：前端、API 和 n8n。"
        "SQLite 和 Chroma 嵌入 API；生成模型与 Dify 在 Compose 外。"
        "下半部分为宿主机固定场景评测、销售 Agent、本地 MCP 与人工审批，未接入网页。",
    )
    d.panel(48, 246, 980, 488, "Compose · 3 个服务", heading_offset=404)
    d.panel(1080, 246, 472, 488, "外部依赖 / 独立部署", GREEN, "#eef8f4")
    d.panel(48, 784, 1504, 402, "宿主机 CLI · 固定虚构销售场景", PURPLE, "#f4f0f9")

    # Draw connectors first so node text is always unobstructed.
    d.arrow([(236, 208), (236, 316)])
    d.arrow([(730, 208), (730, 316)])
    d.arrow([(376, 370), (500, 370)])
    d.arrow([(376, 549), (428, 549), (428, 402), (500, 402)])
    d.arrow([(605, 426), (605, 556)])
    d.arrow([(855, 426), (855, 556)])
    d.arrow([(960, 346), (1120, 346)], "green")
    d.arrow([(960, 385), (1060, 385), (1060, 492), (1120, 492)], "green")
    d.arrow([(1120, 542), (996, 542), (996, 412), (960, 412)], "green")
    d.arrow([(420, 910), (480, 910)], "purple")
    d.arrow([(940, 910), (1040, 910)], "purple")
    d.arrow([(255, 962), (255, 1030)], "purple")
    d.arrow([(710, 962), (710, 1030)], "purple")

    d.card("browser", 96, 132, 280, 76, "浏览器", ["127.0.0.1:8080"])
    d.card(
        "api-client", 500, 132, 460, 76, "API 客户端 / Swagger", ["127.0.0.1:8000/docs"]
    )
    d.card(
        "frontend",
        96,
        316,
        280,
        110,
        "frontend · Nginx",
        ["静态 HTML / CSS / JS", "上传 + 片段检索"],
    )
    d.card(
        "api",
        500,
        316,
        460,
        110,
        "api · FastAPI",
        ["路由 → 业务服务 → 数据访问", "知识库 / 工作流 / 协作接口"],
    )
    d.card(
        "n8n",
        96,
        494,
        280,
        110,
        "n8n · 工作流",
        ["127.0.0.1:5678", "独立配置凭据和模型"],
    )
    d.card("sqlite", 500, 556, 210, 110, "SQLite", ["文档 / 业务记录", "API 进程内"])
    d.card("chroma", 750, 556, 210, 110, "Chroma", ["文档向量 / 片段", "API 进程内"])
    d.card(
        "model",
        1120,
        300,
        384,
        108,
        "配置的生成模型",
        ["RAG 片段 → 带来源回答", "/rag/answer 按配置调用"],
        GREEN,
    )
    d.card(
        "dify",
        1120,
        450,
        384,
        136,
        "Dify · 独立部署",
        [
            "API → Dify：工作流代理",
            "Dify → API：/retrieval",
            "外部知识库接口需 Bearer Key",
        ],
        GREEN,
    )

    d.text(389, 347, "/api/", 20, BLUE)
    d.text(105, 455, "去掉 /api/ 前缀后代理到 API", 19, BLUE)
    d.text(90, 640, "持久化卷：n8n_data", 19, MUTED)
    d.text(510, 490, "业务数据", 19, BLUE)
    d.text(742, 490, "嵌入与检索", 19, BLUE)
    d.text(1010, 328, "HTTP", 19, GREEN)
    d.text(1098, 636, "协作平台：飞书 / 企业微信", 20, MUTED)
    d.text(1098, 670, "API 通知接口按配置可能真实发送。", 20, MUTED)
    d.text(
        72,
        702,
        "API 持久化：./data（SQLite / Chroma）与 ./logs（请求 / 工作流日志）",
        21,
        MUTED,
    )

    d.card(
        "evaluation",
        96,
        858,
        324,
        104,
        "Evaluation Center",
        ["12 个固定 fixture 场景", "隔离子进程执行"],
        PURPLE,
    )
    d.card(
        "agent",
        480,
        858,
        460,
        104,
        "销售 Agent · Day 82 候选入口",
        ["Function Calling / 重试 / 回执校对", "评测使用脚本响应，不调用真实模型"],
        PURPLE,
    )
    d.card(
        "mcp",
        1040,
        858,
        460,
        104,
        "本地 stdio MCP",
        ["工具发现与调用；固定只读 SQL", "数据源：运行目录内的虚构销售 SQLite"],
        PURPLE,
    )
    d.card(
        "report",
        96,
        1030,
        324,
        100,
        "独立规则评分 / 报告",
        ["逐例日志、耗时与已知 usage"],
        PURPLE,
    )
    d.card(
        "hitl",
        480,
        1030,
        460,
        100,
        "Human in the Loop",
        ["合格提案待确认；批准后本地模拟发送"],
        PURPLE,
    )
    d.text(114, 1002, "执行证据", 19, PURPLE)
    d.text(738, 1002, "审批提案", 19, PURPLE)
    d.text(1040, 1018, "Planning / Memory 保留独立实验入口。", 21, MUTED)
    d.text(1040, 1054, "本区无 Agent HTTP API 或网页入口。", 21, MUTED)
    d.text(1040, 1090, "任务日志回放 ≠ 自动恢复执行。", 21, MUTED)
    d.text(
        72,
        1160,
        "CLI 与 Compose 是不同运行入口；评测通过率只对应固定用例，不能代表生产或真实模型质量。",
        21,
        MUTED,
    )
    d.text(
        48,
        1220,
        "阅读方式：先看入口，再看调用路径，最后看存储与边界。逐项代码映射见 docs/week-15.md#day100-code。",
        20,
        MUTED,
    )
    return d


def rag_flow():
    d = Diagram(
        "Knowledge Hub · RAG 数据流",
        "Day 100 / Week 15     分清索引、片段检索和生成回答；网页目前只连接前两项。",
        1080,
        "上传文档经过解析、切分与本地嵌入后写入 Chroma，元数据写入 SQLite。"
        "查询把问题嵌入后检索并返回片段与来源。独立的 rag/answer API 复用检索结果，"
        "有片段时才调用生成模型，无片段时返回无法确定。",
    )
    d.panel(48, 130, 1504, 266, "01 · 建立索引      POST /upload")
    d.panel(48, 430, 1504, 252, "02 · 检索片段      POST /rag/query", GREEN, "#eef8f4")
    d.panel(
        48,
        716,
        1504,
        274,
        "03 · 生成回答      POST /rag/answer（独立 API）",
        PURPLE,
        "#f4f0f9",
    )
    xs, w = [88, 453, 818, 1183], 325
    for y, color in [(249, "blue"), (548, "green")]:
        for x in xs[:-1]:
            d.arrow([(x + w, y), (x + 365, y)], color)
    for x in xs[:-1]:
        d.arrow([(x + w, 840), (x + 365, 840)], "purple")
    d.card(
        "upload",
        xs[0],
        198,
        w,
        104,
        "PDF / DOCX / MD",
        ["前端 POST /api/upload", "Nginx 转为 API /upload"],
    )
    d.card(
        "parse",
        xs[1],
        198,
        w,
        104,
        "解析 → 切分",
        ["提取文本，生成 chunk", "默认 200 字符 / 重叠 50"],
    )
    d.card(
        "embedding",
        xs[2],
        198,
        w,
        104,
        "本地 Embedding",
        ["DefaultEmbeddingFunction", "片段 → 数值向量"],
    )
    d.card(
        "upsert",
        xs[3],
        198,
        w,
        104,
        "Chroma upsert",
        ["向量 + 原文 + 元数据", "source / document_id 等"],
    )
    d.text(
        88,
        355,
        "文档记录：SQLite 保存文档元数据与索引状态；具体写入顺序由上传路由管理。",
        21,
        MUTED,
    )

    d.card(
        "question",
        xs[0],
        496,
        w,
        104,
        "用户问题",
        ["前端 POST /api/rag/query", "携带 question 与 top_k"],
        GREEN,
    )
    d.card(
        "query-embedding",
        xs[1],
        496,
        w,
        104,
        "问题 Embedding",
        ["使用同一嵌入函数", "查询文本 → 查询向量"],
        GREEN,
    )
    d.card(
        "search",
        xs[2],
        496,
        w,
        104,
        "Chroma 相似检索",
        ["按 top_k 返回片段", "不调用生成模型"],
        GREEN,
    )
    d.card(
        "chunks",
        xs[3],
        496,
        w,
        104,
        "检索结果",
        ["片段 / 来源 / 距离等", "页面显示原文与来源"],
        GREEN,
    )
    d.text(
        88,
        645,
        "同一问题也可直接请求 /rag/answer；该接口在后端执行检索，网页当前没有调用它。",
        21,
        MUTED,
    )

    d.card(
        "answer-question",
        xs[0],
        788,
        w,
        104,
        "API 客户端提交问题",
        ["后端 answer_question", "复用 search_chunks"],
        PURPLE,
    )
    d.card(
        "branch",
        xs[1],
        788,
        w,
        104,
        "判断是否有片段",
        ["有片段 → 组织上下文", "无片段 → 返回无法确定"],
        PURPLE,
    )
    d.card(
        "llm",
        xs[2],
        788,
        w,
        104,
        "调用配置的生成模型",
        ["仅在有片段时调用", "模型凭据属于 API 配置"],
        PURPLE,
    )
    d.card(
        "answer",
        xs[3],
        788,
        w,
        104,
        "回答 + 来源",
        ["返回回答及引用材料", "引用可供追溯和核对"],
        PURPLE,
    )
    d.text(800, 771, "有片段时继续", 19, PURPLE)
    d.text(
        88,
        953,
        "首次使用嵌入模型可能需要下载；有来源标签并不等于答案必然正确，仍需独立评测。",
        21,
        MUTED,
    )
    d.text(
        48,
        1036,
        "这是实现路径说明，本次绘图没有重新上传、建立索引、检索向量或调用模型。",
        20,
        MUTED,
    )
    return d


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    topology().save(args.output_dir / "system-architecture.svg")
    rag_flow().save(args.output_dir / "rag-data-flow.svg")
    print(f"Created 2 SVG diagrams in {args.output_dir}")


if __name__ == "__main__":
    main()
