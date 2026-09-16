"""Offline configuration checks: no application, client or database imports."""

import argparse
import json
import os
from pathlib import Path

from . import settings

COMPONENTS = {
    "llm": (settings.get_llm_config,),
    "dify": (settings.get_dify_workflow_config,),
    "external-knowledge": (settings.get_external_knowledge_config,),
    "feishu": (settings.get_feishu_config, settings.get_feishu_message_config),
    "wecom": (settings.get_wecom_config,),
}
SECRET_FIELDS = {
    "dify": ("DIFY_WORKFLOW_API_KEY",),
    "external-knowledge": ("DIFY_EXTERNAL_KNOWLEDGE_API_KEY",),
    "feishu": ("FEISHU_APP_SECRET",),
    "wecom": ("WECOM_APP_SECRET",),
}


def check_component(component: str) -> dict:
    errors = []
    configs = []
    for getter in COMPONENTS[component]:
        try:
            configs.append(getter())
        except RuntimeError as exc:
            # Settings validators only emit fixed rules and known variable names.
            errors.append(str(exc))
    fields = SECRET_FIELDS.get(component, ())
    result = {
        "component": component,
        "status": "configuration_invalid" if errors else "configuration_valid",
        "errors": errors,
        "network_checked": False,
    }
    if component == "llm":
        provider = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()
        definition = settings.PROVIDER_DEFINITIONS.get(provider)
        result["provider"] = provider if definition else "unsupported"
        fields = (definition.api_key_env,) if definition else ()
        result["model"] = "configured" if configs else "not_checked"
    if component in {"dify", "external-knowledge"}:
        result["model"] = "externally_managed"
        result["model_checked"] = False
    result["credentials"] = {
        name: "configured" if os.getenv(name, "").strip() else "missing"
        for name in fields
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="离线检查配置格式；不验证凭据、网络或 Dify/n8n 内部模型。",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--component", choices=tuple(COMPONENTS))
    group.add_argument("--all", action="store_true", help="要求所有组件配置有效")
    parser.add_argument(
        "--env-file",
        type=Path,
        help="明确指定环境文件；默认读取项目根目录 .env，进程环境优先",
    )
    args = parser.parse_args(argv)
    try:
        settings.load_environment(args.env_file)
    except RuntimeError as exc:
        print(
            json.dumps(
                {
                    "status": "configuration_invalid",
                    "errors": [str(exc)],
                    "network_checked": False,
                },
                ensure_ascii=True,
            )
        )
        return 1
    components = tuple(COMPONENTS) if args.all else (args.component,)
    results = [check_component(component) for component in components]
    valid = all(item["status"] == "configuration_valid" for item in results)
    print(
        json.dumps(
            {
                "status": "configuration_valid" if valid else "configuration_invalid",
                "scope": "local_configuration_only",
                "notice": "仅检查配置格式，未验证凭据有效性或网络连通性。",
                "n8n_model": "externally_managed_not_checked",
                "results": results,
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
