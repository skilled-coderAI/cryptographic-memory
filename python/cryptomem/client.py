from __future__ import annotations

import uuid
from datetime import datetime, timezone

from cryptomem.adapters.base import LLMAdapter
from cryptomem.adapters.mock_adapter import MockAdapter
from cryptomem.config import Settings
from cryptomem.crypto.hashing import sha256
from cryptomem.crypto.keys import build_signer
from cryptomem.crypto.merkle import merkle_proof, merkle_root, verify_proof
from cryptomem.crypto.signer import Signer
from cryptomem.efficiency.budgeter import fit_to_budget
from cryptomem.efficiency.cache import SemanticCache
from cryptomem.efficiency.compressor import compress_heuristic
from cryptomem.efficiency.deduper import dedupe
from cryptomem.embeddings.base import Embedder, cosine_similarity
from cryptomem.embeddings.stub import StubEmbedder
from cryptomem.models import (
    Contradiction,
    CryptoEnvelope,
    MemoryNode,
    Relationship,
    ScoredNode,
)
from cryptomem.proactive.planner import Planner
from cryptomem.proactive.triggers import TriggerEngine
from cryptomem.proactive.writeback import WriteBack
from cryptomem.retrieval.retriever import Retriever
from cryptomem.store.base import MemoryStore
from cryptomem.store.sqlite_store import SqliteStore
from cryptomem.verification.citations import Citer
from cryptomem.verification.cove import ChainOfVerification
from cryptomem.verification.entropy import SemanticEntropy
from cryptomem.verification.faithfulness import FaithfulnessChecker
from cryptomem.verification.grounding import GroundingGate, render_context

ABSTAIN = "I cannot answer that from verified memory."


class MemoryClient:
    """High-level verifiable memory: archive, query, verify, traverse, ground.

    Every fact is SHA-256 hashed and Ed25519 signed at write time. At read time
    each node is re-verified; tampered or unsigned facts are dropped and the
    agent abstains rather than guessing. Retrieval runs a
    retrieve -> dedupe -> rank -> budget -> (compress) -> ground pipeline.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        store: MemoryStore | None = None,
        signer: Signer | None = None,
        embedder: Embedder | None = None,
    ):
        self.settings = settings or Settings()
        self.signer = signer or build_signer(self.settings)
        self.store = store or self._build_store()
        self.embedder = embedder or StubEmbedder()
        self.retriever = Retriever(
            store=self.store,
            embedder=self.embedder,
            verify=self.verify,
            require_verification=self.settings.require_verification,
        )
        self.gate = GroundingGate(min_confidence=self.settings.grounding_min_confidence)
        self.cache = SemanticCache()
        self.citer = Citer(self.embedder, min_support=self.settings.citation_min_support)
        self.faithfulness = FaithfulnessChecker(
            self.embedder, threshold=self.settings.faithfulness_threshold
        )
        self.entropy = SemanticEntropy(
            self.embedder, cluster_threshold=self.settings.entropy_cluster_threshold
        )

    def _build_store(self) -> MemoryStore:
        """Select the store from ``settings.mode``; fall back to SQLite offline.

        ``mode="remote"`` (with a ``backend_url``) uses a :class:`RemoteStore`,
        but if the backend fails its health check at init the client degrades
        gracefully to a local SQLite store so edge devices keep working.
        """
        mode = self.settings.mode.lower()
        if mode == "neo4j":
            from cryptomem.store.neo4j_store import Neo4jStore

            return Neo4jStore(
                uri=self.settings.neo4j_uri,
                user=self.settings.neo4j_user,
                password=self.settings.neo4j_password,
                database=self.settings.neo4j_database,
            )
        if mode == "remote" and self.settings.backend_url:
            from cryptomem.store.remote_store import RemoteStore

            remote = RemoteStore(self.settings.backend_url, self.settings.backend_api_key)
            if remote.healthz():
                return remote
            return SqliteStore(self.settings.sqlite_path)
        return SqliteStore(self.settings.sqlite_path)

    def archive(
        self,
        entity: str,
        content: str,
        relationships: list[Relationship] | None = None,
        metadata: dict | None = None,
        node_id: str | None = None,
    ) -> MemoryNode:
        """Sign and persist a new memory node, returning the stored node."""
        rels = relationships or []
        meta = dict(metadata or {})
        meta.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        nid = node_id or f"mem_{uuid.uuid4().hex[:12]}"

        unsigned = MemoryNode(
            node_id=nid,
            entity=entity,
            content=content,
            relationships=rels,
            metadata=meta,
        )
        return self._seal(unsigned)

    def _seal(self, node: MemoryNode) -> MemoryNode:
        """Hash, Merkle-anchor, sign, embed, and persist ``node`` in place."""
        node.crypto = None
        node.embedding = None
        digest = sha256(node.model_dump())
        existing = [
            n.crypto.hash
            for n in self.store.all()
            if n.crypto is not None and n.node_id != node.node_id
        ]
        root = merkle_root([*existing, digest])
        node.embedding = self.embedder.embed(f"{node.entity} {node.content}")
        node.crypto = CryptoEnvelope(
            hash=digest,
            signature=self.signer.sign(digest),
            public_key_ref=self.signer.public_key_hex,
            merkle_root=root,
        )
        self.store.write(node)
        return node

    def verify(self, node: MemoryNode) -> bool:
        """Re-derive the hash and check the signature; ``False`` on any tamper."""
        if node.crypto is None:
            return False
        recomputed = sha256(node.model_dump())
        if recomputed != node.crypto.hash:
            return False
        return Signer.verify(node.crypto.public_key_ref, node.crypto.hash, node.crypto.signature)

    def query(self, text: str, top_k: int = 5, depth: int = 0) -> list[ScoredNode]:
        """Retrieve verified nodes ranked by similarity and graph distance."""
        return self.retriever.retrieve(text, top_k=top_k, depth=depth)

    def neighbors(self, node_id: str, depth: int = 1) -> list[MemoryNode]:
        """Return verified neighbours reachable within ``depth`` hops."""
        return [n for n in self.store.neighbors(node_id, depth=depth) if self.verify(n)]

    def _ledger_leaves(self) -> tuple[list[MemoryNode], list[str]]:
        nodes = sorted(
            (n for n in self.store.all() if n.crypto is not None), key=lambda n: n.node_id
        )
        return nodes, [n.crypto.hash for n in nodes if n.crypto is not None]

    def ledger_root(self) -> str | None:
        """Merkle root over every stored node's hash (current ledger anchor)."""
        return merkle_root(self._ledger_leaves()[1])

    def proof(self, node_id: str) -> dict | None:
        """Return a verifiable Merkle inclusion proof for a node.

        Includes the node's write-time anchor plus an audit path against the
        current ledger root, so an auditor can confirm membership offline via
        :func:`verify_proof` without trusting this process.
        """
        node = self.store.get(node_id)
        if node is None or node.crypto is None:
            return None
        nodes, leaves = self._ledger_leaves()
        index = next((i for i, n in enumerate(nodes) if n.node_id == node_id), -1)
        path = merkle_proof(leaves, index) if index >= 0 else []
        root = merkle_root(leaves)
        included = root is not None and verify_proof(node.crypto.hash, path, root)
        return {
            "node_id": node.node_id,
            "leaf_hash": node.crypto.hash,
            "merkle_root": node.crypto.merkle_root,
            "ledger_root": root,
            "proof": [{"sibling": sibling, "position": pos} for sibling, pos in path],
            "included": included,
            "verified": self.verify(node),
        }

    def contradictions(self) -> list[Contradiction]:
        """Surface same-entity nodes whose content diverges (contradiction radar)."""
        by_entity: dict[str, list[MemoryNode]] = {}
        for node in self.store.all():
            if self.verify(node):
                by_entity.setdefault(node.entity, []).append(node)

        found: list[Contradiction] = []
        threshold = self.settings.contradiction_threshold
        for entity, nodes in by_entity.items():
            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    left, right = nodes[i], nodes[j]
                    if left.embedding is None or right.embedding is None:
                        continue
                    sim = cosine_similarity(left.embedding, right.embedding)
                    if sim < threshold:
                        found.append(
                            Contradiction(
                                entity=entity,
                                left_id=left.node_id,
                                right_id=right.node_id,
                                similarity=round(sim, 4),
                            )
                        )
        return found

    def _ground(self, question: str, top_k: int, depth: int, compress: bool) -> list[ScoredNode]:
        scored = dedupe(self.query(question, top_k=top_k, depth=depth))
        admitted, grounded = self.gate.admit(scored)
        if not grounded:
            return []
        admitted = fit_to_budget(admitted, self.settings.max_context_tokens)
        if compress:
            for s in admitted:
                s.node.content = compress_heuristic(s.node.content)
        return admitted

    def respond(
        self,
        question: str,
        adapter: LLMAdapter | None = None,
        top_k: int = 5,
        depth: int = 0,
        compress: bool = False,
    ) -> tuple[str, dict]:
        """Answer plus a provenance block (injected nodes, verification, root)."""
        admitted = self._ground(question, top_k, depth, compress)
        if not admitted:
            return ABSTAIN, {"injected_nodes": [], "verified": False, "merkle_root": None}

        adapter = adapter or MockAdapter()
        prompt = (
            "Answer using ONLY the verified facts below. "
            "If they do not cover the question, say you cannot answer.\n\n"
            f"Verified facts:\n{render_context(admitted)}\n\nQuestion: {question}"
        )
        text = adapter.complete(prompt)
        head_crypto = admitted[0].node.crypto
        provenance: dict = {
            "injected_nodes": [s.node.node_id for s in admitted],
            "verified": all(s.verified for s in admitted),
            "merkle_root": head_crypto.merkle_root if head_crypto else None,
        }
        if self.settings.enable_citations:
            text, citations = self.citer.annotate(text, admitted)
            provenance["citations"] = citations
        if self.settings.enable_faithfulness:
            score, _ = self.faithfulness.score(text, admitted)
            provenance["faithfulness"] = score
            provenance["faithful"] = score >= self.settings.faithfulness_threshold
        if self.settings.enable_proactive:
            provenance["proactive_suggestions"] = self.suggest(
                [s.node for s in admitted], limit=self.settings.proactive_suggestions
            )
        if self.settings.enable_writeback:
            provenance["staged_nodes"] = [n.node_id for n in self.stage_facts(text)]
        return text, provenance

    def answer(
        self,
        question: str,
        adapter: LLMAdapter | None = None,
        top_k: int = 5,
        depth: int = 0,
        compress: bool = False,
        use_cache: bool = True,
    ) -> str:
        """Answer strictly from verified memory, or abstain if none is found.

        Pipeline: retrieve -> dedupe -> ground -> token-budget -> (compress) ->
        adapter, with a semantic answer cache in front.
        """
        query_vec = self.embedder.embed(question)
        if use_cache:
            cached = self.cache.get(query_vec)
            if cached is not None:
                return cached

        text, _ = self.respond(
            question, adapter=adapter, top_k=top_k, depth=depth, compress=compress
        )
        if use_cache:
            self.cache.put(query_vec, text)
        return text

    def confidence(
        self,
        question: str,
        adapter: LLMAdapter | None = None,
        samples: int | None = None,
        top_k: int = 5,
        depth: int = 0,
    ) -> dict:
        """Estimate epistemic confidence via semantic entropy over samples.

        Grounds the question once, then samples the adapter repeatedly and
        clusters the answers by meaning: agreement -> high confidence, scatter
        -> low. Returns ``{clusters, entropy, confidence}``; abstains (zero
        confidence) when nothing grounds.
        """
        admitted = self._ground(question, top_k=top_k, depth=depth, compress=False)
        if not admitted:
            return {"clusters": 0, "entropy": 1.0, "confidence": 0.0}
        adapter = adapter or MockAdapter()
        prompt = (
            "Answer using ONLY the verified facts below.\n\n"
            f"Verified facts:\n{render_context(admitted)}\n\nQuestion: {question}"
        )
        n = samples if samples is not None else self.settings.entropy_samples
        return self.entropy.estimate(prompt, adapter, samples=n)

    def verify_answer(self, draft: str, top_k: int = 3) -> dict:
        """Re-check a draft answer claim-by-claim against verified memory (CoVe)."""
        cove = ChainOfVerification(self, self.embedder, self.settings.faithfulness_threshold)
        return cove.verify(draft, top_k=top_k)

    def suggest(self, injected: list[MemoryNode], limit: int | None = None) -> list[dict]:
        """Pre-stage adjacent verified facts for the likely next turn (planner)."""
        n = limit if limit is not None else self.settings.proactive_suggestions
        return Planner(self.store, self.verify).suggest(injected, limit=n)

    def triggers(self) -> list[dict]:
        """Evaluate proactive triggers (reconcile / refresh / link-gap)."""
        return TriggerEngine(self).evaluate()

    def stage_facts(self, text: str, entity: str | None = None) -> list[MemoryNode]:
        """Extract facts from ``text`` and stage them as signed pending nodes."""
        return WriteBack(self).stage(text, entity=entity)

    def pending(self) -> list[MemoryNode]:
        """Return verified nodes awaiting confirmation (``status="pending"``)."""
        return [
            n for n in self.store.all() if self.verify(n) and n.metadata.get("status") == "pending"
        ]

    def confirm(self, node_id: str) -> MemoryNode | None:
        """Promote a pending node to ``confirmed`` and re-sign it."""
        node = self.store.get(node_id)
        if node is None or node.metadata.get("status") != "pending":
            return None
        node.metadata["status"] = "confirmed"
        return self._seal(node)
