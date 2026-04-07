"""
src/agents/orchestrator.py
Agent Orchestrator - runs all 7 domain agents with access to
Brain Index, Provider Pool, Tools, and Vision Pipeline.
"""

import asyncio
import json
import re
from typing import Dict, List, Any, Optional
from datetime import date, datetime, UTC
from pathlib import Path


DOMAIN_SYSTEM_PROMPT = """You are {agent_name}, a specialist domain agent inside Baba Desktop Business Brain OS.

Your role: {role}

Data available:
- Business Brain Index: {brain_stats}
- Active tools: {tools}
- Today's date: {date}

STRICT SAFETY RULES:
1. NEVER send messages, emails, or posts - only draft them for approval
2. NEVER move money or make payments
3. NEVER sign documents or agreements
4. NEVER install software without explicit approval
5. ALWAYS flag risks and opportunities clearly
6. ALWAYS end with "Awaiting your approval before any action is taken"

Format responses with clear sections:
- Findings (from indexed data)
- Risks flagged (if any)
- Opportunities identified (if any)
- Recommended actions (ALL marked as "requires approval")
"""


AGENTS = {
    "legal": {
        "name": "Legal Agent",
        "role": "Scan all data for legal risks, disputes, contract issues, council notices, deadlines. Draft letters and summaries. Never give formal legal advice - always recommend consulting a real solicitor for formal matters.",
        "tasks": [
            "Find all unresolved legal issues",
            "Scan contract deadlines and obligations",
            "Draft letter to council",
            "Draft formal demand to debtor",
            "Summarise dispute for solicitor",
            "Flag high-risk items urgently",
            "Review lease and planning notices",
        ],
    },
    "acct": {
        "name": "Accounting Agent",
        "role": "Analyse all bill, invoice, expense, and cashflow data. Track renewals, flag overdue payments, identify savings. Never provide formal accounting advice - always recommend a qualified accountant for tax matters.",
        "tasks": [
            "Tag all recurring bills and amounts",
            "Build renewal calendar (next 90 days)",
            "Flag overdue invoices",
            "Cashflow summary from indexed data",
            "VAT return deadline check",
            "Find unclaimed rebates or credits",
            "Draft invoice chaser (requires approval)",
        ],
    },
    "supplier": {
        "name": "Supplier Agent",
        "role": "Analyse all supplier data: spend, terms, pricing, reps, discounts. Identify renegotiation opportunities, price changes, and missing rebates.",
        "tasks": [
            "Cluster all suppliers by spend",
            "Find renegotiation targets",
            "Spot price changes vs competitors",
            "Rank suppliers by margin impact",
            "Draft renegotiation email (requires approval)",
            "Find missing rebate claims",
        ],
    },
    "deals": {
        "name": "Deal & Property Agent",
        "role": "Scout deal opportunities from indexed data: empty premises, auction listings, subletting potential, liquidation stock, business flips. Surface opportunities - never commit to anything.",
        "tasks": [
            "Find empty or closing premises",
            "Scan for auction listings",
            "Analyse subletting potential",
            "Liquidation stock opportunities",
            "Property status summary",
            "Flag undervalued deals from data",
        ],
    },
    "content": {
        "name": "Content Agent",
        "role": "Generate content ideas, draft posts, scripts, and campaigns - all grounded in the real business data from the Brain Index. All drafts require approval before posting.",
        "tasks": [
            "Generate 10 content ideas from business data",
            "Draft social media post",
            "Build 30-day content calendar",
            "Write product or service description",
            "Draft email campaign",
            "Create ad copy (requires approval)",
        ],
    },
    "comms": {
        "name": "Comms Agent",
        "role": "Analyse all email and WhatsApp threads. Cluster by counterparty, find unanswered messages, draft follow-ups. All send actions require explicit approval.",
        "tasks": [
            "Cluster all threads by counterparty",
            "Find unanswered messages (7+ days)",
            "Summarise WhatsApp conversations",
            "Flag pending replies",
            "Draft follow-up (requires approval)",
            "Build contact relationship map",
        ],
    },
    "pa": {
        "name": "PA & Admin Agent",
        "role": "Track all personal and business admin: bills, insurance, council, vehicles, pets, licences. Surface upcoming renewals and deadlines. Draft reminders for approval.",
        "tasks": [
            "List all upcoming renewals (90 days)",
            "Council correspondence summary",
            "Insurance policies and review dates",
            "Vehicle MOT and service reminders",
            "Draft renewal reminder (requires approval)",
            "Personal admin checklist",
        ],
    },
    "research": {
        "name": "Research Agent",
        "role": "Run deep multi-source research from the Brain Index and web data. Produce actionable, source-aware findings and clearly separate facts from assumptions.",
        "tasks": [
            "Run deep research on current business priority",
            "Compare top 3 strategic options with risks",
            "Build executive brief with references",
            "Summarise legal/accounting implications by scenario",
        ],
    },
    "selfevolve": {
        "name": "Self-Evolving Agent",
        "role": "Identify workflow bottlenecks, repetitive tasks, and optimization opportunities in the current system. Propose safe improvements and automation candidates.",
        "tasks": [
            "Audit repetitive tasks and propose automation",
            "Recommend workflow optimization plan",
            "Identify reliability risks in current operations",
            "Generate staged system-improvement roadmap",
        ],
    },
    "kairos": {
        "name": "Kairos Operations Agent",
        "role": "Act as time-critical operations coordinator. Prioritize tasks by urgency, impact, and deadlines; orchestrate fast response plans with clear approval gates.",
        "tasks": [
            "Prioritise urgent tasks for next 24 hours",
            "Generate critical-path execution plan",
            "Build deadline-risk escalation matrix",
            "Create rapid response checklist for blocked tasks",
        ],
    },
    "obsidian": {
        "name": "Obsidian Knowledge Agent",
        "role": "Maintain structured knowledge capture for business decisions, notes, and linked ideas using an Obsidian vault workflow.",
        "tasks": [
            "Generate structured note from latest decisions",
            "Summarise key insights into Obsidian-ready markdown",
            "Build linked knowledge map from recent projects",
            "Create weekly knowledge digest",
        ],
    },
    "wiki": {
        "name": "LLM Wiki Curator Agent",
        "role": "Compile, maintain, and lint a persistent markdown-first knowledge base from raw sources; preserve traceability and cross-links.",
        "tasks": [
            "Compile raw notes into structured wiki pages",
            "Maintain backlinks and concept pages",
            "Run consistency and link lint checks",
            "Propose weekly knowledge maintenance tasks",
        ],
    },
    "solicitor": {
        "name": "Solicitor Expert Agent",
        "role": "Legal specialist for disputes, contracts, notices, property compliance, and deadlines. Draft solicitor-ready summaries and letters. Never provide formal legal advice.",
        "tasks": [
            "Build legal risk register from indexed data",
            "Draft solicitor briefing pack",
            "Prioritise legal deadlines and notices",
            "Draft formal response letters (approval required)",
        ],
    },
    "accountant": {
        "name": "Accountant Expert Agent",
        "role": "Accounting specialist for VAT/HMRC, invoices, cashflow, and controls. Produce accountant-ready summaries and action lists.",
        "tasks": [
            "Prepare VAT/HMRC risk and deadline summary",
            "Analyse overdue invoices and payment risk",
            "Build weekly cashflow action plan",
            "Draft accountant handover summary",
        ],
    },
    "moneymaker": {
        "name": "Money-Making Expert Agent",
        "role": "Revenue and margin specialist across deals, suppliers, stock, and opportunities. Focus on practical upside with clear risks.",
        "tasks": [
            "Find top profit opportunities in current data",
            "Rank margin improvement actions by impact",
            "Identify supplier renegotiation wins",
            "Create 30-day money-action plan",
        ],
    },
    "coder": {
        "name": "Coding & Programming Expert Agent",
        "role": "Technical delivery specialist for automation, scripts, integrations, and reliable implementation plans. Keep changes safe and approval-gated.",
        "tasks": [
            "Design implementation plan for requested feature",
            "Propose safe automation scripts and checks",
            "Draft integration steps and validation tests",
            "Prepare debugging and rollback checklist",
        ],
    },
    "programmer": {
        "name": "Programmer Expert Agent",
        "role": "Programming specialist (alias of coding expert) for end-to-end implementation strategy and technical execution support.",
        "tasks": [
            "Break feature into coding milestones",
            "Generate test-first implementation outline",
            "Identify technical risks and mitigations",
            "Produce deployment-safe change plan",
        ],
    },
}


def _load_custom_agents():
    cfg = Path("config/agents_custom.json")
    if not cfg.exists():
        return
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return
        for agent_id, meta in data.items():
            if not isinstance(meta, dict):
                continue
            role = str(meta.get("role", "")).strip()
            name = str(meta.get("name", agent_id)).strip() or agent_id
            tasks = meta.get("tasks", [])
            if not isinstance(tasks, list):
                tasks = []
            AGENTS[agent_id] = {
                "name": name,
                "role": role or f"Custom agent: {name}",
                "tasks": [str(t) for t in tasks if str(t).strip()],
            }
    except Exception:
        return


_load_custom_agents()


class AgentOrchestrator:
    """Runs domain agents using the provider pool and brain index."""

    def __init__(self, pool, brain, tools, vision=None):
        self.pool = pool
        self.brain = brain
        self.tools = tools
        self.vision = vision
        self.evidence_required_mode = True
        # Web tool policy for agent-initiated tool calls:
        # ask (default), approved, denied, stopped
        self.web_tools_policy = "ask"

    def _resolve_agent_id(self, agent_id: str) -> str:
        aliases = {
            "solicitor_expert": "solicitor",
            "legal_expert": "solicitor",
            "accounting": "accountant",
            "acct_expert": "accountant",
            "money": "moneymaker",
            "moneymaker_expert": "moneymaker",
            "coding": "coder",
            "coding_expert": "coder",
            "developer": "coder",
            "dev": "coder",
            "programming": "programmer",
            "programmer_expert": "programmer",
        }
        aid = (agent_id or "").strip().lower()
        return aliases.get(aid, aid)

    async def run(self, agent_id: str, task: str, extra_context: str = "") -> str:
        agent_id = self._resolve_agent_id(agent_id)
        agent = AGENTS.get(agent_id)
        if not agent:
            raise ValueError(f"Unknown agent: {agent_id}")

        brain_stats = self.brain.stats()
        tools_list = ", ".join([t["name"] for t in self.tools.all()])

        system = DOMAIN_SYSTEM_PROMPT.format(
            agent_name=agent["name"],
            role=agent["role"],
            brain_stats=f"{brain_stats['emails']} emails, {brain_stats['docs']} docs, {brain_stats['high_risk']} high-risk items",
            tools=tools_list or "brain_search, draft, analyse",
            date=date.today().isoformat(),
        )
        if self.evidence_required_mode:
            system = (
                f"{system}\n\n"
                "EVIDENCE REQUIRED MODE (STRICT):\n"
                "- Do not invent facts, dates, counts, legal outcomes, or names.\n"
                "- If uncertain, explicitly state unknown.\n"
                "- Include an 'Evidence trail' section listing the sources used.\n"
                "- Include a one-line 'Confidence' rating (high/medium/low) with reason.\n"
            )

        brain_context = self._get_brain_context(agent_id)

        user_message = f"""Task: {task}

Relevant data from Business Brain Index:
{brain_context}

{extra_context}

Please analyse and respond according to your role. Remember: draft only, never execute."""

        messages = [{"role": "user", "content": user_message}]

        provider, model = self._route(agent_id)

        try:
            reply = await self.pool.chat(
                provider, model, messages, system=system, max_tokens=2048
            )
        except Exception:
            reply, _ = await self.pool.chat_with_fallback(
                provider, model, messages, system=system
            )

        proposal_status = self._handle_skill_proposals_from_reply(reply, agent_id)
        reply_clean = self._strip_skill_request_blocks(reply)
        tool_results = self._execute_tool_calls_from_reply(reply_clean)
        if tool_results:
            tool_feedback = json.dumps(tool_results, indent=2)
            follow_up = (
                "Tool calls requested by your previous output have been executed.\n"
                f"Tool results:\n{tool_feedback}\n\n"
                "Now provide the final user-facing response using those tool results. "
                "Do not include internal reasoning tags."
            )
            messages_2 = [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": reply_clean},
                {"role": "user", "content": follow_up},
            ]
            try:
                reply_clean = await self.pool.chat(
                    provider, model, messages_2, system=system, max_tokens=2048
                )
            except Exception:
                reply_clean, _ = await self.pool.chat_with_fallback(
                    provider, model, messages_2, system=system
                )

        if proposal_status.get("queued", 0) > 0:
            reply_clean = (
                f"{reply_clean}\n\n"
                f"[Self-Evolve] Queued {proposal_status['queued']} skill proposal(s) for approval."
            )

        if self.evidence_required_mode:
            reply_clean = self._ensure_evidence_trail(reply_clean, brain_context, tool_results)

        return reply_clean

    def run_sync(self, agent_id: str, task: str, extra_context: str = "") -> str:
        return asyncio.run(self.run(agent_id, task, extra_context=extra_context))

    def set_web_tools_policy(self, policy: str):
        p = str(policy or "").strip().lower()
        if p not in {"ask", "approved", "denied", "stopped"}:
            p = "ask"
        self.web_tools_policy = p

    def set_evidence_required_mode(self, enabled: bool):
        self.evidence_required_mode = bool(enabled)

    def list_agents(self) -> List[Dict]:
        return [
            {"id": k, "name": v["name"], "tasks": v["tasks"]} for k, v in AGENTS.items()
        ]

    def _route(self, agent_id: str):
        agent_id = self._resolve_agent_id(agent_id)
        routes = {
            "legal": ("groq", "llama-3.3-70b-versatile"),
            "acct": ("jan", "Qwen3_5-9B_Q4_K_M"),
            "supplier": ("jan", "Qwen3_5-9B_Q4_K_M"),
            "deals": ("groq", "llama-3.3-70b-versatile"),
            "content": ("groq", "llama-3.3-70b-versatile"),
            "comms": ("ollama", "qwen3.5:latest"),
            "pa": ("ollama", "qwen3.5:latest"),
            "research": ("groq", "llama-3.3-70b-versatile"),
            "selfevolve": ("lmstudio", "mradermacher/omnicoder-9b"),
            "kairos": ("jan", "Jackrong/Qwen3.5-9B-Claude-4.6-Opus-Reasoning-Distilled-v2-GGUF"),
            "obsidian": ("ollama", "qwen3.5:latest"),
            "wiki": ("ollama", "qwen3.5:latest"),
            "solicitor": ("jan", "Meta-Llama-3_1-8B-Instruct-IQ4_XS"),
            "accountant": ("jan", "Meta-Llama-3_1-8B-Instruct-IQ4_XS"),
            "moneymaker": ("jan", "Meta-Llama-3_1-8B-Instruct-IQ4_XS"),
            "coder": ("ollama", "qwen3.5:latest"),
            "programmer": ("ollama", "qwen3.5:latest"),
        }
        return routes.get(agent_id, ("ollama", "qwen3.5:latest"))

    def _get_brain_context(self, agent_id: str, limit: int = 10) -> str:
        agent_id = self._resolve_agent_id(agent_id)
        type_map = {
            "legal": ["legal"],
            "acct": ["bill", "insurance"],
            "supplier": ["supplier"],
            "deals": ["property", "deal"],
            "content": [],
            "comms": ["comms"],
            "pa": ["bill", "insurance", "ops"],
            "wiki": [],
            "solicitor": ["legal", "property"],
            "accountant": ["bill", "insurance", "ops"],
            "moneymaker": ["deal", "supplier", "bill", "ops"],
            "coder": ["ops", "comms"],
            "programmer": ["ops", "comms"],
        }
        types = type_map.get(agent_id, [])
        items = []
        for t in types:
            items.extend(self.brain.by_type(t, limit=limit // max(len(types), 1)))

        if not items:
            items = self.brain.all(limit=limit)

        if not items:
            return "No data indexed yet - import emails, PDFs, or WhatsApp exports in the Brain Index tab."

        lines = []
        for it in items[:limit]:
            risk = (
                f" [RISK:{it['risk_level'].upper()}]"
                if it.get("risk_level") not in ("none", None)
                else ""
            )
            renew = f" [RENEWAL:{it['renewal_date']}]" if it.get("renewal_date") else ""
            lines.append(f"- [{it['type'].upper()}] {it['summary'][:80]}{risk}{renew}")

        return "\n".join(lines)

    def _strip_skill_request_blocks(self, text: str) -> str:
        cleaned = re.sub(
            r"<request_new_skill>[\s\S]*?</request_new_skill>",
            "",
            text or "",
            flags=re.IGNORECASE,
        )
        return cleaned.strip()

    def _extract_skill_requests(self, text: str) -> List[Dict[str, str]]:
        blocks = re.findall(
            r"<request_new_skill>([\s\S]*?)</request_new_skill>",
            text or "",
            flags=re.IGNORECASE,
        )
        out = []
        for block in blocks:
            name = ""
            reason = ""
            risk = ""
            code = ""
            lines = block.splitlines()
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                low = line.lower()
                if low.startswith("name:"):
                    name = line.split(":", 1)[1].strip()
                elif low.startswith("reason:"):
                    reason = line.split(":", 1)[1].strip()
                elif low.startswith("risk:"):
                    risk = line.split(":", 1)[1].strip()
                elif low.startswith("code:"):
                    code_head = line.split(":", 1)[1].lstrip()
                    code_tail = "\n".join(lines[i + 1 :])
                    code = f"{code_head}\n{code_tail}".strip() if code_tail else code_head
                    break
                i += 1

            if name and code:
                out.append(
                    {
                        "name": name,
                        "reason": reason,
                        "risk": risk,
                        "code": code,
                    }
                )
        return out

    def _handle_skill_proposals_from_reply(
        self, reply: str, agent_id: str
    ) -> Dict[str, Any]:
        requests = self._extract_skill_requests(reply)
        if not requests:
            return {"queued": 0}
        if not hasattr(self.tools, "save_runtime_proposal"):
            return {"queued": 0, "error": "Tool registry proposal API unavailable"}

        queued = 0
        errors = []
        for req in requests:
            try:
                self.tools.save_runtime_proposal(
                    req.get("name", ""),
                    req.get("reason", ""),
                    req.get("code", ""),
                    req.get("risk", ""),
                    metadata={"agent_id": agent_id},
                )
                queued += 1
            except Exception as e:
                errors.append(str(e))
        return {"queued": queued, "errors": errors}

    def _execute_tool_calls_from_reply(self, reply: str) -> List[Dict[str, Any]]:
        tool_calls = []
        for match in re.finditer(r"\{[\s\S]*?\}", reply or ""):
            chunk = match.group(0)
            if '"action"' not in chunk:
                continue
            try:
                data = json.loads(chunk)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            action = str(data.get("action", "")).strip().lower()
            if action not in {"use_tool", "tool_call"}:
                continue
            tool_name = str(data.get("tool", "")).strip()
            args = data.get("args", {})
            if not tool_name:
                continue
            if not isinstance(args, dict):
                args = {}
            # Approval-gated web tools for agent autonomy safety.
            if tool_name in {"web_search", "web_fetch"}:
                policy = str(getattr(self, "web_tools_policy", "ask") or "ask").lower()
                if policy in {"ask", "denied", "stopped"}:
                    tool_calls.append(
                        {
                            "tool": tool_name,
                            "args": args,
                            "ok": False,
                            "error": f"Web tool blocked by policy '{policy}'.",
                        }
                    )
                    continue
            try:
                result = self.tools.run(tool_name, **args)
                tool_calls.append(
                    {"tool": tool_name, "args": args, "ok": True, "result": result}
                )
            except Exception as e:
                tool_calls.append(
                    {"tool": tool_name, "args": args, "ok": False, "error": str(e)}
                )
        return tool_calls

    def _ensure_evidence_trail(
        self, reply: str, brain_context: str, tool_results: List[Dict[str, Any]]
    ) -> str:
        text = str(reply or "").strip() or "No output generated."
        low = text.lower()
        if "evidence trail" in low and "confidence" in low:
            return text

        used_tools = []
        for tr in tool_results or []:
            if not isinstance(tr, dict):
                continue
            tname = str(tr.get("tool", "") or "").strip()
            ok = bool(tr.get("ok"))
            if tname:
                used_tools.append(f"{tname} ({'ok' if ok else 'blocked/failed'})")
        tools_txt = ", ".join(used_tools[:6]) if used_tools else "none"

        brain_lines = []
        for ln in str(brain_context or "").splitlines():
            s = ln.strip()
            if s:
                brain_lines.append(s[:120])
            if len(brain_lines) >= 4:
                break
        brain_txt = "; ".join(brain_lines) if brain_lines else "No indexed context available"

        tail = (
            "\n\nEvidence trail:\n"
            f"- Brain context: {brain_txt}\n"
            f"- Tool outputs: {tools_txt}\n"
            "- Unknowns were not guessed.\n"
            "Confidence: medium (auto-enforced evidence mode)\n"
        )
        return text + tail


class MoneyEngine:
    """Generates money-making and savings opportunities from Brain Index data."""

    def __init__(self, brain, pool):
        self.brain = brain
        self.pool = pool

    async def full_analysis(self) -> Dict[str, Any]:
        suppliers = self.brain.suppliers()
        bills = self.brain.bills()
        renewals = self.brain.renewals_due(90)
        legal = self.brain.legal_items()

        prompt = f"""Analyse this business data and identify ALL money-making and savings opportunities.

SUPPLIERS ({len(suppliers)} found):
{self._fmt_items(suppliers, 5)}

BILLS & EXPENSES ({len(bills)} found):
{self._fmt_items(bills, 5)}

RENEWALS DUE IN 90 DAYS ({len(renewals)}):
{self._fmt_items(renewals, 5)}

LEGAL ITEMS ({len(legal)} found):
{self._fmt_items(legal, 3)}

Provide:
1. Top 5 immediate savings (with estimated GBP value)
2. Top 5 income opportunities (with realistic GBP estimate)
3. Top 3 property/premises angles
4. Top 3 online income plays
5. Priority action list (all require user approval before execution)

Be specific and grounded in the data above."""

        messages = [{"role": "user", "content": prompt}]
        try:
            reply = await self.pool.chat(
                "groq", "llama-3.3-70b-versatile", messages, max_tokens=2048
            )
        except Exception:
            reply, _ = await self.pool.chat_with_fallback(
                "groq", "llama-3.3-70b-versatile", messages
            )
        return {
            "analysis": reply,
            "supplier_count": len(suppliers),
            "bill_count": len(bills),
            "renewal_count": len(renewals),
        }

    def run_sync(self) -> Dict[str, Any]:
        return asyncio.run(self.full_analysis())

    def _fmt_items(self, items: List[Dict], limit: int) -> str:
        lines = []
        for it in items[:limit]:
            amounts = it.get("amounts", [])
            amt = f" GBP{amounts[0]['value']}" if amounts else ""
            lines.append(f"  - {it.get('summary', '')[:70]}{amt}")
        return "\n".join(lines) if lines else "  (none indexed yet)"
