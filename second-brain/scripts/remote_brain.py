#!/usr/bin/env python3
"""Dependency-free CLI adapter for the shared Streamable HTTP MCP server."""
import argparse
import json
import os
import sys
import urllib.request

URL = os.environ.get("SECOND_BRAIN_MCP_URL", "http://100.70.58.73:8001/mcp")


def tool(name, arguments):
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    def rpc(payload):
        req = urllib.request.Request(URL, data=json.dumps(payload).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=600) as r:
            if r.headers.get("Mcp-Session-Id"):
                headers["Mcp-Session-Id"] = r.headers["Mcp-Session-Id"]
            data = r.read().decode()
            if not data:
                return None
            if r.headers.get("Content-Type", "").startswith("text/event-stream"):
                data = next(line[6:] for line in data.splitlines() if line.startswith("data: "))
            response = json.loads(data)
            if "error" in response:
                raise RuntimeError(response["error"])
            return response.get("result")
    init = rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "automatic-filer", "version": "1"}}})
    headers["MCP-Protocol-Version"] = init["protocolVersion"]
    rpc({"jsonrpc": "2.0", "method": "notifications/initialized"})
    result = rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": name, "arguments": arguments}})
    if result.get("isError"):
        raise RuntimeError(result.get("content"))
    blocks = [x["text"] for x in result.get("content", []) if x.get("type") == "text"]
    if not blocks:
        return None
    if len(blocks) == 1:
        try:
            return json.loads(blocks[0])
        except json.JSONDecodeError:
            return blocks[0]
    return [json.loads(x) for x in blocks]


def query_main():
    p = argparse.ArgumentParser(description="Query the shared vault; never read the Mac copy.")
    for name in ["segment", "tag", "project", "repo", "area", "type", "kind", "text", "backlinks-to", "read"]:
        p.add_argument("--" + name)
    p.add_argument("--exclude-superseded", action="store_true")
    p.add_argument("--limit", type=int, default=100)
    args = p.parse_args()
    if args.read:
        print(tool("get_note", {"path": args.read})["content"])
        return
    filters = {k: v for k, v in vars(args).items() if k in ["segment", "project", "repo", "area", "type", "kind"] and v}
    if args.tag:
        filters["tags"] = args.tag
    notes = tool("lookup_notes", {"text": args.text or "", "filters": filters, "exclude_superseded": args.exclude_superseded, "backlinks_to": args.backlinks_to or "", "limit": args.limit})
    # FastMCP may serialize a list as one JSON block or one block per item.
    if isinstance(notes, dict):
        notes = [notes]
    if not notes:
        print("No notes matched.")
        return
    for n in notes:
        print(n["path"] + "\n  " + n["title"])
        print(n["content"])
    print(str(len(notes)) + " note(s) matched on the server.")


def create_main():
    p = argparse.ArgumentParser(description="Create a durable note through the shared MCP/API.")
    for name in ["segment", "title", "body", "area", "project", "repo", "type", "tags", "links", "aliases", "supersedes", "reason"]:
        p.add_argument("--" + name, required=name in ["segment", "title", "body"], default="")
    p.add_argument("--memory-type", default="memory")
    p.add_argument("--entities", default="[]", help="JSON array of named, typed entities")
    p.add_argument("--relations", default="[]", help="JSON array of source/type/target assertions supported by the body")
    args = vars(p.parse_args())
    for field in ["entities", "relations"]:
        args[field] = json.loads(args[field])
    result = tool("create_note", args)
    print(json.dumps(result, ensure_ascii=False))


def enrich_main():
    p = argparse.ArgumentParser(description="Annotate existing remote evidence through MCP; preserve its body.")
    p.add_argument("--path", required=True)
    p.add_argument("--expected-digest", required=True, help="content_digest from get_note")
    p.add_argument("--memory-type", default="memory")
    p.add_argument("--entities", default="[]")
    p.add_argument("--relations", default="[]")
    args = vars(p.parse_args())
    for field in ["entities", "relations"]:
        args[field] = json.loads(args[field])
    print(json.dumps(tool("enrich_note", args), ensure_ascii=False))


def recall_main():
    p = argparse.ArgumentParser(description="Intent-aware recall with source citations.")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--filters", default="{}", help="JSON metadata filters")
    args = p.parse_args()
    print(json.dumps(tool("recall", {"query": args.query, "limit": args.limit, "filters": json.loads(args.filters)}), indent=2, ensure_ascii=False))


def call_main():
    p = argparse.ArgumentParser(description="Call a shared second-brain MCP tool.")
    p.add_argument("name")
    p.add_argument("--arguments", default="{}", help="JSON object")
    args = p.parse_args()
    print(json.dumps(tool(args.name, json.loads(args.arguments)), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        mode = sys.argv.pop(1)
        if mode == "query": query_main()
        elif mode == "create": create_main()
        elif mode == "skill": print(tool("skill", {}))
        elif mode == "enrich": enrich_main()
        elif mode == "recall": recall_main()
        elif mode == "call": call_main()
        else: raise ValueError("Expected query, create, enrich, recall, call or skill")
    except Exception as e:
        print("Shared second brain unavailable; no local fallback: " + str(e), file=sys.stderr)
        sys.exit(1)
