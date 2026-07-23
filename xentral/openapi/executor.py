"""
Generic executor for OpenAPI-generated Xentral tools.

One executor class handles every operation in the catalog: it substitutes
path parameters, serializes query parameters in Xentral's deepObject style
(filter[0][key]=...), sends JSON bodies, and formats responses for MCP.
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx

from xentral.base import XentralAPIBase, XentralAPIError

logger = logging.getLogger(__name__)

# Responses larger than this are truncated so a single tool call cannot
# flood the MCP client's context window.
MAX_RESPONSE_CHARS = 60_000

# Where binary responses (PDF, ZIP, images, ...) are stored
DOWNLOADS_DIR = Path("downloads")


def flatten_query_value(prefix: str, value: Any, out: Dict[str, str]) -> None:
    """
    Serialize nested structures into Xentral's deepObject query notation.

    {"filter": [{"key": "name", "op": "equals", "value": "X"}]} becomes
    filter[0][key]=name & filter[0][op]=equals & filter[0][value]=X
    """
    if isinstance(value, dict):
        for key, item in value.items():
            flatten_query_value(f"{prefix}[{key}]", item, out)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            flatten_query_value(f"{prefix}[{index}]", item, out)
    elif isinstance(value, bool):
        out[prefix] = "true" if value else "false"
    elif value is None:
        return
    else:
        out[prefix] = str(value)


def maybe_parse_json_argument(value: Any) -> Any:
    """
    Tolerate structured arguments passed as JSON strings.

    MCP clients occasionally send '{"number": "1"}' instead of the object.
    """
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                return json.loads(stripped)
            except ValueError:
                return value
    return value


class OpenAPIToolExecutor(XentralAPIBase):
    """
    Executes one catalog operation. Subclasses are generated dynamically by
    the loader with `_operation` set to the catalog entry, so instances can
    be created without arguments (as the MCP protocol layer expects).
    """

    _operation: Dict[str, Any] = {}

    def execute(self, arguments: Dict[str, Any]) -> str:
        operation = self._operation
        arguments = arguments or {}

        try:
            url = self.build_api_url(self._build_path(operation, arguments))
            params = self._build_query(operation, arguments)
            json_body, content_type = self._build_body(operation, arguments)

            headers = dict(self.headers)
            if content_type:
                headers["Content-Type"] = content_type

            logger.info(
                "Executing %s %s params=%s body=%s",
                operation["method"], url, params, json_body is not None,
            )

            with httpx.Client(headers=headers, timeout=60.0) as client:
                response = client.request(
                    method=operation["method"],
                    url=url,
                    params=params or None,
                    json=json_body,
                )

            return self._format_response(operation, response)

        except XentralAPIError as error:
            return self.format_error_response(error)
        except httpx.HTTPError as error:
            return self.format_error_response(
                XentralAPIError(f"Request failed: {error}")
            )
        except Exception as error:  # pragma: no cover - defensive
            logger.exception("Unexpected error in %s", operation.get("name"))
            return self.format_error_response(error)

    # ------------------------------------------------------------------
    # Request building
    # ------------------------------------------------------------------

    def _build_path(self, operation: Dict[str, Any], arguments: Dict[str, Any]) -> str:
        """Substitute {placeholders} in the operation path."""
        path = operation["path"]
        for name in operation.get("path_params", []):
            if name not in arguments or arguments[name] in (None, ""):
                raise XentralAPIError(
                    f"Missing required path parameter '{name}' for "
                    f"{operation['method']} {operation['path']}"
                )
            value = quote(str(arguments[name]), safe="")
            path = path.replace("{" + name + "}", value)

        unresolved = re.findall(r"\{([^}]+)\}", path)
        if unresolved:
            raise XentralAPIError(
                f"Unresolved path parameters {unresolved} in {path}"
            )
        return path

    def _build_query(
        self, operation: Dict[str, Any], arguments: Dict[str, Any]
    ) -> Dict[str, str]:
        """Serialize declared query parameters, deepObject-style for structures."""
        params: Dict[str, str] = {}
        for name in operation.get("query_params", []):
            if name not in arguments:
                continue
            value = maybe_parse_json_argument(arguments[name])
            if value is None:
                continue
            if isinstance(value, (dict, list, tuple)):
                flatten_query_value(name, value, params)
            elif isinstance(value, bool):
                params[name] = "true" if value else "false"
            else:
                params[name] = str(value)
        return params

    def _build_body(
        self, operation: Dict[str, Any], arguments: Dict[str, Any]
    ) -> tuple[Optional[Any], Optional[str]]:
        """Build the JSON body and content type, if the operation accepts one."""
        body_info = operation.get("body")
        if not body_info:
            return None, None

        content_type = arguments.get("content_type") or body_info[
            "default_content_type"
        ]
        if content_type not in body_info["content_types"]:
            raise XentralAPIError(
                f"Invalid content_type '{content_type}'. "
                f"Allowed: {body_info['content_types']}"
            )
        # The wildcard placeholder means "no body / no specific content type"
        if content_type == "*/*":
            content_type = None

        json_body = None
        if "body" in arguments and arguments["body"] is not None:
            json_body = maybe_parse_json_argument(arguments["body"])

        return json_body, content_type

    # ------------------------------------------------------------------
    # Response formatting
    # ------------------------------------------------------------------

    def _format_response(
        self, operation: Dict[str, Any], response: httpx.Response
    ) -> str:
        request_line = f"{operation['method']} {response.request.url}"

        if response.status_code >= 400:
            return self._format_http_error(request_line, response)

        if response.status_code == 204 or not response.content:
            return (
                f"✅ **{operation['summary'] or operation['name']}** succeeded "
                f"(HTTP {response.status_code}, no content)\n`{request_line}`"
            )

        content_type = response.headers.get("content-type", "").lower()

        if "json" in content_type:
            try:
                data = response.json()
            except ValueError:
                return self._format_text(request_line, response)
            return self._format_json(request_line, response.status_code, data)

        if content_type.startswith("text/"):
            return self._format_text(request_line, response)

        return self._save_binary(operation, request_line, response)

    def _format_json(self, request_line: str, status: int, data: Any) -> str:
        text = json.dumps(data, indent=2, ensure_ascii=False)

        truncation_note = ""
        if len(text) > MAX_RESPONSE_CHARS and isinstance(data, dict):
            items = data.get("data")
            if isinstance(items, list) and items:
                # Drop trailing list items until the payload fits
                shown = list(items)
                while len(shown) > 1 and len(text) > MAX_RESPONSE_CHARS:
                    shown = shown[: max(1, len(shown) // 2)]
                    text = json.dumps(
                        {**data, "data": shown}, indent=2, ensure_ascii=False
                    )
                truncation_note = (
                    f"\n\n⚠️ Response truncated: showing {len(shown)} of "
                    f"{len(items)} returned items. Use filters or a smaller "
                    "page[size] to narrow the result."
                )

        if len(text) > MAX_RESPONSE_CHARS:
            text = text[:MAX_RESPONSE_CHARS]
            truncation_note = (
                "\n\n⚠️ Response truncated (raw output exceeded "
                f"{MAX_RESPONSE_CHARS} characters)."
            )

        return (
            f"✅ HTTP {status} `{request_line}`\n\n"
            f"```json\n{text}\n```{truncation_note}"
        )

    def _format_text(self, request_line: str, response: httpx.Response) -> str:
        text = response.text
        note = ""
        if len(text) > MAX_RESPONSE_CHARS:
            text = text[:MAX_RESPONSE_CHARS]
            note = "\n\n⚠️ Response truncated."
        return f"✅ HTTP {response.status_code} `{request_line}`\n\n{text}{note}"

    def _save_binary(
        self, operation: Dict[str, Any], request_line: str, response: httpx.Response
    ) -> str:
        """Store binary payloads (PDF, ZIP, images) on disk instead of inlining."""
        content_type = response.headers.get("content-type", "application/octet-stream")
        extension = {
            "application/pdf": ".pdf",
            "application/zip": ".zip",
            "text/csv": ".csv",
            "image/png": ".png",
            "image/jpeg": ".jpg",
        }.get(content_type.split(";")[0].strip(), ".bin")

        DOWNLOADS_DIR.mkdir(exist_ok=True)
        filename = f"{operation['name']}_{int(time.time())}{extension}"
        file_path = DOWNLOADS_DIR / filename
        file_path.write_bytes(response.content)

        return (
            f"✅ HTTP {response.status_code} `{request_line}`\n\n"
            f"Binary response ({content_type}, {len(response.content)} bytes) "
            f"saved to `{file_path}`."
        )

    def _format_http_error(self, request_line: str, response: httpx.Response) -> str:
        body = response.text or "(empty body)"
        try:
            body = json.dumps(response.json(), indent=2, ensure_ascii=False)
        except ValueError:
            pass
        if len(body) > 4000:
            body = body[:4000] + "…"
        return (
            f"❌ **HTTP {response.status_code}** `{request_line}`\n\n"
            f"```json\n{body}\n```"
        )
