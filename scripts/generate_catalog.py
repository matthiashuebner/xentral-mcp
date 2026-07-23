#!/usr/bin/env python3
"""
Generate the MCP tool catalog from the official Xentral OpenAPI specification.

Downloads (or reads) the Xentral OpenAPI 3.0 spec and compiles it into a
compact tool catalog (xentral/openapi/catalog.json) that the MCP server loads
at startup. Every API operation becomes one MCP tool.

Usage:
    python scripts/generate_catalog.py                  # download spec from GitHub
    python scripts/generate_catalog.py --spec spec.json # use a local spec file

The catalog is committed to the repository, so this script only needs to be
re-run when Xentral publishes API changes.
"""

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

SPEC_URL = (
    "https://raw.githubusercontent.com/xentral/api-spec-public/main/"
    "openapi/xentral-api.openapi-3.0.0.json"
)

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = REPO_ROOT / "xentral" / "openapi" / "catalog.json"
TOOLS_LIST_PATH = REPO_ROOT / "mcp-tools-list.md"

HTTP_METHODS = ("get", "post", "put", "patch", "delete")

# Maximum length for tool descriptions sent to MCP clients
MAX_DESCRIPTION_LENGTH = 400


def load_spec(spec_path: str | None) -> dict:
    """Load the OpenAPI spec from a local file or download it from GitHub."""
    if spec_path:
        print(f"Reading spec from {spec_path}")
        with open(spec_path, encoding="utf-8") as f:
            return json.load(f)

    print(f"Downloading spec from {SPEC_URL}")
    with urllib.request.urlopen(SPEC_URL) as response:
        return json.load(response)


def operation_id_to_tool_name(operation_id: str) -> str:
    """
    Convert an OpenAPI operationId to a snake_case MCP tool name.

    Examples:
        analytics.report.getById   -> analytics_report_get_by_id
        auth-platform.exchangeToken -> auth_platform_exchange_token
    """
    name = operation_id.replace(".", "_").replace("-", "_")
    # camelCase -> snake_case
    name = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name)
    name = re.sub(r"_+", "_", name)
    return name.lower()


def clean_text(text: str | None) -> str:
    """Collapse whitespace in spec descriptions."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def build_description(operation: dict, method: str, path: str) -> str:
    """Build a compact MCP tool description from the operation metadata."""
    summary = clean_text(operation.get("summary"))
    description = clean_text(operation.get("description"))
    tags = operation.get("tags") or []

    parts = []
    if operation.get("deprecated"):
        parts.append("[DEPRECATED]")
    if tags:
        parts.append(f"[{tags[0]}]")
    if summary:
        parts.append(summary + ".")
    if description and description.lower() != summary.lower():
        parts.append(description)

    text = " ".join(parts)
    if len(text) > MAX_DESCRIPTION_LENGTH:
        text = text[: MAX_DESCRIPTION_LENGTH - 1].rstrip() + "…"

    # Always include the concrete HTTP call so users can cross-reference the docs
    text += f" ({method.upper()} {path})"
    return text


def unwrap_anyof(schema: dict) -> dict:
    """Unwrap `anyOf`/`oneOf` wrappers that contain exactly one schema."""
    if not isinstance(schema, dict):
        return schema
    for key in ("anyOf", "oneOf"):
        variants = schema.get(key)
        if isinstance(variants, list) and len(variants) == 1 and len(schema) == 1:
            return unwrap_anyof(variants[0])
    return schema


def is_empty_body_schema(schema: dict) -> bool:
    """Detect placeholder schemas used for operations without a real body."""
    if not schema:
        return True
    # The spec models empty bodies as {"type": "string", "enum": [""], ...}
    if schema.get("type") == "string" and schema.get("enum") == [""]:
        return True
    return False


QUERY_PARAM_HINTS = {
    "filter": (
        "Filter conditions as an array of {key, op, value} objects, "
        'e.g. [{"key": "name", "op": "equals", "value": "Miller"}]. '
        "Allowed keys and operators are defined in the schema."
    ),
    "page": 'Page-based pagination, e.g. {"number": "1", "size": "20"}.',
    "order": (
        "Sort order as an array of {field, dir} objects, "
        'e.g. [{"field": "id", "dir": "desc"}].'
    ),
}


def build_tool(path: str, method: str, operation: dict) -> dict:
    """Compile one OpenAPI operation into a catalog tool entry."""
    properties: dict = {}
    required: list[str] = []
    path_params: list[str] = []
    query_params: list[str] = []

    for param in operation.get("parameters", []):
        name = param["name"]
        schema = unwrap_anyof(param.get("schema", {"type": "string"}))
        prop = dict(schema)

        description = clean_text(param.get("description")) or clean_text(
            schema.get("description")
        )
        if name in QUERY_PARAM_HINTS:
            hint = QUERY_PARAM_HINTS[name]
            description = f"{hint} {description}".strip()
        if description:
            prop["description"] = description

        if param.get("in") == "path":
            path_params.append(name)
            properties[name] = prop
            required.append(name)
        elif param.get("in") == "query":
            query_params.append(name)
            properties[name] = prop
            if param.get("required"):
                required.append(name)

    # Request body
    body_info = None
    request_body = operation.get("requestBody") or {}
    content = request_body.get("content") or {}
    if content:
        # Prefer plain JSON; fall back to the first declared content type
        content_types = list(content.keys())
        default_ct = (
            "application/json"
            if "application/json" in content_types
            else content_types[0]
        )
        body_schema = unwrap_anyof(content[default_ct].get("schema") or {})

        has_body = not is_empty_body_schema(body_schema)
        if has_body:
            prop = dict(body_schema)
            prop["description"] = (
                "Request body (JSON). " + clean_text(prop.get("description", ""))
            ).strip()
            properties["body"] = prop
            if request_body.get("required"):
                required.append("body")

        # Offer alternative vendor content types (e.g. upsert, force) if present
        alternative_cts = [ct for ct in content_types if ct != default_ct]
        if alternative_cts:
            properties["content_type"] = {
                "type": "string",
                "enum": content_types,
                "description": (
                    f"Request content type (default: {default_ct}). Vendor types "
                    "like *.upsert+json or *.force+json trigger alternative "
                    "behavior, and their body schema may differ from the default."
                ),
            }

        body_info = {
            "default_content_type": default_ct,
            "content_types": content_types,
            "has_body": has_body,
        }

    input_schema = {
        "type": "object",
        "properties": properties,
    }
    if required:
        input_schema["required"] = required

    tags = operation.get("tags") or ["Other"]

    return {
        "name": operation_id_to_tool_name(operation["operationId"]),
        "operation_id": operation["operationId"],
        "method": method.upper(),
        "path": path,
        "tag": tags[0],
        "summary": clean_text(operation.get("summary")),
        "deprecated": bool(operation.get("deprecated")),
        "description": build_description(operation, method, path),
        "path_params": path_params,
        "query_params": query_params,
        "body": body_info,
        "input_schema": input_schema,
    }


def generate_catalog(spec: dict) -> dict:
    """Compile the full OpenAPI spec into the tool catalog."""
    tools = []
    for path, path_item in sorted(spec["paths"].items()):
        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if not operation:
                continue
            if not operation.get("operationId"):
                print(f"WARNING: skipping {method.upper()} {path} (no operationId)")
                continue
            tools.append(build_tool(path, method, operation))

    # Tool names must be unique — fail loudly if the mapping ever collides
    names = [t["name"] for t in tools]
    duplicates = {n for n in names if names.count(n) > 1}
    if duplicates:
        raise SystemExit(f"ERROR: duplicate tool names generated: {duplicates}")

    for tool in tools:
        if len(tool["name"]) > 64:
            raise SystemExit(f"ERROR: tool name exceeds 64 chars: {tool['name']}")
        if "body" in tool["path_params"] or "body" in tool["query_params"]:
            raise SystemExit(
                f"ERROR: parameter named 'body' collides in {tool['operation_id']}"
            )

    return {
        "source": SPEC_URL,
        "api_title": spec["info"].get("title"),
        "api_version": spec["info"].get("version"),
        "tool_count": len(tools),
        "tools": tools,
    }


def write_tools_list(catalog: dict) -> None:
    """Generate mcp-tools-list.md — a human-readable overview of all tools."""
    by_tag: dict[str, list[dict]] = {}
    for tool in catalog["tools"]:
        by_tag.setdefault(tool["tag"], []).append(tool)

    lines = [
        "# Xentral MCP Tools",
        "",
        f"Auto-generated from the [official Xentral OpenAPI spec]({catalog['source']}).",
        f"**{catalog['tool_count']} API tools** across {len(by_tag)} resource groups, "
        "plus the hand-written convenience tools in `xentral/`.",
        "",
        "Regenerate with: `python scripts/generate_catalog.py`",
        "",
    ]

    for tag in sorted(by_tag):
        tools = by_tag[tag]
        lines.append(f"## {tag} ({len(tools)} tools)")
        lines.append("")
        lines.append("| Tool | Endpoint | Description |")
        lines.append("|------|----------|-------------|")
        for tool in sorted(tools, key=lambda t: t["name"]):
            deprecated = " ⚠️ deprecated" if tool["deprecated"] else ""
            summary = tool["summary"].replace("|", "\\|")
            lines.append(
                f"| `{tool['name']}` | `{tool['method']} {tool['path']}` "
                f"| {summary}{deprecated} |"
            )
        lines.append("")

    TOOLS_LIST_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {TOOLS_LIST_PATH}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--spec",
        help="Path to a local OpenAPI spec file (otherwise downloaded from GitHub)",
    )
    args = parser.parse_args()

    spec = load_spec(args.spec)
    catalog = generate_catalog(spec)

    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=1, ensure_ascii=False)
    size_mb = CATALOG_PATH.stat().st_size / 1024 / 1024
    print(f"Wrote {CATALOG_PATH} ({catalog['tool_count']} tools, {size_mb:.1f} MB)")

    write_tools_list(catalog)
    return 0


if __name__ == "__main__":
    sys.exit(main())
