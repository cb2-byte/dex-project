"""Persistent, evidence-backed operator relationship graph.

Only explicit on-chain observations are added as relationships. In particular,
this module never infers a funding link from shared timing or token behavior.
"""
import hashlib
import json
import os
import tempfile
import threading
from collections import deque
from typing import Any, Dict, Iterable, Optional


class OperatorIntelligenceGraph:
    """Small JSON-backed graph for wallet, launch, and outcome evidence."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, "r") as handle:
                self.data = json.load(handle)
        except FileNotFoundError:
            self.data = {"schema_version": 1, "nodes": {}, "edges": {}}
        self.data.setdefault("schema_version", 1)
        self.data.setdefault("nodes", {})
        self.data.setdefault("edges", {})

    @staticmethod
    def wallet_id(address: str) -> str:
        # Solana public keys are case-sensitive base58 strings.
        return f"wallet:{address.strip()}"

    @staticmethod
    def launch_id(chain: str, mint: str) -> str:
        chain = chain.strip().lower()
        normalized_mint = mint.strip() if chain == "solana" else mint.strip().lower()
        return f"launch:{chain}:{normalized_mint}"

    def _save(self) -> None:
        directory = os.path.dirname(self.path)
        fd, temp_path = tempfile.mkstemp(prefix=".operator-graph-", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(self.data, handle, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def _node(self, node_id: str, kind: str, attributes: Dict[str, Any]) -> None:
        node = self.data["nodes"].setdefault(node_id, {"id": node_id, "kind": kind})
        node.update({key: value for key, value in attributes.items() if value is not None})

    def _edge(self, source: str, target: str, relationship: str,
              event_key: str, evidence: Dict[str, Any]) -> None:
        edge_identity = "\0".join((source, target, relationship, event_key))
        edge_id = hashlib.sha256(edge_identity.encode()).hexdigest()[:24]
        self.data["edges"].setdefault(edge_id, {
            "id": edge_id,
            "source": source,
            "target": target,
            "relationship": relationship,
            "event_key": event_key,
            "evidence": evidence,
        })

    def record_launch(self, chain: str, mint: str, creator: str,
                      detection_id: str, evidence: Dict[str, Any],
                      funding_sources: Optional[Iterable[Any]] = None) -> None:
        chain = chain.strip().lower()
        launch = self.launch_id(chain, mint)
        with self._lock:
            self._node(launch, "launch", {"chain": chain, "mint": mint,
                                           "creator": creator or None,
                                           "name": evidence.get("name"),
                                           "symbol": evidence.get("symbol")})
            if creator:
                operator = self.wallet_id(creator)
                self._node(operator, "wallet", {"address": creator, "chain": chain,
                                                 "role": "creator"})
                self._edge(operator, launch, "deployed", detection_id, evidence)

                for source in funding_sources or []:
                    if isinstance(source, dict):
                        funder = source.get("address") or source.get("wallet")
                        source_evidence = source.get("evidence", {})
                    else:
                        funder = str(source) if source else ""
                        source_evidence = {}
                    if not funder or funder.strip() == creator.strip():
                        continue
                    funder_id = self.wallet_id(funder)
                    self._node(funder_id, "wallet", {"address": funder, "chain": chain,
                                                       "role": "funding_source"})
                    self._edge(funder_id, operator, "funded", str(source_evidence.get("signature") or detection_id),
                               {**source_evidence, "observed_for_detection": detection_id})
            self._save()

    def record_outcome(self, chain: str, mint: str, detection_id: str,
                       outcome: str, timestamp: float, details: Optional[Dict[str, Any]] = None) -> None:
        launch = self.launch_id(chain, mint)
        chain_key = chain.strip().lower()
        mint_key = mint.strip() if chain_key == "solana" else mint.strip().lower()
        outcome_id = f"outcome:{chain_key}:{mint_key}:{detection_id}:{outcome}"
        with self._lock:
            self._node(launch, "launch", {"chain": chain.strip().lower(), "mint": mint})
            self._node(outcome_id, "outcome", {"value": outcome, "timestamp": timestamp})
            self._edge(launch, outcome_id, "outcome", f"{detection_id}:{outcome}",
                       {"detection_id": detection_id, "outcome": outcome,
                        "timestamp": timestamp, "details": details or {}})
            self._save()

    def get_subgraph(self, start_node: str, depth: int = 2, limit: int = 500) -> Dict[str, Any]:
        """Return the evidence-backed neighborhood reachable from a node."""
        depth = max(0, min(int(depth), 8))
        limit = max(1, min(int(limit), 5000))
        with self._lock:
            distances = {start_node: 0}
            queue = deque([start_node])
            selected_edges = {}
            while queue and len(selected_edges) < limit:
                current = queue.popleft()
                current_depth = distances[current]
                if current_depth >= depth:
                    continue
                for edge_id, edge in self.data["edges"].items():
                    if edge["source"] != current and edge["target"] != current:
                        continue
                    selected_edges[edge_id] = edge
                    neighbor = edge["target"] if edge["source"] == current else edge["source"]
                    if neighbor not in distances:
                        distances[neighbor] = current_depth + 1
                        queue.append(neighbor)
                    if len(selected_edges) >= limit:
                        break
            node_ids = set(distances)
            return {
                "start_node": start_node,
                "nodes": [self.data["nodes"][node_id] for node_id in node_ids if node_id in self.data["nodes"]],
                "edges": list(selected_edges.values()),
            }
