import time
import logging
from collections import deque
from decimal import Decimal
from typing import Optional, Dict, Any, List, Set, Tuple
import networkx as nx

from backend.app.adapters.base import BlockchainProvider
from backend.app.domain.models import (
    Transfer,
    GraphNode,
    GraphEdge,
    InvestigationGraph,
)

logger = logging.getLogger("crypto_tracer.tracing.engine")


class GraphEngine:
    """
    Core deterministic multi-hop transaction graph traversal engine.
    Constructs a NetworkX MultiDiGraph from normalized blockchain transfer records.
    Enforces visited-address cycle protection, hop limits, and node/edge safety bounds.
    """

    def __init__(
        self,
        provider: BlockchainProvider,
        max_hops: int = 4,
        max_nodes: int = 500,
        max_edges: int = 2000,
    ):
        self.provider = provider
        self.max_hops = max_hops
        self.max_nodes = max_nodes
        self.max_edges = max_edges

    async def trace(
        self,
        source_address: str,
        asset_contract: Optional[str] = None,
    ) -> InvestigationGraph:
        start_time = time.perf_counter()
        source = source_address.strip()

        G = nx.MultiDiGraph()

        # Add root suspect wallet node
        G.add_node(
            source,
            id=source,
            address=source,
            chain="TRON",
            node_type="suspect",
            hop=0,
            total_received=Decimal(0),
            total_sent=Decimal(0),
            transaction_count=0,
        )

        visited_addresses: Set[str] = set()
        seen_tx_keys: Set[Tuple[str, str, str, int]] = set()
        queue: deque[Tuple[str, int]] = deque([(source, 0)])

        bounds_hit = False

        while queue:
            # Check safety bounds
            if G.number_of_nodes() >= self.max_nodes or G.number_of_edges() >= self.max_edges:
                logger.warning(
                    f"Traversal safety bounds reached (nodes={G.number_of_nodes()}, edges={G.number_of_edges()})"
                )
                bounds_hit = True
                break

            current_addr, current_hop = queue.popleft()

            # Boundary: Do not expand outgoing edges from max_hops
            if current_hop >= self.max_hops:
                continue

            # Cycle / visited protection: Do not re-fetch outgoing edges for visited address
            if current_addr in visited_addresses:
                continue
            visited_addresses.add(current_addr)

            try:
                # Fetch outgoing fund transfers for this address via BlockchainProvider
                page = await self.provider.get_transfers(
                    address=current_addr,
                    asset_contract=asset_contract,
                    direction="outgoing",
                )
            except Exception as e:
                logger.warning(f"Error fetching transfers for address {current_addr}: {e}")
                continue

            for tx in page.transfers:
                dest = tx.to_address.strip() if tx.to_address else ""

                # Ignore empty destinations and self-transfers
                if not dest or dest == current_addr:
                    continue

                # Transaction deduplication per edge
                tx_key = (tx.tx_hash, current_addr, dest, tx.amount_raw)
                if tx_key in seen_tx_keys:
                    continue
                seen_tx_keys.add(tx_key)

                # Edge capacity check
                if G.number_of_edges() >= self.max_edges:
                    bounds_hit = True
                    break

                next_hop = current_hop + 1

                # Node addition / capacity check
                if not G.has_node(dest):
                    if G.number_of_nodes() >= self.max_nodes:
                        bounds_hit = True
                        break

                    G.add_node(
                        dest,
                        id=dest,
                        address=dest,
                        chain=tx.chain,
                        node_type="intermediate",
                        hop=next_hop,
                        total_received=Decimal(0),
                        total_sent=Decimal(0),
                        transaction_count=0,
                    )

                    # Enqueue for next hop expansion if depth permits
                    if next_hop < self.max_hops and dest not in visited_addresses:
                        queue.append((dest, next_hop))
                else:
                    # Update minimum hop depth if discovered via shorter path
                    existing_hop = G.nodes[dest].get("hop", next_hop)
                    if next_hop < existing_hop:
                        G.nodes[dest]["hop"] = next_hop

                # Unique edge key for multigraph
                edge_id = f"{tx.tx_hash}_{current_addr}_{dest}"
                G.add_edge(
                    current_addr,
                    dest,
                    key=edge_id,
                    id=edge_id,
                    tx_hash=tx.tx_hash,
                    from_address=current_addr,
                    to_address=dest,
                    amount=tx.amount_decimal,
                    amount_raw=tx.amount_raw,
                    asset=f"{tx.chain}:{tx.asset_symbol}",
                    timestamp=tx.timestamp,
                    block_number=tx.block_number,
                    hop=next_hop,
                )

                # Update node volume & activity counters
                G.nodes[current_addr]["total_sent"] += tx.amount_decimal
                G.nodes[current_addr]["transaction_count"] += 1
                G.nodes[dest]["total_received"] += tx.amount_decimal
                G.nodes[dest]["transaction_count"] += 1

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Convert NetworkX MultiDiGraph to InvestigationGraph model
        nodes: List[GraphNode] = []
        for n, data in G.nodes(data=True):
            # If a node has no outgoing edges, mark as candidate endpoint
            node_type = data.get("node_type", "intermediate")
            if node_type != "suspect" and G.out_degree(n) == 0:
                node_type = "endpoint"

            nodes.append(
                GraphNode(
                    id=n,
                    address=data["address"],
                    chain=data.get("chain", "TRON"),
                    node_type=node_type,
                    hop=data.get("hop", 0),
                    total_received=data.get("total_received", Decimal(0)),
                    total_sent=data.get("total_sent", Decimal(0)),
                    transaction_count=data.get("transaction_count", 0),
                )
            )

        edges: List[GraphEdge] = []
        for u, v, k, data in G.edges(keys=True, data=True):
            edges.append(
                GraphEdge(
                    id=data["id"],
                    tx_hash=data["tx_hash"],
                    from_address=data["from_address"],
                    to_address=data["to_address"],
                    amount=data["amount"],
                    amount_raw=data["amount_raw"],
                    asset=data["asset"],
                    timestamp=data["timestamp"],
                    block_number=data.get("block_number"),
                    hop=data["hop"],
                )
            )

        # Compute max hop reached
        hops_reached = max((node.hop for node in nodes), default=0)

        meta = {
            "source_wallet": source,
            "max_hops_configured": self.max_hops,
            "hops_reached": hops_reached,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "visited_count": len(visited_addresses),
            "duration_ms": elapsed_ms,
            "bounds_hit": bounds_hit,
        }

        return InvestigationGraph(nodes=nodes, edges=edges, meta=meta)
