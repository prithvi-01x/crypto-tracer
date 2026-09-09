from typing import Dict, List, Tuple
from reportlab.graphics.shapes import Drawing, Rect, Circle, String, Line, Group
from reportlab.lib import colors

from backend.app.domain.models import InvestigationGraph, GraphNode, GraphEdge


def render_graph_drawing(graph: InvestigationGraph, width: float = 500, height: float = 150) -> Drawing:
    """
    Renders an investigation graph snapshot as a ReportLab Drawing flowable.
    Arranges nodes horizontally by hop depth and vertically within each hop layer.
    """
    drawing = Drawing(width, height)
    # Background card
    drawing.add(Rect(0, 0, width, height, fillColor=colors.HexColor("#0B132B"), strokeColor=colors.HexColor("#1E293B"), strokeWidth=1, rx=6, ry=6))

    # Watermark / title in top right
    drawing.add(String(width - 15, height - 16, "TRC-20 USDT Multi-Hop Traversal", textAnchor="end", fontSize=8, fontName="Helvetica-Bold", fillColor=colors.HexColor("#64748B")))

    # Group nodes by hop
    hop_map: Dict[int, List[GraphNode]] = {}
    for node in graph.nodes:
        hop_map.setdefault(node.hop, []).append(node)

    sorted_hops = sorted(hop_map.keys())
    if not sorted_hops:
        drawing.add(String(width / 2, height / 2, "No graph nodes observed", textAnchor="middle", fontSize=10, fontName="Helvetica", fillColor=colors.HexColor("#94A3B8")))
        return drawing

    max_hop = max(sorted_hops)
    hop_count = max(1, max_hop)

    padding_x = 45
    avail_w = width - (2 * padding_x)
    dx = avail_w / hop_count if hop_count > 0 else 0

    # Map address -> (cx, cy)
    coords: Dict[str, Tuple[float, float]] = {}

    for hop in sorted_hops:
        nodes_in_hop = hop_map[hop][:3]  # Limit to top 3 nodes per hop layer for clean visual representation
        n_count = len(nodes_in_hop)
        cx = padding_x + (hop * dx)

        for i, node in enumerate(nodes_in_hop):
            cy = (height / (n_count + 1)) * (i + 1)
            coords[node.address] = (cx, cy)

    # 1. Draw directed transaction edges
    for edge in graph.edges:
        if edge.pruned:
            continue
        p1 = coords.get(edge.from_address)
        p2 = coords.get(edge.to_address)
        if p1 and p2:
            x1, y1 = p1
            x2, y2 = p2

            # Edge line
            drawing.add(Line(x1, y1, x2, y2, strokeColor=colors.HexColor("#3B82F6"), strokeWidth=1.5))

            # Midpoint amount label
            mx = (x1 + x2) / 2
            my = ((y1 + y2) / 2) + 4
            amt_str = f"{float(edge.amount):,.1f} USDT"
            drawing.add(String(mx, my, amt_str, textAnchor="middle", fontSize=6.5, fontName="Helvetica-Bold", fillColor=colors.HexColor("#38BDF8")))

    # 2. Draw node badges
    box_w = 64
    box_h = 24

    for node in graph.nodes:
        pos = coords.get(node.address)
        if not pos:
            continue
        cx, cy = pos
        bx = cx - (box_w / 2)
        by = cy - (box_h / 2)

        # Color schemes by node type / hop
        if node.hop == 0:
            fill_col = colors.HexColor("#7F1D1D")  # Red for suspect
            stroke_col = colors.HexColor("#EF4444")
            role_label = "SUSPECT"
        elif node.node_type == "endpoint":
            fill_col = colors.HexColor("#064E3B")  # Emerald for VASP/endpoint
            stroke_col = colors.HexColor("#10B981")
            role_label = "VASP DEST"
        else:
            fill_col = colors.HexColor("#312E81")  # Indigo for intermediate
            stroke_col = colors.HexColor("#6366F1")
            role_label = f"HOP {node.hop}"

        drawing.add(Rect(bx, by, box_w, box_h, fillColor=fill_col, strokeColor=stroke_col, strokeWidth=1.2, rx=4, ry=4))

        # Text labels
        abbr_addr = f"{node.address[:4]}...{node.address[-3:]}"
        drawing.add(String(cx, cy + 2, role_label, textAnchor="middle", fontSize=6, fontName="Helvetica-Bold", fillColor=colors.HexColor("#E2E8F0")))
        drawing.add(String(cx, cy - 7, abbr_addr, textAnchor="middle", fontSize=6.5, fontName="Courier", fillColor=colors.HexColor("#F8FAFC")))

    return drawing
