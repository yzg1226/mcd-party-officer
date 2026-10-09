"""
麦当劳 MCP 通用客户端。

- 协议：JSON-RPC 2.0 over Streamable HTTP
- 端点：https://mcp.mcd.cn
- 鉴权：Authorization: Bearer <MCP Token>
- Token 来源：环境变量 MCD_MCP_TOKEN（或 MCDONALDS_MCP_TOKEN），也可显式传入
- 依赖：仅标准库

用法：
    from mcd_client import McDClient
    cli = McDClient()                  # 读环境变量
    tools = cli.list_tools()
    data = cli.call("query-party-city", {"spuId": 1779})
"""

import json
import os
import urllib.error
import urllib.request

MCP_URL = "https://mcp.mcd.cn"
PROTOCOL_VERSION = "2025-06-18"


class McDError(Exception):
    """麦当劳 MCP 调用异常。"""


class McDClient:
    def __init__(self, token=None, url=MCP_URL, timeout=40):
        self.token = (token
                      or os.environ.get("MCD_MCP_TOKEN")
                      or os.environ.get("MCDONALDS_MCP_TOKEN"))
        if not self.token:
            raise McDError("缺少 MCP Token：请设置环境变量 MCD_MCP_TOKEN")
        self.url = url
        self.timeout = timeout
        self._rid = 0

    # ---------- 底层 ----------
    def _rpc(self, method, params=None):
        self._rid += 1
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": self._rid,
            "method": method,
            "params": params if params is not None else {},
        }).encode("utf-8")

        req = urllib.request.Request(self.url, data=body, headers={
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
        })
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                text = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            raise McDError("HTTP %s: %s" % (e.code, detail))
        except urllib.error.URLError as e:
            raise McDError("网络错误: %s" % e)

        # 兼容 SSE 响应
        stripped = text.lstrip()
        if stripped.startswith("data:") or "\ndata:" in text:
            for line in text.splitlines():
                if line.startswith("data:"):
                    return json.loads(line[5:].strip())
        return json.loads(text)

    # ---------- 公开接口 ----------
    def list_tools(self):
        """返回全部可用工具（当前 35 个）。"""
        return self._rpc("tools/list").get("result", {}).get("tools", [])

    def call(self, name, args=None, raw_text=False):
        """
        调用一个工具。

        - raw_text=False（默认）：返回解析后的 JSON 对象
        - raw_text=True：返回原始文本（含工具自带的展示说明）
        """
        result = self._rpc("tools/call", {"name": name, "arguments": args or {}})
        if "error" in result:
            raise McDError("%s -> %s" % (name, json.dumps(result["error"], ensure_ascii=False)))

        text = ""
        for chunk in result.get("result", {}).get("content", []):
            if chunk.get("type") == "text":
                text += chunk.get("text", "")
        if raw_text:
            return text
        return extract_json(text)


def extract_json(text):
    """
    从 MCP 返回文本中提取内嵌 JSON。

    麦香 MCP 的响应形如：
        <markdown 字段说明>
        {"success":true,...,"data":{...}}
    这里用 raw_decode 从 JSON 起点解析，不依赖结尾位置。
    """
    if not isinstance(text, str):
        return text
    for anchor in ('{"success"', '{"code"', '{"data"'):
        i = text.find(anchor)
        if i < 0:
            continue
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[i:])
            return obj
        except Exception:
            continue
    return None
