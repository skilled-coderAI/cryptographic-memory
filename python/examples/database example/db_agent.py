"""Shared cryptomem engine that turns a SQLite sales database into verified memory.

This module is the brain behind the web view in ``server.py``. At startup it
builds a small, realistic **sales/CRM SQLite database** (reps, deals, quarters,
regions, products) and then *derives signed facts* from it -- per-deal facts plus
roll-up aggregates such as quarterly closed-won revenue, win rates, regional
totals and per-rep performance -- and archives each one as a cryptographically
signed :class:`cryptomem.MemoryClient` node.

No SQL is ever generated or executed to answer a user's question. The user just
asks in plain English (e.g. *"what kind of sales effort happened in Q2?"*) and a
local Ollama model answers **only** from these signature-verified database facts,
abstaining when nothing verified matches. :func:`run_pipeline` runs the retrieval
*stage by stage* and reports each stage through an ``emit`` callback so the UI can
show exactly how a database fact becomes a trusted answer:

    understand -> recall verified DB facts -> signature verification
    -> grounding gate -> (grounded) synthesize | (nothing verified) abstain

Similarities, signature checks, confidences and the Merkle ledger root all come
straight from the engine; the underlying numbers come straight from the database.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable
from typing import Any

from cryptomem import MemoryClient

MIN_CONFIDENCE = float(os.environ.get("MEM_MIN_CONFIDENCE", "0.30"))
OLLAMA_HOST = os.environ.get("CRYPTOMEM_OLLAMA_URL", "http://localhost:11434")
MODEL_ID = os.environ.get("AGNO_MODEL", "qwen3.5:0.8b")
# KV-cache context window. Smaller = far less RAM, which matters a lot when a
# tiny model shares an 8 GB CPU box with the embedder.
NUM_CTX = int(os.environ.get("MEM_NUM_CTX", "2048"))
# Embedder: "stub" (zero-RAM, default) keeps memory free for the local model on
# small machines; set MEM_EMBEDDER=minilm for real semantic retrieval -- strongly
# recommended here because the database produces many similar-sounding facts.
EMBEDDER_CHOICE = os.environ.get("MEM_EMBEDDER", "stub").lower()

Emit = Callable[[dict], None]

_MEM: MemoryClient | None = None
_DB: sqlite3.Connection | None = None
_EMBEDDER_LABEL = "stub"

FISCAL_YEAR = "FY26"

# --- seed rows: a compact but realistic sales/CRM dataset -------------------
# reps: id, name, region, hire_year
_REPS = [
    (1, "Alice Chen", "West", 2021),
    (2, "Bob Martins", "East", 2019),
    (3, "Carla Diaz", "West", 2022),
    (4, "Devin Okafor", "Central", 2020),
    (5, "Priya Nair", "East", 2023),
]

# deals: id, rep_id, quarter, region, product, amount, stage
#   stage in {"Closed Won", "Closed Lost", "Open"}
_DEALS = [
    (101, 1, "Q1", "West", "Platform", 120000, "Closed Won"),
    (102, 1, "Q1", "West", "Analytics", 64000, "Closed Won"),
    (103, 2, "Q1", "East", "Platform", 90000, "Closed Lost"),
    (104, 4, "Q1", "Central", "Support", 28000, "Closed Won"),
    (105, 3, "Q1", "West", "Analytics", 41000, "Open"),
    (106, 5, "Q1", "East", "Platform", 76000, "Closed Won"),
    (107, 1, "Q2", "West", "Platform", 210000, "Closed Won"),
    (108, 2, "Q2", "East", "Analytics", 88000, "Closed Won"),
    (109, 2, "Q2", "East", "Platform", 150000, "Open"),
    (110, 3, "Q2", "West", "Support", 33000, "Closed Lost"),
    (111, 4, "Q2", "Central", "Platform", 132000, "Closed Won"),
    (112, 5, "Q2", "East", "Analytics", 57000, "Closed Won"),
    (113, 1, "Q2", "West", "Support", 24000, "Open"),
    (114, 3, "Q3", "West", "Platform", 168000, "Closed Won"),
    (115, 2, "Q3", "East", "Analytics", 72000, "Closed Lost"),
    (116, 4, "Q3", "Central", "Analytics", 95000, "Closed Won"),
    (117, 5, "Q3", "East", "Platform", 184000, "Closed Won"),
    (118, 1, "Q3", "West", "Platform", 102000, "Open"),
    (119, 3, "Q3", "West", "Support", 38000, "Closed Won"),
    (120, 2, "Q4", "East", "Platform", 240000, "Open"),
    (121, 4, "Q4", "Central", "Platform", 156000, "Closed Won"),
    (122, 5, "Q4", "East", "Analytics", 81000, "Closed Won"),
    (123, 1, "Q4", "West", "Analytics", 67000, "Open"),
    (124, 3, "Q4", "West", "Platform", 199000, "Closed Won"),
]

_QUARTER_LABEL = {
    "Q1": "Q1 FY26",
    "Q2": "Q2 FY26",
    "Q3": "Q3 FY26",
    "Q4": "Q4 FY26",
}


def _build_embedder() -> Any:
    """Select the embedder: lightweight stub by default, MiniLM on request."""
    global _EMBEDDER_LABEL
    if EMBEDDER_CHOICE in ("minilm", "semantic", "local"):
        try:
            from cryptomem import MiniLMEmbedder

            embedder = MiniLMEmbedder()
            embedder.embed("warmup")  # surface download/offline errors up front
            _EMBEDDER_LABEL = "MiniLM (semantic, 384-dim)"
            return embedder
        except Exception as exc:  # noqa: BLE001 - intentional graceful fallback
            from cryptomem import StubEmbedder

            _EMBEDDER_LABEL = f"stub (MiniLM unavailable: {exc})"
            return StubEmbedder()

    from cryptomem import StubEmbedder

    _EMBEDDER_LABEL = "stub (hash-based, low-RAM)"
    return StubEmbedder()


def get_db() -> sqlite3.Connection:
    """Return the process-wide sales database, building + seeding it on first use."""
    global _DB
    if _DB is None:
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _seed_db(conn)
        _DB = conn
    return _DB


def _seed_db(conn: sqlite3.Connection) -> None:
    """Create the schema and load the seed rows (idempotent)."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS reps (
            id        INTEGER PRIMARY KEY,
            name      TEXT NOT NULL,
            region    TEXT NOT NULL,
            hire_year INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS deals (
            id       INTEGER PRIMARY KEY,
            rep_id   INTEGER NOT NULL REFERENCES reps(id),
            quarter  TEXT NOT NULL,
            region   TEXT NOT NULL,
            product  TEXT NOT NULL,
            amount   INTEGER NOT NULL,
            stage    TEXT NOT NULL
        );
        """
    )
    if conn.execute("SELECT COUNT(*) FROM reps").fetchone()[0] == 0:
        conn.executemany("INSERT INTO reps VALUES (?, ?, ?, ?)", _REPS)
    if conn.execute("SELECT COUNT(*) FROM deals").fetchone()[0] == 0:
        conn.executemany("INSERT INTO deals VALUES (?, ?, ?, ?, ?, ?, ?)", _DEALS)
    conn.commit()


def _money(value: float) -> str:
    return f"${value:,.0f}"


def get_memory() -> MemoryClient:
    """Return the process-wide MemoryClient, archiving DB-derived facts on first use."""
    global _MEM
    if _MEM is None:
        _MEM = MemoryClient(embedder=_build_embedder())
        _seed_memory_from_db(_MEM, get_db())
    return _MEM


def embedder_label() -> str:
    return _EMBEDDER_LABEL


def _seed_memory_from_db(mem: MemoryClient, db: sqlite3.Connection) -> None:
    """Derive signed facts + aggregates from the sales DB (idempotent).

    Every fact's ``content`` is computed directly from the database, so the
    agent's verified answers always reflect the real underlying data.
    """
    if any(h.verified for h in mem.query("quarterly sales revenue", top_k=1)):
        return

    src = "sales.db"

    # 1) Per-quarter sales-effort roll-ups (the headline "effort" facts).
    rows = db.execute(
        """
        SELECT quarter,
               COUNT(*)                                              AS opps,
               SUM(amount)                                           AS pipeline,
               SUM(CASE WHEN stage='Closed Won'  THEN 1 ELSE 0 END)  AS won,
               SUM(CASE WHEN stage='Closed Won'  THEN amount ELSE 0 END) AS won_amt,
               SUM(CASE WHEN stage='Closed Lost' THEN 1 ELSE 0 END)  AS lost,
               SUM(CASE WHEN stage='Open'        THEN 1 ELSE 0 END)  AS open_cnt,
               SUM(CASE WHEN stage='Open'        THEN amount ELSE 0 END) AS open_amt
        FROM deals GROUP BY quarter ORDER BY quarter
        """
    ).fetchall()
    for r in rows:
        decided = r["won"] + r["lost"]
        win_rate = round(100 * r["won"] / decided) if decided else 0
        label = _QUARTER_LABEL[r["quarter"]]
        mem.archive(
            f"Sales effort {label}",
            f"In {label} the sales team worked {r['opps']} opportunities worth "
            f"{_money(r['pipeline'])} in total pipeline. {r['won']} deals closed won for "
            f"{_money(r['won_amt'])} (a {win_rate}% win rate), {r['lost']} were lost, and "
            f"{r['open_cnt']} remain open worth {_money(r['open_amt'])}.",
            metadata={"source": f"{src}:deals", "quarter": r["quarter"]},
        )

    # 2) Per-region closed-won revenue for the fiscal year.
    rows = db.execute(
        """
        SELECT region,
               SUM(CASE WHEN stage='Closed Won' THEN amount ELSE 0 END) AS won_amt,
               SUM(CASE WHEN stage='Closed Won' THEN 1 ELSE 0 END)      AS won
        FROM deals GROUP BY region ORDER BY won_amt DESC
        """
    ).fetchall()
    for r in rows:
        mem.archive(
            f"{r['region']} region {FISCAL_YEAR}",
            f"The {r['region']} region closed {r['won']} won deals totaling "
            f"{_money(r['won_amt'])} in closed-won revenue across {FISCAL_YEAR}.",
            metadata={"source": f"{src}:deals", "region": r["region"]},
        )

    # 3) Per-product closed-won revenue for the fiscal year.
    rows = db.execute(
        """
        SELECT product, SUM(amount) AS won_amt, COUNT(*) AS won
        FROM deals WHERE stage='Closed Won' GROUP BY product ORDER BY won_amt DESC
        """
    ).fetchall()
    for r in rows:
        mem.archive(
            f"{r['product']} product line {FISCAL_YEAR}",
            f"The {r['product']} product line generated {_money(r['won_amt'])} in closed-won "
            f"revenue from {r['won']} deals across {FISCAL_YEAR}.",
            metadata={"source": f"{src}:deals", "product": r["product"]},
        )

    # 4) Per-rep performance for the fiscal year.
    rows = db.execute(
        """
        SELECT reps.name AS name, reps.region AS region,
               SUM(CASE WHEN deals.stage='Closed Won' THEN deals.amount ELSE 0 END) AS won_amt,
               SUM(CASE WHEN deals.stage='Closed Won' THEN 1 ELSE 0 END)            AS won,
               SUM(CASE WHEN deals.stage='Open'       THEN deals.amount ELSE 0 END) AS open_amt
        FROM reps LEFT JOIN deals ON deals.rep_id = reps.id
        GROUP BY reps.id ORDER BY won_amt DESC
        """
    ).fetchall()
    ranked = [r for r in rows if r["won_amt"]]
    for r in rows:
        mem.archive(
            f"Rep {r['name']}",
            f"{r['name']} ({r['region']} region) closed {r['won']} deals worth "
            f"{_money(r['won_amt'])} and is carrying {_money(r['open_amt'])} in open pipeline "
            f"for {FISCAL_YEAR}.",
            metadata={"source": f"{src}:reps", "rep": r["name"]},
        )

    # 5) Headline facts: top performer + total company revenue.
    if ranked:
        top = ranked[0]
        mem.archive(
            f"Top sales rep {FISCAL_YEAR}",
            f"The top performing sales rep in {FISCAL_YEAR} is {top['name']} with "
            f"{_money(top['won_amt'])} in closed-won revenue from {top['won']} deals.",
            metadata={"source": f"{src}:reps"},
        )
    total = db.execute("SELECT SUM(amount) FROM deals WHERE stage='Closed Won'").fetchone()[0]
    biggest = db.execute(
        """
        SELECT reps.name AS name, deals.product AS product, deals.amount AS amount,
               deals.quarter AS quarter
        FROM deals JOIN reps ON reps.id = deals.rep_id
        WHERE deals.stage='Closed Won' ORDER BY deals.amount DESC LIMIT 1
        """
    ).fetchone()
    mem.archive(
        f"Total company revenue {FISCAL_YEAR}",
        f"Total closed-won revenue across the company for {FISCAL_YEAR} is {_money(total)} "
        f"from all regions combined.",
        metadata={"source": f"{src}:deals"},
    )
    if biggest:
        mem.archive(
            f"Largest deal {FISCAL_YEAR}",
            f"The largest closed-won deal of {FISCAL_YEAR} was a {_money(biggest['amount'])} "
            f"{biggest['product']} sale by {biggest['name']} in "
            f"{_QUARTER_LABEL[biggest['quarter']]}.",
            metadata={"source": f"{src}:deals"},
        )


def schema_summary() -> list[dict]:
    """Describe the underlying sales tables (for the UI 'Database' panel)."""
    db = get_db()
    tables = []
    for (name,) in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall():
        cols = [row["name"] for row in db.execute(f"PRAGMA table_info({name})").fetchall()]
        count = db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        tables.append({"table": name, "columns": cols, "rows": count})
    return tables


def list_facts() -> list[dict]:
    """Return every stored, signature-verified DB fact for the sidebar."""
    mem = get_memory()
    facts = []
    for node in mem.store.all():
        verified = mem.verify(node)
        crypto = node.crypto
        facts.append(
            {
                "node_id": node.node_id,
                "entity": node.entity,
                "content": node.content,
                "verified": verified,
                "hash": (crypto.hash[:12] + "..") if crypto else None,
                "source": node.metadata.get("source"),
            }
        )
    return facts


def _short(text: str, n: int = 90) -> str:
    return text if len(text) <= n else text[: n - 1] + "\u2026"


def run_pipeline(query: str, emit: Emit) -> tuple[str, dict]:
    """Run the verified-DB-memory pipeline, emitting a trace step per stage.

    Returns ``(facts_block, provenance)`` where ``facts_block`` is the string
    handed back to the LLM (the verified database context, or a
    NO_VERIFIED_MEMORY abstention notice) and ``provenance`` summarises what
    grounded the answer.
    """
    mem = get_memory()

    # 1) Understand the question -> embed it for semantic lookup.
    vector = mem.embedder.embed(query)
    emit(
        {
            "type": "step",
            "stage": "embed",
            "title": "Understand question",
            "detail": f"{_EMBEDDER_LABEL} \u2192 {len(vector)}-dim query vector",
        }
    )

    # 2) Recall verified database facts (raw cosine similarity over the signed store).
    candidates = mem.store.query(vector, top_k=6)
    emit(
        {
            "type": "step",
            "stage": "retrieve",
            "title": f"Recall verified database facts \u2014 {len(candidates)} candidate(s)",
            "items": [
                {
                    "node_id": node.node_id,
                    "entity": node.entity,
                    "content": _short(node.content),
                    "similarity": round(float(sim), 3),
                }
                for node, sim in candidates
            ],
        }
    )

    # 3) Re-verify every candidate's Ed25519 signature + content hash.
    verified_rows = []
    scored = []
    for node, sim in candidates:
        ok = mem.verify(node)
        confidence = round(max(float(sim), 0.0), 3) if ok else 0.0
        verified_rows.append(
            {
                "node_id": node.node_id,
                "verified": ok,
                "hash": node.crypto.hash[:12] + ".." if node.crypto else None,
            }
        )
        if ok:
            scored.append((node, confidence))
    emit(
        {
            "type": "step",
            "stage": "verify",
            "title": "Signature verification (SHA-256 + Ed25519)",
            "detail": "Tampered or unsigned rows are dropped before they can ground an answer.",
            "items": verified_rows,
        }
    )

    # 4) Grounding gate: only verified facts above the relevance threshold pass.
    admitted = [(n, c) for n, c in scored if c >= MIN_CONFIDENCE]
    admitted.sort(key=lambda pair: pair[1], reverse=True)
    grounded = bool(admitted)
    emit(
        {
            "type": "step",
            "stage": "gate",
            "title": "Grounding gate",
            "detail": f"threshold = {MIN_CONFIDENCE:.2f} \u00b7 "
            + ("PASS \u2014 grounding" if grounded else "EMPTY \u2014 must abstain"),
            "decision": "grounded" if grounded else "abstain",
            "items": [
                {"node_id": n.node_id, "entity": n.entity, "confidence": c} for n, c in admitted
            ],
        }
    )

    if not grounded:
        provenance = {
            "grounded": False,
            "injected_nodes": [],
            "ledger_root": mem.ledger_root(),
            "verified": False,
        }
        return "NO_VERIFIED_MEMORY: abstain; do not guess.", provenance

    # 5) Provenance: ledger root + the exact signed DB facts that ground the answer.
    provenance = {
        "grounded": True,
        "injected_nodes": [n.node_id for n, _ in admitted],
        "ledger_root": mem.ledger_root(),
        "verified": True,
        "facts": [{"node_id": n.node_id, "entity": n.entity, "confidence": c} for n, c in admitted],
    }
    emit(
        {
            "type": "step",
            "stage": "generate",
            "title": "Synthesize answer from verified data",
            "detail": "Local model is composing an answer from verified database facts only\u2026",
        }
    )

    facts_block = "VERIFIED_FACTS:\n" + "\n".join(
        f"- [{n.node_id}] ({n.entity}) {n.content} (confidence={c:.2f})" for n, c in admitted
    )
    return facts_block, provenance


def build_agent(tool: Callable[..., str], model_id: str | None = None, host: str | None = None):
    """Build the agno agent wired to a single verified-database-memory ``tool``."""
    from agno.agent import Agent
    from agno.models.ollama import Ollama

    return Agent(
        name="Verified Sales Data Agent",
        model=Ollama(
            id=model_id or MODEL_ID,
            host=host or OLLAMA_HOST,
            options={"num_ctx": NUM_CTX},
        ),
        tools=[tool],
        instructions=(
            "You are a sales-data analyst that answers strictly from cryptographically "
            "verified database facts.\n"
            "1. ALWAYS call recall_database_facts before answering a question about sales, "
            "revenue, reps, regions, products, quarters, or pipeline.\n"
            "2. Answer ONLY using the VERIFIED_FACTS returned. Quote the exact figures and "
            "cite the node ids in square brackets, e.g. [mem_ab12cd34].\n"
            "3. If recall_database_facts returns NO_VERIFIED_MEMORY, reply that the database "
            "has no verified data covering that question. Never guess or invent numbers."
        ),
        markdown=True,
    )
