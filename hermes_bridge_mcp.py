#!/usr/bin/env python3
"""hermes-bridge MCP server — superbrain access to Hermes harness (read + curate memory).

Lets the Antigravity ACP kernel (or any MCP client) pull what the Hermes
context pack and sessions store contain, and persist durable learnings:

  - profile_list()                                       → list all available Hermes profiles
  - context_pack(task_description, max_skills, profile)  → automated context pack leveraging Hermes harness
  - memory_search(query, profile)                        → relevant lines from MEMORY.md / USER.md
  - memory_record(content, target, action, old_text, profile) → save or update facts in Hermes MEMORY.md/USER.md
  - skill_list(category_filter, profile)                 → name + description + category of every skill
  - skill_view(name, profile)                            → full SKILL.md body (frontmatter stripped)
  - session_list(limit, search, profile)                 → metadata of recent Hermes sessions
  - session_get(session_id, limit, offset, profile)      → messages from a session (with turn filtering)
  - session_tool_calls(session_id, tool_name, profile)   → inspect tool inputs/outputs in detail
  - session_search(query, limit, profile)                → full-text search across all sessions/messages
  - session_sync(conversation_id, source, ...)           → mirror a Claude Code / Codex / Antigravity transcript into state.db

Stdlib + Hermes harness reuse:
- Read-only queries use SQLite ?mode=ro and direct filesystem parsing.
- Memory recording directly leverages tools.memory_tool.MemoryStore from hermes-agent,
  preserving file locks, delimiters (§), and character budgets.

Transport: MCP over stdio (newline-delimited JSON-RPC). Logs -> stderr.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
HERMES_BASE = HOME / ".hermes"
HERMES_AGENT_PATH = HERMES_BASE / "hermes-agent"

# Seamlessly reuse Hermes harness when present on the system
if HERMES_AGENT_PATH.is_dir() and str(HERMES_AGENT_PATH) not in sys.path:
    sys.path.insert(0, str(HERMES_AGENT_PATH))

MEMORY_FILES = ("MEMORY.md", "USER.md")
MEMORY_CAP = 6000
SKILL_BODY_CAP = 12000
LINE_HIT_CAP = 40
DEFAULT_SESSION_LIMIT = 15
DEFAULT_MESSAGE_LIMIT = 40
DEFAULT_PROFILE = "simpay" if (HERMES_BASE / "profiles" / "simpay").is_dir() else "default"


def _log(msg: str) -> None:
    print(f"[hermes-bridge] {msg}", file=sys.stderr, flush=True)


def _list_profiles() -> list[dict[str, str]]:
    """Scan and return all available profiles under ~/.hermes/profiles and default."""
    profiles = []
    profiles.append({
        "name": "default",
        "description": "Base Hermes configuration (~/.hermes)",
        "has_db": (HERMES_BASE / "state.db").is_file(),
    })
    pdir = HERMES_BASE / "profiles"
    if pdir.is_dir():
        for p in sorted(pdir.iterdir()):
            if p.is_dir():
                db = p / "state.db"
                profiles.append({
                    "name": p.name,
                    "description": f"Hermes profile '{p.name}'",
                    "has_db": db.is_file(),
                })
    return profiles


def _resolve_profile(name: str, fallback_default: str = "") -> tuple[str, Path | None, list[Path], Path | None]:
    """Return (actual_profile_name, memories_dir, skill_dirs, state_db_path) for the profile."""
    name = (name or fallback_default or os.getenv("HERMES_PROFILE", "") or DEFAULT_PROFILE).strip()
    mem_candidates: list[Path] = []
    skill_dirs: list[Path] = []
    db_candidates: list[Path] = []

    if name and name != "default":
        mem_candidates.append(HERMES_BASE / "profiles" / name / "memories")
        skill_dirs.append(HERMES_BASE / "profiles" / name / "skills")
        db_candidates.append(HERMES_BASE / "profiles" / name / "state.db")

    home = os.getenv("HERMES_HOME", "").strip()
    if home:
        mem_candidates.append(Path(home) / "memories")
        skill_dirs.append(Path(home) / "skills")
        db_candidates.append(Path(home) / "state.db")

    mem_candidates.append(HERMES_BASE / "memories")
    skill_dirs.append(HERMES_BASE / "skills")
    db_candidates.append(HERMES_BASE / "state.db")

    mem_dir = next((d for d in mem_candidates if d.is_dir()), None)
    state_db = next((f for f in db_candidates if f.is_file()), None)
    return name, mem_dir, [d for d in skill_dirs if d.is_dir()], state_db


def _get_db_connection(db_path: Path | None) -> sqlite3.Connection | None:
    if not db_path or not db_path.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        _log(f"connect to {db_path} failed: {e}")
        return None


def _read_memories(mem_dir: Path | None) -> dict[str, str]:
    out: dict[str, str] = {}
    if not mem_dir:
        return out
    for fname in MEMORY_FILES:
        p = mem_dir / fname
        try:
            if p.is_file():
                out[fname] = p.read_text(encoding="utf-8", errors="replace").strip()[:MEMORY_CAP]
        except Exception as e:
            _log(f"read {p} failed: {e}")
    return out


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", (text or "").lower()))


def _tool_profile_list() -> str:
    profiles = _list_profiles()
    out = ["Available Hermes profiles:\n"]
    for p in profiles:
        db_status = "has history" if p["has_db"] else "no db"
        out.append(f"• **{p['name']}**: {p['description']} ({db_status})")
    out.append("\nTip: You can pass `profile: '<name>'` to any hermes-bridge tool to query or mutate a specific profile.")
    return "\n".join(out)


def _tool_memory_search(mem_dir: Path | None, query: str, profile_name: str) -> str:
    mems = _read_memories(mem_dir)
    if not mems:
        return f"No Hermes memory files found for profile '{profile_name}'."
    tokens = _tokenize(query)
    if not tokens:
        parts = [f"## {k} (profile: {profile_name})\n{v[:2000]}" for k, v in mems.items() if v]
        return "\n\n".join(parts) or "Memory files are empty."
    hits: list[str] = []
    for fname, text in mems.items():
        for line in text.splitlines():
            ltokens = _tokenize(line)
            if tokens & ltokens and line.strip():
                hits.append(f"[{profile_name}:{fname}] {line.strip()}")
                if len(hits) >= LINE_HIT_CAP:
                    break
    if not hits:
        return f"No memory lines matched the query in profile '{profile_name}'. Full memory heads:\n" + "\n\n".join(
            f"## {k}\n{v[:1200]}" for k, v in mems.items() if v
        )
    return "\n".join(hits)


def _tool_memory_record(
    content: str,
    target: str = "memory",
    action: str = "add",
    old_text: str = "",
    profile_name: str = "",
) -> str:
    """Record or update durable memory using Hermes' official MemoryStore."""
    target_profile = profile_name or "simpay"
    target = (target or "memory").strip().lower()
    if target not in ("memory", "user"):
        return f"Invalid target '{target}'. Must be 'memory' (project facts) or 'user' (user profile)."

    action = (action or "add").strip().lower()
    if action not in ("add", "replace", "remove"):
        return f"Invalid action '{action}'. Must be 'add', 'replace', or 'remove'."

    prof_dir = (HERMES_BASE / "profiles" / target_profile) if target_profile != "default" else HERMES_BASE
    mem_dir = prof_dir / "memories"
    mem_dir.mkdir(parents=True, exist_ok=True)

    old_home = os.environ.get("HERMES_HOME")
    os.environ["HERMES_HOME"] = str(prof_dir)
    try:
        from tools.memory_tool import MemoryStore
        ms = MemoryStore()
        ms.load_from_disk()

        if action == "add":
            res = ms.add(target, content)
        elif action == "replace":
            res = ms.replace(target, old_text, content)
        elif action == "remove":
            res = ms.remove(target, old_text or content)
        else:
            return f"Unsupported action {action}"

        if res.get("success"):
            return (
                f"Memory updated successfully in profile '{target_profile}' [{target.upper()}]:\n"
                f"Status: {res.get('message', 'Saved')} | Usage: {res.get('usage', 'N/A')}\n"
                f"Entry content: {content[:200]}"
            )
        else:
            err = res.get("error", "Unknown memory error")
            current = res.get("current_entries", [])
            entries_preview = "\n".join(f"- {e[:100]}..." for e in current[:5])
            return (
                f"Failed to update memory in profile '{target_profile}': {err}\n"
                f"Existing entries:\n{entries_preview}"
            )
    except Exception as e:
        _log(f"memory_record error: {e}")
        return f"Error executing memory mutation via Hermes harness: {e}"
    finally:
        if old_home is not None:
            os.environ["HERMES_HOME"] = old_home
        else:
            os.environ.pop("HERMES_HOME", None)


def _parse_frontmatter(path: Path) -> tuple[str, str, str]:
    name = path.parent.name
    desc, cat = "", ""
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        if text.startswith("---"):
            end = text.find("\n---", 3)
            head = text[3:end] if end != -1 else text[3:800]
            m = re.search(r"^description:\s*[\"']?(.+?)[\"']?\s*$", head, re.M)
            if m:
                desc = m.group(1).strip()[:300]
        rel = path.parent.relative_to(path.parent.parent.parent)
        parts = rel.parts
        if len(parts) >= 2:
            cat = parts[0]
    except Exception as e:
        _log(f"frontmatter {path} failed: {e}")
    return name, desc, cat


def _scan_skills(skill_dirs: list[Path]) -> list[dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for sdir in skill_dirs:
        try:
            for skill_md in sorted(sdir.rglob("SKILL.md")):
                name, desc, cat = _parse_frontmatter(skill_md)
                if name and name not in found:
                    found[name] = {
                        "name": name,
                        "description": desc,
                        "category": cat,
                        "path": str(skill_md.parent),
                    }
        except Exception as e:
            _log(f"scan {sdir} failed: {e}")
    return sorted(found.values(), key=lambda s: s["name"])


def _tool_skill_list(skill_dirs: list[Path], category_filter: str = "", profile_name: str = "") -> str:
    skills = _scan_skills(skill_dirs)
    if not skills:
        return f"No Hermes skills found for profile '{profile_name}'."
    if category_filter:
        cwant = category_filter.strip().lower()
        skills = [s for s in skills if s["category"].lower() == cwant]
        if not skills:
            return f"No Hermes skills found in category '{category_filter}' (profile: {profile_name})."
    lines = [
        f"- {s['name']}" + (f" [{s['category']}]" if s["category"] else "")
        + (f": {s['description']}" if s["description"] else "")
        for s in skills
    ]
    return f"{len(lines)} Hermes skills (profile: {profile_name}, use skill_view(name) for the full procedure):\n" + "\n".join(lines)


def _tool_skill_view(skill_dirs: list[Path], name: str, profile_name: str = "") -> str:
    want = (name or "").strip().lower()
    if not want:
        return "Missing skill name."
    for s in _scan_skills(skill_dirs):
        if s["name"].lower() == want:
            try:
                text = Path(s["path"], "SKILL.md").read_text(encoding="utf-8-sig", errors="replace")
                if text.startswith("---"):
                    end = text.find("\n---", 3)
                    if end != -1:
                        text = text[end + 4:]
                return f"# {s['name']} (profile: {profile_name})\n\n" + text.strip()[:SKILL_BODY_CAP]
            except Exception as e:
                return f"Could not read skill '{s['name']}': {e}"
    return f"Skill '{name}' not found in profile '{profile_name}'. Call skill_list() for available names."


def _tool_context_pack(task_description: str, max_skills: int = 3, profile_name: str = "") -> str:
    task = (task_description or "").strip()
    if not task:
        return "Please provide a task_description to build the context pack."

    max_n = max(1, min(int(max_skills or 3), 10))
    target_profile = profile_name or "simpay"

    old_prof = os.environ.get("HERMES_PROFILE")
    old_pack_env = os.environ.get("HERMES_ANTIGRAVITY_ACP_CONTEXT_PACK")
    os.environ["HERMES_PROFILE"] = target_profile
    os.environ["HERMES_ANTIGRAVITY_ACP_CONTEXT_PACK"] = str(max_n)

    try:
        from agent.acp_context_pack import build_context_pack
        messages = [{"role": "user", "content": task}]
        pack = build_context_pack(messages)
        if pack:
            return f"[Hermes Profile: {target_profile}]\n" + pack
    except Exception as e:
        _log(f"harness build_context_pack failed for {target_profile}: {e}")
    finally:
        if old_prof is not None:
            os.environ["HERMES_PROFILE"] = old_prof
        else:
            os.environ.pop("HERMES_PROFILE", None)
        if old_pack_env is not None:
            os.environ["HERMES_ANTIGRAVITY_ACP_CONTEXT_PACK"] = old_pack_env
        else:
            os.environ.pop("HERMES_ANTIGRAVITY_ACP_CONTEXT_PACK", None)

    # Fallback direct reader
    _, mem_dir, skill_dirs, _ = _resolve_profile(target_profile)
    mems = _read_memories(mem_dir)
    mem_section = "\n\n".join(f"## {k}\n{v[:3000]}" for k, v in mems.items() if v)
    tokens = _tokenize(task)
    skills = _scan_skills(skill_dirs)
    matched_skills = []
    for s in skills:
        stokens = _tokenize(f"{s['name']} {s['description']} {s['category']}")
        score = len(tokens & stokens)
        if score > 0:
            matched_skills.append((score, s))
    matched_skills.sort(key=lambda x: x[0], reverse=True)
    skill_parts = []
    for _, s in matched_skills[:max_n]:
        body = _tool_skill_view(skill_dirs, s["name"], target_profile)
        skill_parts.append(f"### {s['name']}\n{body[:3500]}")

    out = [f"# HERMES CONTEXT PACK (Profile: {target_profile})\n"]
    if mem_section:
        out.append("## PERSISTENT MEMORY\n" + mem_section)
    if skill_parts:
        out.append("## RELEVANT SKILLS\n" + "\n\n".join(skill_parts))
    return "\n\n".join(out) if (mem_section or skill_parts) else f"No relevant context found in profile '{target_profile}'."


def _format_timestamp(ts: float | None) -> str:
    if not ts:
        return "unknown"
    try:
        return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(ts)


def _find_session_id(conn: sqlite3.Connection, identifier: str) -> str | None:
    identifier = identifier.strip()
    c = conn.cursor()
    c.execute("SELECT id FROM sessions WHERE id = ?", (identifier,))
    row = c.fetchone()
    if row:
        return row[0]
    c.execute("SELECT id FROM sessions WHERE id LIKE ? ORDER BY started_at DESC LIMIT 1", (f"%{identifier}%",))
    row = c.fetchone()
    return row[0] if row else None


def _tool_session_list(state_db: Path | None, limit: int = DEFAULT_SESSION_LIMIT, search: str = "", profile_name: str = "") -> str:
    conn = _get_db_connection(state_db)
    if not conn:
        return f"Hermes database not found for profile '{profile_name}' (expected at {state_db})."
    try:
        c = conn.cursor()
        limit = min(max(1, int(limit or DEFAULT_SESSION_LIMIT)), 50)
        search = (search or "").strip()
        if search:
            c.execute("""
                SELECT id, source, model, title, started_at, message_count, tool_call_count, cwd
                FROM sessions
                WHERE id LIKE ? OR title LIKE ? OR cwd LIKE ? OR model LIKE ?
                ORDER BY started_at DESC
                LIMIT ?
            """, (f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%", limit))
        else:
            c.execute("""
                SELECT id, source, model, title, started_at, message_count, tool_call_count, cwd
                FROM sessions
                ORDER BY started_at DESC
                LIMIT ?
            """, (limit,))
        rows = c.fetchall()
        if not rows:
            return f"No sessions found matching criteria in profile '{profile_name}'."

        output = [f"Found {len(rows)} sessions (Profile: {profile_name}):\n"]
        for r in rows:
            sid = r["id"]
            title = r["title"] or "(no title)"
            started = _format_timestamp(r["started_at"])
            model = r["model"] or "unknown-model"
            source = r["source"] or "cli"
            msgs = r["message_count"]
            tools = r["tool_call_count"]
            cwd = f" in {r['cwd']}" if r["cwd"] else ""
            output.append(f"• `{sid}` [{started}] ({model}, {source}{cwd})")
            output.append(f"  Title: {title} | Messages: {msgs} | Tool Calls: {tools}\n")
        return "\n".join(output)
    except Exception as e:
        return f"Error querying sessions in profile '{profile_name}': {e}"
    finally:
        conn.close()


def _tool_session_get(
    state_db: Path | None,
    session_id: str,
    limit: int = DEFAULT_MESSAGE_LIMIT,
    offset: int = 0,
    profile_name: str = "",
) -> str:
    conn = _get_db_connection(state_db)
    if not conn:
        return f"Hermes database not found for profile '{profile_name}'."
    try:
        c = conn.cursor()
        resolved_id = _find_session_id(conn, session_id)
        if not resolved_id:
            return f"Session '{session_id}' not found in profile '{profile_name}'."

        c.execute("SELECT id, model, title, started_at, message_count, tool_call_count, cwd FROM sessions WHERE id = ?", (resolved_id,))
        s_meta = c.fetchone()

        limit = min(max(1, int(limit or DEFAULT_MESSAGE_LIMIT)), 100)
        offset = max(0, int(offset or 0))

        c.execute("""
            SELECT id, role, content, tool_name, tool_call_id, tool_calls, timestamp
            FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
            LIMIT ? OFFSET ?
        """, (resolved_id, limit, offset))
        messages = c.fetchall()

        c.execute("SELECT count(*) FROM messages WHERE session_id = ?", (resolved_id,))
        total_msgs = c.fetchone()[0]

        out = [
            f"# Hermes Session: `{resolved_id}` (Profile: {profile_name})",
            f"- **Title**: {s_meta['title'] or '(none)'}",
            f"- **Model**: {s_meta['model']} | **Started**: {_format_timestamp(s_meta['started_at'])}",
            f"- **CWD**: {s_meta['cwd'] or 'none'}",
            f"- **Messages**: showing {len(messages)} of {total_msgs} (offset {offset})\n",
            "---",
        ]

        for m in messages:
            role = m["role"].upper()
            ts = _format_timestamp(m["timestamp"])
            content = (m["content"] or "").strip()
            tname = m["tool_name"]
            tcalls = m["tool_calls"]

            if role == "TOOL":
                preview = content[:800] + ("..." if len(content) > 800 else "")
                out.append(f"### [TOOL RESULT: `{tname or 'unknown'}`] ({ts})")
                out.append(f"```\n{preview}\n```\n")
            elif role == "ASSISTANT":
                out.append(f"### [ASSISTANT] ({ts})")
                if content:
                    out.append(content)
                if tcalls:
                    try:
                        calls_data = json.loads(tcalls)
                        for call in calls_data:
                            c_fn = call.get("function", {}) if "function" in call else call
                            fn_name = c_fn.get("name") or call.get("tool_name") or "tool"
                            fn_args = c_fn.get("arguments") or call.get("arguments") or {}
                            args_str = json.dumps(fn_args, ensure_ascii=False) if isinstance(fn_args, dict) else str(fn_args)
                            out.append(f"-> **Call Tool**: `{fn_name}` with `{args_str[:400]}`")
                    except Exception:
                        out.append(f"-> **Tool Calls Raw**: `{tcalls[:400]}`")
                out.append("")
            else:
                out.append(f"### [{role}] ({ts})")
                out.append(f"{content}\n")

        return "\n".join(out)
    except Exception as e:
        return f"Error retrieving session: {e}"
    finally:
        conn.close()


def _tool_session_tool_calls(
    state_db: Path | None,
    session_id: str,
    tool_name: str = "",
    limit: int = 30,
    profile_name: str = "",
) -> str:
    conn = _get_db_connection(state_db)
    if not conn:
        return f"Hermes database not found for profile '{profile_name}'."
    try:
        c = conn.cursor()
        resolved_id = _find_session_id(conn, session_id)
        if not resolved_id:
            return f"Session '{session_id}' not found in profile '{profile_name}'."

        limit = min(max(1, int(limit or 30)), 100)
        tool_name = (tool_name or "").strip().lower()

        c.execute("""
            SELECT id, role, tool_name, content, tool_call_id, tool_calls, timestamp
            FROM messages
            WHERE session_id = ? AND (role = 'tool' OR tool_calls IS NOT NULL)
            ORDER BY id ASC
        """, (resolved_id,))
        rows = c.fetchall()

        results = []
        for r in rows:
            role = r["role"]
            tname = r["tool_name"] or ""
            tcalls = r["tool_calls"]
            content = (r["content"] or "").strip()
            ts = _format_timestamp(r["timestamp"])

            if role == "assistant" and tcalls:
                try:
                    parsed = json.loads(tcalls)
                    for item in parsed:
                        fn = item.get("function", {}) if "function" in item else item
                        name = fn.get("name") or item.get("tool_name") or ""
                        args = fn.get("arguments") or item.get("arguments") or {}
                        cid = item.get("id") or item.get("call_id") or ""
                        if not tool_name or tool_name in name.lower():
                            results.append({
                                "type": "INVOCATION",
                                "name": name,
                                "call_id": cid,
                                "arguments": args,
                                "timestamp": ts,
                            })
                except Exception:
                    pass
            elif role == "tool":
                cid = r["tool_call_id"] or ""
                if not tool_name or tool_name in tname.lower():
                    results.append({
                        "type": "RESULT",
                        "name": tname,
                        "call_id": cid,
                        "content": content[:1200] + ("..." if len(content) > 1200 else ""),
                        "timestamp": ts,
                    })

        if not results:
            msg = f"No tool calls found for session `{resolved_id}` in profile '{profile_name}'"
            if tool_name:
                msg += f" with filter '{tool_name}'"
            return msg + "."

        results = results[:limit]
        out = [f"Found {len(results)} tool interactions in session `{resolved_id}` (Profile: {profile_name}):\n"]
        for res in results:
            if res["type"] == "INVOCATION":
                args_preview = json.dumps(res["arguments"], ensure_ascii=False) if isinstance(res["arguments"], dict) else str(res["arguments"])
                out.append(f"🔧 **INVOKE** `{res['name']}` [{res['timestamp']}] (call_id: {res['call_id']})")
                out.append(f"   Args: `{args_preview[:500]}`\n")
            else:
                out.append(f"📥 **OUTPUT** `{res['name']}` [{res['timestamp']}] (call_id: {res['call_id']})")
                out.append(f"   Result: ```\n{res['content']}\n   ```\n")

        return "\n".join(out)
    except Exception as e:
        return f"Error retrieving tool calls: {e}"
    finally:
        conn.close()


def _tool_session_search(state_db: Path | None, query: str, limit: int = 15, profile_name: str = "") -> str:
    conn = _get_db_connection(state_db)
    if not conn:
        return f"Hermes database not found for profile '{profile_name}'."
    try:
        c = conn.cursor()
        query = (query or "").strip()
        if not query:
            return "Please provide a search query."
        limit = min(max(1, int(limit or 15)), 50)

        c.execute("""
            SELECT m.id, m.session_id, s.title, m.role, m.tool_name, m.content, m.timestamp
            FROM messages_fts f
            JOIN messages m ON f.rowid = m.id
            LEFT JOIN sessions s ON m.session_id = s.id
            WHERE messages_fts MATCH ?
            ORDER BY m.timestamp DESC
            LIMIT ?
        """, (query, limit))
        rows = c.fetchall()

        if not rows:
            return f"No messages matched '{query}' in profile '{profile_name}'."

        out = [f"Search results for '{query}' in profile '{profile_name}' ({len(rows)} hits):\n"]
        for r in rows:
            sid = r["session_id"]
            title = r["title"] or "(no title)"
            role = r["role"]
            tname = f":{r['tool_name']}" if r["tool_name"] else ""
            ts = _format_timestamp(r["timestamp"])
            content = (r["content"] or "").strip()
            snippet = content[:300].replace("\n", " ") + ("..." if len(content) > 300 else "")
            out.append(f"• Session `{sid}` — *{title}*")
            out.append(f"  [{ts}] {role}{tname}: {snippet}\n")

        return "\n".join(out)
    except Exception as e:
        try:
            c.execute("""
                SELECT m.id, m.session_id, s.title, m.role, m.tool_name, m.content, m.timestamp
                FROM messages m
                LEFT JOIN sessions s ON m.session_id = s.id
                WHERE m.content LIKE ? OR m.tool_name LIKE ?
                ORDER BY m.timestamp DESC
                LIMIT ?
            """, (f"%{query}%", f"%{query}%", limit))
            rows = c.fetchall()
            if not rows:
                return f"No messages matched '{query}' in profile '{profile_name}'."
            out = [f"Search results (substring fallback) for '{query}' in profile '{profile_name}' ({len(rows)} hits):\n"]
            for r in rows:
                sid = r["session_id"]
                title = r["title"] or "(no title)"
                role = r["role"]
                tname = f":{r['tool_name']}" if r["tool_name"] else ""
                ts = _format_timestamp(r["timestamp"])
                content = (r["content"] or "").strip()
                snippet = content[:300].replace("\n", " ") + ("..." if len(content) > 300 else "")
                out.append(f"• Session `{sid}` — *{title}*")
                out.append(f"  [{ts}] {role}{tname}: {snippet}\n")
            return "\n".join(out)
        except Exception as e2:
            return f"Search failed: {e2}"
    finally:
        conn.close()


def _normalize_model_name(raw: str) -> str:
    if not raw:
        return "gemini-3.8-flash"
    low = raw.lower().strip()
    if "3.8" in low and "flash" in low:
        return "gemini-3.8-flash"
    if "2.5" in low and "pro" in low:
        return "gemini-2.5-pro"
    if "flash" in low:
        return "gemini-flash"
    if "pro" in low:
        return "gemini-pro"
    return raw.strip()


def _claude_projects_dir() -> Path:
    return Path(os.getenv("CLAUDE_CONFIG_DIR", str(HOME / ".claude"))).expanduser() / "projects"


def _claude_project_slug(cwd: str) -> str:
    # Claude Code stores transcripts under projects/<cwd with every non-alphanumeric char -> '-'>/
    return re.sub(r"[^A-Za-z0-9]", "-", cwd)


def _locate_claude(conv_id: str, cwd: str = "") -> Path | None:
    """Claude Code transcript by session id; with no id, the newest one for `cwd` (fallback)."""
    root = _claude_projects_dir()
    if not root.is_dir():
        return None
    if conv_id:
        if cwd:
            p = root / _claude_project_slug(cwd) / f"{conv_id}.jsonl"
            if p.is_file():
                return p
        return next((c for c in root.glob(f"*/{conv_id}.jsonl") if c.is_file()), None)
    proj = root / _claude_project_slug(cwd) if cwd else None
    candidates = list(proj.glob("*.jsonl")) if proj and proj.is_dir() else list(root.glob("*/*.jsonl"))
    return max(candidates, key=lambda c: c.stat().st_mtime, default=None)


def _looks_like_claude(path: Path) -> bool:
    if ".claude" in path.parts and "projects" in path.parts:
        return True
    try:
        with open(path, "r", encoding="utf-8") as f:
            for _ in range(20):
                try:
                    item = json.loads(f.readline() or "null")
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict) and ("sessionId" in item or "parentUuid" in item):
                    return True
    except OSError:
        pass
    return False


def _find_session_transcript(
    conv_id: str,
    explicit_path: str = "",
    source_hint: str = "",
    cwd: str = "",
) -> tuple[Path | None, str]:
    hint = (source_hint or "").strip().lower()
    if explicit_path:
        path = Path(explicit_path).expanduser()
        if path.is_file():
            if hint == "claude" or _looks_like_claude(path):
                return path, "claude"
            return path, ("codex" if ".codex" in path.parts else "antigravity")
    if hint == "claude" or not conv_id:
        found = _locate_claude(conv_id, cwd)
        if found:
            return found, "claude"
        if hint == "claude" or not conv_id:
            return None, ""
    antigravity_path = HOME / f".gemini/antigravity/brain/{conv_id}/.system_generated/logs/transcript.jsonl"
    if antigravity_path.is_file():
        return antigravity_path, "antigravity"
    codex_home = Path(os.getenv("CODEX_HOME", str(HOME / ".codex"))).expanduser()
    sessions_dir = codex_home / "sessions"
    if sessions_dir.is_dir():
        for candidate in sessions_dir.rglob(f"*-{conv_id}.jsonl"):
            if candidate.is_file():
                return candidate, "codex"
    found = _locate_claude(conv_id, cwd)
    if found:
        return found, "claude"
    return None, ""


def _timestamp_from_item(item: dict) -> float | None:
    raw = item.get("created_at") or item.get("timestamp")
    if not raw:
        return None
    try:
        return datetime.datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


def _codex_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts = []
    for part in content:
        if isinstance(part, str):
            parts.append(part)
        elif isinstance(part, dict):
            text = part.get("text") or part.get("content")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts).strip()


_CLAUDE_TERMINAL_STOPS = {"end_turn", "stop_sequence", "max_tokens", "refusal"}


def _claude_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts = []
    for part in content:
        if isinstance(part, str):
            parts.append(part)
        elif isinstance(part, dict):
            ptype = part.get("type")
            if ptype == "text":
                parts.append(part.get("text") or "")
            elif ptype == "image":
                parts.append("[image]")
            elif ptype == "tool_result":
                parts.append(_claude_text(part.get("content")))
    return "\n".join(p for p in parts if p).strip()


def _claude_title(transcript_path: Path) -> str | None:
    title = None
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                if '"custom-title"' not in line and '"ai-title"' not in line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                title = item.get("customTitle") or item.get("aiTitle") or item.get("title") or title
    except OSError:
        pass
    return title


def _parse_claude(transcript_path: Path) -> tuple[list[dict], str | None, str | None, str | None]:
    """Claude Code JSONL -> Hermes events (OpenAI-style: assistant text/reasoning/tool_calls + tool results).

    Streaming writes one JSONL line per content block, all sharing message.id; blocks are merged into
    a single assistant event. A trailing group is only emitted once it is provably complete (terminal
    stop_reason or followed by another record), so re-syncing a live session never freezes a partial turn.
    """
    events: list[dict] = []
    model = None
    cwd = None
    tool_names: dict[str, str] = {}
    group: dict | None = None

    def flush(final: bool = False) -> None:
        nonlocal group
        g, group = group, None
        if not g:
            return
        if final and g["stop_reason"] not in _CLAUDE_TERMINAL_STOPS:
            return
        text = "\n".join(t for t in g["text"] if t).strip()
        reasoning = "\n".join(t for t in g["reasoning"] if t).strip()
        if not (text or reasoning or g["tool_calls"]):
            return
        events.append({
            "role": "assistant", "content": text, "reasoning": reasoning or None,
            "tool_calls": g["tool_calls"] or None, "ts": g["ts"], "source_id": f"claude:assistant:{g['id']}",
        })

    with open(transcript_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            rtype = item.get("type")
            if rtype not in ("user", "assistant") or item.get("isSidechain") or item.get("isMeta"):
                continue
            msg = item.get("message") or {}
            content = msg.get("content")
            ts = _timestamp_from_item(item)
            cwd = item.get("cwd") or cwd

            if rtype == "assistant":
                mid = msg.get("id") or item.get("uuid") or f"line:{len(events)}"
                if group is None or group["id"] != mid:
                    flush()
                    group = {"id": mid, "text": [], "reasoning": [], "tool_calls": [], "ts": ts, "stop_reason": None}
                group["stop_reason"] = msg.get("stop_reason") or group["stop_reason"]
                if msg.get("model") and msg["model"] != "<synthetic>":
                    model = msg["model"]
                for block in content if isinstance(content, list) else []:
                    btype = block.get("type")
                    if btype == "text":
                        group["text"].append(block.get("text") or "")
                    elif btype == "thinking":
                        group["reasoning"].append(block.get("thinking") or "")
                    elif btype == "tool_use":
                        call_id = block.get("id") or f"call:{len(events)}"
                        name = block.get("name") or "claude_tool"
                        tool_names[call_id] = name
                        group["tool_calls"].append({
                            "id": call_id, "type": "function",
                            "function": {"name": name, "arguments": json.dumps(block.get("input") or {}, ensure_ascii=False)},
                        })
                continue

            flush()
            uid = item.get("uuid") or f"line:{len(events)}"
            if isinstance(content, str):
                if content.strip():
                    events.append({"role": "user", "content": content.strip(), "ts": ts, "source_id": f"claude:user:{uid}"})
                continue
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    call_id = block.get("tool_use_id") or uid
                    body = _claude_text(block.get("content"))
                    if block.get("is_error") and body:
                        body = f"[error] {body}"
                    events.append({
                        "role": "tool", "content": body, "tool_name": tool_names.get(call_id, "claude_tool"),
                        "tool_call_id": call_id, "ts": ts, "source_id": f"claude:tool:{call_id}",
                    })
            user_text = _claude_text([b for b in content if not (isinstance(b, dict) and b.get("type") == "tool_result")]) if isinstance(content, list) else ""
            if user_text:
                events.append({"role": "user", "content": user_text, "ts": ts, "source_id": f"claude:user:{uid}"})
    flush(final=True)
    return events, model, cwd, None


def _parse_transcript(transcript_path: Path, source: str) -> tuple[list[dict], str | None, str | None, str | None]:
    if source == "claude":
        return _parse_claude(transcript_path)
    raw_events: list[dict] = []
    detected_model = None
    detected_cwd = None
    system_prompt = None
    with open(transcript_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if source == "antigravity":
                stype = item.get("type")
                ts = _timestamp_from_item(item)
                if stype == "USER_INPUT":
                    raw_events.append({"role": "user", "content": (item.get("content") or "").strip(), "ts": ts, "source_id": f"antigravity:{item.get('id') or len(raw_events)}"})
                elif stype == "PLANNER_RESPONSE":
                    raw_events.append({"role": "assistant", "content": (item.get("content") or "").strip(), "tool_calls": item.get("tool_calls"), "ts": ts, "source_id": f"antigravity:{item.get('id') or len(raw_events)}"})
                elif stype == "GENERIC":
                    raw_events.append({"role": "tool", "content": (item.get("content") or "").strip(), "tool_name": "antigravity_tool", "ts": ts, "source_id": f"antigravity:{item.get('id') or len(raw_events)}"})
                if not detected_model and "Model Selection" in line:
                    match = re.search(r"Model Selection`?\s+from\s+.*?\s+to\s+([A-Za-z0-9\.\-\_\s\(\)]+?)(?:\.\s|\.$|\n|\"|\<)", line)
                    if match:
                        detected_model = _normalize_model_name(match.group(1))
                continue
            payload = item.get("payload") or {}
            if item.get("type") == "session_meta":
                detected_cwd = payload.get("cwd") or detected_cwd
                base = payload.get("base_instructions")
                if isinstance(base, dict):
                    system_prompt = base.get("text") or system_prompt
                elif isinstance(base, str):
                    system_prompt = base or system_prompt
            elif item.get("type") == "turn_context":
                detected_cwd = payload.get("cwd") or detected_cwd
                detected_model = payload.get("model") or detected_model
            elif item.get("type") == "event_msg" and payload.get("type") == "thread_settings_applied":
                settings = payload.get("thread_settings") or {}
                detected_cwd = settings.get("cwd") or detected_cwd
                detected_model = settings.get("model") or detected_model
            elif item.get("type") == "response_item":
                payload_type = payload.get("type")
                ts = _timestamp_from_item(item)
                event_id = payload.get("id") or item.get("id") or f"line:{len(raw_events)}"
                if payload_type == "message":
                    role = payload.get("role")
                    content = _codex_text(payload.get("content"))
                    if role in ("system", "developer", "user", "assistant") and content:
                        raw_events.append({"role": role, "content": content, "ts": ts, "source_id": f"codex:message:{event_id}"})
                elif payload_type == "custom_tool_call":
                    value = payload.get("input")
                    args = value
                    if isinstance(value, str) and value[:1] in "[{":
                        try:
                            args = json.loads(value)
                        except json.JSONDecodeError:
                            args = value
                    call_id = payload.get("call_id") or payload.get("id") or event_id
                    raw_events.append({
                        "role": "assistant", "content": "", "tool_name": payload.get("name") or "codex_tool",
                        "tool_calls": [{"id": call_id, "type": "function", "function": {"name": payload.get("name") or "codex_tool", "arguments": args or {}}}],
                        "ts": ts, "source_id": f"codex:call:{call_id}",
                    })
                elif payload_type == "custom_tool_call_output":
                    value = payload.get("output")
                    content = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                    call_id = payload.get("call_id") or event_id
                    raw_events.append({"role": "tool", "content": content, "tool_name": "codex_tool_output", "tool_call_id": call_id, "ts": ts, "source_id": f"codex:output:{call_id}"})
            elif item.get("type") == "world_state":
                state = payload.get("state")
                if state:
                    context = json.dumps(state, ensure_ascii=False, sort_keys=True)
                    system_prompt = (system_prompt + "\n\nCodex world state:\n" + context) if system_prompt else context
    return raw_events, detected_model, detected_cwd, system_prompt


def _exec_sync_worker(data: dict) -> int:
    conv_id = data["conv_id"]
    title = data.get("title", "")
    target_profile = data.get("target_profile", "simpay")
    prof_dir = Path(data["prof_dir"])
    final_model = data["model_name"]
    effective_cwd = data["cwd_dir"]
    transcript_path = Path(data["transcript_path"])
    source = data.get("source", "antigravity")

    old_home = os.environ.get("HERMES_HOME")
    os.environ["HERMES_HOME"] = str(prof_dir)
    try:
        from hermes_state import SessionDB
        sdb = SessionDB()

        raw_events, _, _, system_prompt = _parse_transcript(transcript_path, source)

        sess = sdb.get_session(conv_id)
        if not sess:
            sdb.create_session(
                session_id=conv_id,
                source=source,
                model=final_model,
                cwd=effective_cwd,
                system_prompt=system_prompt,
            )
            s_title = title or data.get("auto_title") or f"{source.title()} Session {conv_id[:8]}"
            sdb.set_session_title(conv_id, s_title)
        else:
            if title:
                sdb.set_session_title(conv_id, title)
            try:
                sdb.update_session_model(conv_id, final_model)
            except Exception as mod_err:
                _log(f"update_session_model non-fatal: {mod_err}")
            if system_prompt:
                try:
                    sdb.update_system_prompt(conv_id, system_prompt)
                except Exception as prompt_err:
                    _log(f"update_system_prompt non-fatal: {prompt_err}")

        existing_rows = sdb.get_messages(conv_id, limit=100000)
        existing_ids = {row.get("platform_message_id") for row in existing_rows if row.get("platform_message_id")}
        if existing_ids:
            new_events = [ev for ev in raw_events if ev.get("source_id") not in existing_ids]
        else:
            existing_count = sdb.message_count(conv_id)
            new_events = raw_events[existing_count:] if existing_count < len(raw_events) else []
        inserted = 0
        for ev in new_events:
            tcalls_json = json.dumps(ev["tool_calls"], ensure_ascii=False) if ev.get("tool_calls") else None
            sdb.append_message(
                session_id=conv_id,
                role=ev["role"],
                content=ev["content"],
                tool_name=ev.get("tool_name"),
                tool_calls=tcalls_json,
                tool_call_id=ev.get("tool_call_id"),
                reasoning=ev.get("reasoning"),
                platform_message_id=ev.get("source_id"),
                timestamp=ev.get("ts"),
            )
            inserted += 1

        total_msgs = sdb.message_count(conv_id)
        sdb.close()
        msg = (
            f"Successfully synced conversation '{conv_id}' to Hermes profile '{target_profile}':\n"
            f"- Model: {final_model}\n"
            f"- Total messages in Hermes state.db: {total_msgs}\n"
            f"- Newly appended in this sync: {inserted}\n"
            f"- Ready to continue inside Hermes Desktop or CLI (`hermes -s {conv_id}`)."
        )
        print(msg)
        return 0
    except Exception as e:
        _log(f"sync-worker failed: {e}")
        print(f"Failed to sync session to Hermes: {e}", file=sys.stderr)
        return 1
    finally:
        if old_home is not None:
            os.environ["HERMES_HOME"] = old_home
        else:
            os.environ.pop("HERMES_HOME", None)


def _can_import_hermes_state() -> bool:
    try:
        import hermes_state  # noqa: F401
        return True
    except Exception:
        return False


def _tool_session_sync(
    conversation_id: str = "",
    title: str = "",
    profile_name: str = "",
    model_name: str = "",
    cwd_dir: str = "",
    transcript_path: str = "",
    source: str = "",
) -> str:
    target_profile = profile_name or "simpay"
    conv_id = (conversation_id or "").strip()
    if conv_id.lower() in ("latest", "current", "auto"):
        conv_id = ""

    lookup_cwd = cwd_dir or os.getenv("CLAUDE_PROJECT_DIR", "") or os.getcwd()
    resolved_path, src = _find_session_transcript(conv_id, transcript_path, source, lookup_cwd)
    if not resolved_path:
        scope = f"conversation '{conv_id}'" if conv_id else "any recent session"
        return (
            f"Transcript file not found for {scope} in Antigravity, Codex or Claude Code (~/.claude/projects) session storage. "
            f"Pass `transcript_path` explicitly or a valid `conversation_id`."
        )
    if not conv_id:
        conv_id = resolved_path.stem
        _log(f"session_sync: no conversation_id given, using newest claude transcript -> {conv_id}")

    prof_dir = (HERMES_BASE / "profiles" / target_profile) if target_profile != "default" else HERMES_BASE
    _, detected_model, detected_cwd, _ = _parse_transcript(resolved_path, src)
    if src == "claude":
        final_model = model_name if model_name and model_name != "antigravity" else (detected_model or "claude")
    elif src == "codex":
        final_model = model_name if model_name and model_name != "antigravity" else (detected_model or "codex")
    else:
        final_model = _normalize_model_name(model_name) if (model_name and model_name != "antigravity") else (detected_model or "gemini-3.8-flash")
    effective_cwd = cwd_dir or detected_cwd or os.getcwd()

    payload = {
        "conv_id": conv_id,
        "title": title,
        "auto_title": _claude_title(resolved_path) if src == "claude" else None,
        "target_profile": target_profile,
        "prof_dir": str(prof_dir),
        "model_name": final_model,
        "cwd_dir": effective_cwd,
        "transcript_path": str(resolved_path),
        "source": src,
    }

    # Fallback: hermes_state lives in the Hermes venv; hop into it when this interpreter can't import it.
    hermes_py = HERMES_BASE / "hermes-agent" / "venv" / "bin" / "python"
    needs_hop = sys.version_info < (3, 10) or not _can_import_hermes_state()
    if needs_hop and hermes_py.is_file():
        import subprocess
        proc = subprocess.run(
            [str(hermes_py), str(Path(__file__).resolve()), "--sync-worker", json.dumps(payload)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            err = proc.stderr.strip() or proc.stdout.strip()
            _log(f"session_sync worker error: {err}")
            return f"Failed to sync session to Hermes: {err}"
        return proc.stdout.strip()

    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    with redirect_stdout(f):
        rc = _exec_sync_worker(payload)
    if rc == 0:
        return f.getvalue().strip()
    return f"Failed to sync session to Hermes: {f.getvalue().strip()}"


TOOLS = [
    {
        "name": "session_sync",
        "description": "Reflect and persist a Claude Code, Codex or Antigravity conversation transcript into Hermes state.db (incremental, idempotent), so the session can continue inside Hermes Desktop or CLI. Source is auto-detected; if conversation_id is omitted the newest Claude Code transcript of the current project is used.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "conversation_id": {"type": "string", "description": "Session UUID (Claude Code sessionId, Codex thread id or Antigravity conversation id). Optional for Claude Code: omit or pass 'latest' to sync the newest transcript of the current project."},
                "source": {"type": "string", "enum": ["auto", "claude", "codex", "antigravity"], "description": "Which agent produced the transcript (default 'auto': Antigravity, Codex, then Claude Code)."},
                "title": {"type": "string", "description": "Optional title for the Hermes session (Claude Code's own session title is used when omitted)."},
                "profile": {"type": "string", "description": "Target Hermes profile (defaults to 'simpay')."},
                "model_name": {"type": "string", "description": "Model identifier to record (defaults to the model detected in the transcript)."},
                "cwd_dir": {"type": "string", "description": "Working directory of the session (also used to locate Claude Code's per-project transcripts)."},
                "transcript_path": {"type": "string", "description": "Optional explicit JSONL transcript path; the dialect is sniffed automatically."}
            }
        }
    },
    {
        "name": "profile_list",
        "description": "List all configured Hermes profiles (e.g. 'simpay', 'sub', 'remote', 'default') and check which have history databases.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "context_pack",
        "description": "Generates a complete Hermes Context Pack (persistent memory + domain skills matched to the prompt) leveraging the official Hermes harness algorithm.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_description": {"type": "string", "description": "Description or prompt of the current task to match relevant skills."},
                "max_skills": {"type": "integer", "description": "Maximum number of relevant skills to include (default: 3, max: 10)."},
                "profile": {"type": "string", "description": "Optional profile name (e.g. 'simpay', 'sub', 'default'). Defaults to 'simpay'."},
            },
            "required": ["task_description"],
        },
    },
    {
        "name": "memory_search",
        "description": "Search the Hermes persistent memory (MEMORY.md notes + USER.md profile) for lines relevant to a query. Read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to look for (keywords from the current task)."},
                "profile": {"type": "string", "description": "Optional profile name (defaults to 'simpay')."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "memory_record",
        "description": "Increment, update or curate Hermes persistent memory (MEMORY.md for project facts, USER.md for user profile) across sessions and agents.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The concise fact or rule to persist (typically 50-250 characters)."},
                "target": {"type": "string", "enum": ["memory", "user"], "description": "Target store: 'memory' (project/domain fact) or 'user' (user preference). Defaults to 'memory'."},
                "action": {"type": "string", "enum": ["add", "replace", "remove"], "description": "Mutation action: 'add' (append new fact), 'replace' (update existing fact), 'remove' (delete stale fact). Defaults to 'add'."},
                "old_text": {"type": "string", "description": "Substring of existing entry to find when action is 'replace' or 'remove'."},
                "profile": {"type": "string", "description": "Target Hermes profile (e.g. 'sub', 'simpay'). Defaults to 'simpay'."},
            },
            "required": ["content"],
        },
    },
    {
        "name": "skill_list",
        "description": "List all Hermes domain skills (name, description, category). Read-only. Use skill_view to read one in full.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category_filter": {"type": "string", "description": "Optional category filter (e.g. devops, media, automation)."},
                "profile": {"type": "string", "description": "Optional profile name (defaults to 'simpay')."},
            },
        },
    },
    {
        "name": "skill_view",
        "description": "Read a Hermes skill (full procedure: workflows, pitfalls, commands). Read-only. Call skill_list first if unsure of the name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Skill name, e.g. simpay-provider-integration."},
                "profile": {"type": "string", "description": "Optional profile name (defaults to 'simpay')."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "session_list",
        "description": "List recent Hermes conversation sessions (ID, title, model, message count, tool call count, timestamps). Read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum number of sessions to return (default 15, max 50)."},
                "search": {"type": "string", "description": "Optional search term to filter by title, session ID, model or CWD."},
                "profile": {"type": "string", "description": "Optional profile name (defaults to 'simpay')."},
            },
        },
    },
    {
        "name": "session_get",
        "description": "Retrieve the conversation transcript of a specific Hermes session by ID or prefix. Read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session ID or substring (e.g. '20260903_050346_41d12b' or '41d12b')."},
                "limit": {"type": "integer", "description": "Maximum number of messages to return (default 40, max 100)."},
                "offset": {"type": "integer", "description": "Starting message offset (default 0)."},
                "profile": {"type": "string", "description": "Optional profile name (defaults to 'simpay')."},
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "session_tool_calls",
        "description": "Extract all tool calls, arguments and returned outputs from a specific Hermes session. Read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session ID or substring."},
                "tool_name": {"type": "string", "description": "Optional filter for tool name (e.g. terminal, read_file, web_search)."},
                "limit": {"type": "integer", "description": "Maximum number of tool call events to return (default 30)."},
                "profile": {"type": "string", "description": "Optional profile name (defaults to 'simpay')."},
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "session_search",
        "description": "Search across all Hermes sessions and messages using fast SQLite Full-Text Search (FTS). Read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords or search term to look for across all sessions."},
                "limit": {"type": "integer", "description": "Maximum number of matching messages to return (default 15)."},
                "profile": {"type": "string", "description": "Optional profile name (defaults to 'simpay')."},
            },
            "required": ["query"],
        },
    },
]


def _dispatch(name: str, args: dict, default_profile: str) -> str:
    try:
        args = args or {}
        req_prof = str(args.get("profile", "") or "").strip()
        prof_name, mem_dir, skill_dirs, state_db = _resolve_profile(req_prof, default_profile)

        if name == "session_sync":
            return _tool_session_sync(
                conversation_id=str(args.get("conversation_id", "")),
                title=str(args.get("title", "")),
                profile_name=prof_name,
                model_name=str(args.get("model_name", "")),
                cwd_dir=str(args.get("cwd_dir", "")),
                transcript_path=str(args.get("transcript_path", "")),
                source=str(args.get("source", "")),
            )
        if name == "profile_list":
            return _tool_profile_list()
        if name == "context_pack":
            return _tool_context_pack(
                str(args.get("task_description", "")),
                int(args.get("max_skills", 3)),
                prof_name,
            )
        if name == "memory_search":
            return _tool_memory_search(mem_dir, str(args.get("query", "")), prof_name)
        if name == "memory_record":
            return _tool_memory_record(
                content=str(args.get("content", "")),
                target=str(args.get("target", "memory")),
                action=str(args.get("action", "add")),
                old_text=str(args.get("old_text", "")),
                profile_name=prof_name,
            )
        if name == "skill_list":
            return _tool_skill_list(skill_dirs, str(args.get("category_filter", "")), prof_name)
        if name == "skill_view":
            return _tool_skill_view(skill_dirs, str(args.get("name", "")), prof_name)
        if name == "session_list":
            return _tool_session_list(state_db, int(args.get("limit", DEFAULT_SESSION_LIMIT)), str(args.get("search", "")), prof_name)
        if name == "session_get":
            return _tool_session_get(
                state_db,
                str(args.get("session_id", "")),
                int(args.get("limit", DEFAULT_MESSAGE_LIMIT)),
                int(args.get("offset", 0)),
                prof_name,
            )
        if name == "session_tool_calls":
            return _tool_session_tool_calls(
                state_db,
                str(args.get("session_id", "")),
                str(args.get("tool_name", "")),
                int(args.get("limit", 30)),
                prof_name,
            )
        if name == "session_search":
            return _tool_session_search(state_db, str(args.get("query", "")), int(args.get("limit", 15)), prof_name)
        return f"Unknown tool '{name}'. Available: {[t['name'] for t in TOOLS]}"
    except Exception as e:
        _log(f"tool {name} failed: {e}")
        return f"hermes-bridge: tool '{name}' failed (non-fatal): {e}"


def _respond(rid, result=None, error=None) -> None:
    msg: dict = {"jsonrpc": "2.0", "id": rid}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result if result is not None else {}
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def serve(cli_profile: str) -> int:
    default_profile = cli_profile or os.getenv("HERMES_PROFILE", "") or DEFAULT_PROFILE
    _log(f"serving default_profile={default_profile}")
    stdin = sys.stdin
    for raw in stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except Exception:
            continue
        method = msg.get("method", "")
        rid = msg.get("id")
        params = msg.get("params") or {}
        try:
            if method == "initialize":
                _respond(rid, {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "hermes-bridge", "version": "2.4.0"},
                })
            elif method == "tools/list":
                _respond(rid, {"tools": TOOLS})
            elif method == "tools/call":
                tname = params.get("name", "")
                targs = params.get("arguments") or {}
                text = _dispatch(tname, targs, default_profile)
                _respond(rid, {"content": [{"type": "text", "text": text}]})
            elif method == "ping":
                _respond(rid, {})
            elif method.startswith("notifications/"):
                continue
            elif rid is not None:
                _respond(rid, {})
        except Exception as e:
            _log(f"dispatch failed: {e}")
            if rid is not None:
                _respond(rid, error={"code": -32603, "message": str(e)[:300]})
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="hermes-bridge MCP server (Hermes harness superbrain access)")
    ap.add_argument("--profile", default="", help="Default Hermes profile name (default: $HERMES_PROFILE or simpay)")
    ap.add_argument("--sync-worker", default="", help="Internal sync worker payload (JSON)")
    args = ap.parse_args(argv)
    if args.sync_worker:
        return _exec_sync_worker(json.loads(args.sync_worker))
    return serve(args.profile)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
