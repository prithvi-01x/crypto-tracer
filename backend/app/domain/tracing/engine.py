import time
import logging
from collections import deque
from decimal import Decimal
from typing import Optional, Dict, Any, List, Set, Tuple
import networkx as nx

from backend.app.adapters.base import (
    BlockchainProvider,
    BlockchainProviderError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    InvalidAddressError,
)
from backend.app.domain.attribution.registry import VASPRegistry, default_registry
from backend.app.domain.boundaries import (
    BoundaryCode,
    TraceBoundaryInfo,
    get_default_investigator_explanation,
)
from backend.app.domain.models import (
    Transfer,
    GraphNode,
    GraphEdge,
    PrunedRecord,
    InvestigationGraph,
)
from backend.app.domain.tracing.pruner import RelevancePruner

logger = logging.getLogger("crypto_tracer.tracing.engine")


class GraphEngine:
    """
    Core deterministic multi-hop transaction graph traversal engine.
    Constructs a NetworkX MultiDiGraph from normalized blockchain transfer records.
    Enforces visited-address cycle protection, hop limits, node/edge safety bounds,
    relevance pruning, mixer/bridge boundary detection, and partial trace preservation.
    """

    def __init__(
        self,
        provider: BlockchainProvider,
        max_hops: int = 4,
        max_nodes: int = 500,
        max_edges: int = 2000,
        min_relevant_usd: Decimal = Decimal("1.00"),
        max_branches_per_node: int = 20,
        target_asset: str = "USDT",
        registry: Optional[VASPRegistry] = None,
    ):
        self.provider = provider
        self.max_hops = max_hops
        self.max_nodes = max_nodes
        self.max_edges = max_edges
        self.min_relevant_usd = Decimal(str(min_relevant_usd))
        self.max_branches_per_node = max_branches_per_node
        self.target_asset = target_asset
        self.registry = registry or default_registry
        self.pruner = RelevancePruner(
            min_relevant_usd=self.min_relevant_usd,
            max_branches_per_node=self.max_branches_per_node,
            target_asset=self.target_asset,
        )

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

        raw_transfers_fetched_count = 0
        traversal_relevant_transfers_count = 0
        all_pruned_records: List[PrunedRecord] = []
        bounds_hit = False
        is_partial = False
        max_hops_encountered = False

        # Boundary tracking details
        boundary_code: Optional[BoundaryCode] = None
        boundary_addr: Optional[str] = None
        boundary_hop: Optional[int] = None
        boundary_entity: Optional[str] = None
        boundary_limit: Optional[str] = None
        technical_details: Optional[str] = None

        while queue:
            # Check safety bounds
            if G.number_of_nodes() >= self.max_nodes:
                logger.warning(
                    f"Traversal node limit reached (nodes={G.number_of_nodes()})"
                )
                bounds_hit = True
                is_partial = True
                if not boundary_code:
                    boundary_code = BoundaryCode.MAX_NODES_REACHED
                    boundary_limit = f"{self.max_nodes} nodes"
                    technical_details = f"Node count limit ({self.max_nodes}) exceeded"
                break

            if G.number_of_edges() >= self.max_edges:
                logger.warning(
                    f"Traversal edge limit reached (edges={G.number_of_edges()})"
                )
                bounds_hit = True
                is_partial = True
                if not boundary_code:
                    boundary_code = BoundaryCode.MAX_EDGES_REACHED
                    boundary_limit = f"{self.max_edges} edges"
                    technical_details = f"Edge count limit ({self.max_edges}) exceeded"
                break

            current_addr, current_hop = queue.popleft()

            # Boundary: Do not expand outgoing edges beyond max_hops
            if current_hop >= self.max_hops:
                max_hops_encountered = True
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
            except ProviderTimeoutError as e:
                if current_hop == 0:
                    # Root query failure: unrecoverable
                    raise
                logger.warning(f"Provider timeout at hop {current_hop} for {current_addr}: {e}")
                bounds_hit = True
                is_partial = True
                boundary_code = BoundaryCode.PROVIDER_TIMEOUT
                boundary_addr = current_addr
                boundary_hop = current_hop
                technical_details = str(e)
                break
            except ProviderRateLimitError as e:
                if current_hop == 0:
                    # Root query rate-limited: unrecoverable
                    raise
                logger.warning(f"Provider rate limit at hop {current_hop} for {current_addr}: {e}")
                bounds_hit = True
                is_partial = True
                boundary_code = BoundaryCode.PROVIDER_RATE_LIMITED
                boundary_addr = current_addr
                boundary_hop = current_hop
                technical_details = str(e)
                break
            except Exception as e:
                logger.warning(f"Error fetching transfers for address {current_addr}: {e}")
                if current_hop == 0:
                    raise
                continue

            raw_transfers = page.transfers
            raw_transfers_fetched_count += len(raw_transfers)

            # Filter candidate transfers: ignore empty destinations and self-transfers
            candidate_transfers: List[Transfer] = []
            for tx in raw_transfers:
                dest = tx.to_address.strip() if tx.to_address else ""
                if not dest or dest == current_addr:
                    continue
                candidate_transfers.append(tx)

            # Partition candidate transfers using RelevancePruner
            relevant_txs, pruned_records = self.pruner.partition_transfers(
                transfers=candidate_transfers,
                current_hop=current_hop,
            )
            traversal_relevant_transfers_count += len(relevant_txs)
            all_pruned_records.extend(pruned_records)

            for tx in relevant_txs:
                dest = tx.to_address.strip()

                # Transaction deduplication per edge
                tx_key = (tx.tx_hash, current_addr, dest, tx.amount_raw)
                if tx_key in seen_tx_keys:
                    continue
                seen_tx_keys.add(tx_key)

                # Edge capacity check
                if G.number_of_edges() >= self.max_edges:
                    bounds_hit = True
                    is_partial = True
                    if not boundary_code:
                        boundary_code = BoundaryCode.MAX_EDGES_REACHED
                        boundary_limit = f"{self.max_edges} edges"
                    break

                next_hop = current_hop + 1

                # Node addition / capacity check
                if not G.has_node(dest):
                    if G.number_of_nodes() >= self.max_nodes:
                        bounds_hit = True
                        is_partial = True
                        if not boundary_code:
                            boundary_code = BoundaryCode.MAX_NODES_REACHED
                            boundary_limit = f"{self.max_nodes} nodes"
                        break

                    # Determine initial node type based on VASP / Mixer / Bridge registry
                    if self.registry.is_mixer(dest):
                        initial_type = "mixer"
                    elif self.registry.is_bridge(dest):
                        initial_type = "bridge"
                    elif self.registry.is_known_vasp(dest):
                        initial_type = "vasp"
                    else:
                        initial_type = "intermediate"

                    G.add_node(
                        dest,
                        id=dest,
                        address=dest,
                        chain=tx.chain,
                        node_type=initial_type,
                        hop=next_hop,
                        total_received=Decimal(0),
                        total_sent=Decimal(0),
                        transaction_count=0,
                    )

                    # Boundary Check 1: Mixer / High-Risk Obfuscation
                    if initial_type == "mixer":
                        mixer_entry = self.registry.get(dest)
                        mixer_name = mixer_entry.entity_name if mixer_entry else "Privacy Mixer"
                        logger.info(f"Mixer boundary reached at {dest} ({mixer_name}). Traversal halted from this node.")
                        boundary_code = BoundaryCode.MIXER_BOUNDARY
                        boundary_addr = dest
                        boundary_hop = next_hop
                        boundary_entity = mixer_name
                        is_partial = True
                        # Do NOT enqueue mixer node for outgoing expansion

                    # Boundary Check 2: Cross-Chain Bridge Gateway
                    elif initial_type == "bridge":
                        bridge_entry = self.registry.get(dest)
                        bridge_name = bridge_entry.entity_name if bridge_entry else "Bridge Gateway"
                        logger.info(f"Cross-chain bridge boundary reached at {dest} ({bridge_name}). Traversal halted from this node.")
                        boundary_code = BoundaryCode.BRIDGE_BOUNDARY
                        boundary_addr = dest
                        boundary_hop = next_hop
                        boundary_entity = bridge_name
                        is_partial = True
                        # Do NOT enqueue bridge node for single-chain outgoing expansion

                    # Enqueue standard intermediate wallet for next hop expansion if depth permits
                    elif next_hop < self.max_hops and dest not in visited_addresses:
                        queue.append((dest, next_hop))
                    elif next_hop >= self.max_hops:
                        max_hops_encountered = True
                else:
                    # Deterministic minimum hop distance
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
                    source=tx.source,
                    relevance_score=Decimal("1.0"),
                    pruned=False,
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
            node_type = data.get("node_type", "intermediate")
            # Preserve mixer, bridge, and suspect types; endpoints have out_degree 0
            if node_type not in ("suspect", "mixer", "bridge") and G.out_degree(n) == 0:
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
                    source=data.get("source", "trongrid"),
                    relevance_score=data.get("relevance_score", Decimal("1.0")),
                    pruned=data.get("pruned", False),
                )
            )

        # Compute max hop reached
        hops_reached = max((node.hop for node in nodes), default=0)

        # Classify final operational outcome / boundary if none set during traversal
        if len(edges) == 0:
            if raw_transfers_fetched_count == 0:
                boundary_code = BoundaryCode.NO_TRANSFERS_FOUND
                boundary_addr = source
                is_partial = False
            else:
                boundary_code = BoundaryCode.NO_RELEVANT_PATH
                boundary_addr = source
                is_partial = False
        elif boundary_code is None:
            if max_hops_encountered or hops_reached >= self.max_hops:
                boundary_code = BoundaryCode.MAX_HOPS_REACHED
                boundary_limit = str(self.max_hops)
                is_partial = False

        boundary_info: Optional[TraceBoundaryInfo] = None
        if boundary_code:
            explanation = get_default_investigator_explanation(
                boundary_code,
                address=boundary_addr or source,
                hop=boundary_hop or hops_reached,
                entity_name=boundary_entity or "",
                limit=boundary_limit or "",
            )
            cat = "TRAVERSAL_LIMIT"
            if boundary_code in (BoundaryCode.PROVIDER_TIMEOUT, BoundaryCode.PROVIDER_RATE_LIMITED):
                cat = "PROVIDER_ERROR"
            elif boundary_code in (BoundaryCode.MIXER_BOUNDARY, BoundaryCode.BRIDGE_BOUNDARY):
                cat = "OBFUSCATION"
            elif boundary_code in (BoundaryCode.INVALID_ADDRESS, BoundaryCode.UNSUPPORTED_CHAIN, BoundaryCode.UNSUPPORTED_ASSET):
                cat = "INPUT_ERROR"

            boundary_info = TraceBoundaryInfo(
                code=boundary_code,
                category=cat,
                is_partial=is_partial,
                terminal=True,
                address=boundary_addr or source,
                hop=boundary_hop or hops_reached,
                entity_name=boundary_entity,
                technical_details=technical_details,
                investigator_explanation=explanation,
            )

        meta = {
            "source_wallet": source,
            "max_hops": self.max_hops,
            "max_hops_configured": self.max_hops,
            "hops_reached": hops_reached,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "visited_count": len(visited_addresses),
            "raw_transfers_fetched_count": raw_transfers_fetched_count,
            "traversal_relevant_transfers_count": traversal_relevant_transfers_count,
            "edges_included_count": len(edges),
            "pruned_transfers_count": len(all_pruned_records),
            "pruned_nodes": len(all_pruned_records),
            "min_relevant_usd": float(self.min_relevant_usd),
            "max_branches_per_node": self.max_branches_per_node,
            "duration_ms": elapsed_ms,
            "bounds_hit": bounds_hit,
            "is_partial": is_partial,
            "boundary_reached": boundary_code.value if boundary_code else None,
            "investigator_explanation": boundary_info.investigator_explanation if boundary_info else None,
        }

        return InvestigationGraph(
            nodes=nodes,
            edges=edges,
            pruned_records=all_pruned_records,
            meta=meta,
            boundary=boundary_info.model_dump() if boundary_info else None,
        )
