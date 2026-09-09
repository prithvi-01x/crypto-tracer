import React, { useEffect, useRef, useState, useCallback } from 'react';
import cytoscape, { type Core, type EventObject } from 'cytoscape';
import { 
  ZoomIn, 
  ZoomOut, 
  Maximize2, 
  RotateCcw, 
  Crosshair, 
  Tag, 
  Info, 
  Layers
} from 'lucide-react';
import type { InvestigationGraph, GraphNode, GraphEdge } from '../../types/graph';

interface InvestigationGraphCanvasProps {
  graph: InvestigationGraph | null;
  onSelectNode: (node: GraphNode | null) => void;
  onSelectEdge: (edge: GraphEdge | null) => void;
  selectedNode: GraphNode | null;
  selectedEdge: GraphEdge | null;
}

export const InvestigationGraphCanvas: React.FC<InvestigationGraphCanvasProps> = ({
  graph,
  onSelectNode,
  onSelectEdge,
  selectedNode,
  selectedEdge,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [showLabels, setShowLabels] = useState(true);

  // Helper to format short address
  const shortAddr = (addr: string) => {
    if (!addr) return '';
    return `${addr.slice(0, 5)}...${addr.slice(-4)}`;
  };

  // Helper to format currency
  const formatAmount = (val: number | string) => {
    const num = typeof val === 'string' ? parseFloat(val) : val;
    if (isNaN(num)) return `$${val}`;
    if (num >= 1000) {
      return `$${(num / 1000).toFixed(1)}k`;
    }
    return `$${num.toFixed(2)}`;
  };

  // Highlight path from root suspect to given target node
  const highlightPathToRoot = useCallback((targetId: string) => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.elements().removeClass('highlighted faded');

    const targetNode = cy.getElementById(targetId);
    if (!targetNode || targetNode.length === 0) return;

    // Find root suspect node
    const rootNode = cy.nodes('[type = "suspect"]');
    if (rootNode.length === 0) {
      targetNode.addClass('highlighted');
      return;
    }

    // Use Dijkstra's algorithm for shortest directed path from root to target
    const dijkstra = cy.elements().dijkstra({
      root: rootNode,
      directed: true,
      weight: () => 1,
    });

    const pathToTarget = dijkstra.pathTo(targetNode);

    if (pathToTarget && pathToTarget.length > 0) {
      cy.elements().addClass('faded');
      pathToTarget.removeClass('faded').addClass('highlighted');
    } else {
      // If no direct forward path, at least highlight the selected node and its edges
      cy.elements().addClass('faded');
      targetNode.removeClass('faded').addClass('highlighted');
      targetNode.connectedEdges().removeClass('faded').addClass('highlighted');
    }
  }, []);

  // Initialize and update Cytoscape
  useEffect(() => {
    if (!containerRef.current || !graph) return;

    // Convert domain nodes to Cytoscape format
    const elements: cytoscape.ElementDefinition[] = [];

    // Add Nodes
    graph.nodes.forEach((n) => {
      let labelText = `${shortAddr(n.address)}`;
      if (n.node_type === 'suspect') {
        labelText = `🚨 SUSPECT\n${shortAddr(n.address)}`;
      } else if (n.node_type === 'endpoint') {
        labelText = `🎯 ENDPOINT\n${shortAddr(n.address)}`;
      } else {
        labelText = `Hop ${n.hop}\n${shortAddr(n.address)}`;
      }

      elements.push({
        group: 'nodes',
        data: {
          id: n.address,
          label: labelText,
          type: n.node_type,
          hop: n.hop,
          rawNode: n,
        },
      });
    });

    // Add Edges
    graph.edges.forEach((e) => {
      const edgeLabel = `${formatAmount(e.amount)}`;
      elements.push({
        group: 'edges',
        data: {
          id: e.id,
          source: e.from_address,
          target: e.to_address,
          amount: e.amount,
          label: edgeLabel,
          hop: e.hop,
          rawEdge: e,
        },
      });
    });

    // Destroy existing instance before recreation
    if (cyRef.current) {
      cyRef.current.destroy();
    }

    const rootSuspectAddress = graph.meta.source_wallet || graph.nodes.find(n => n.node_type === 'suspect')?.address;

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      boxSelectionEnabled: false,
      autounselectify: false,
      style: [
        // Node Base
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'color': '#e2e8f0',
            'font-size': '10px',
            'font-family': 'ui-monospace, monospace',
            'font-weight': 'bold',
            'text-wrap': 'wrap',
            'text-valign': 'bottom',
            'text-margin-y': 6,
            'text-background-color': '#090d16',
            'text-background-opacity': 0.85,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
            'transition-property': 'background-color, line-color, target-arrow-color, opacity, width, height, border-color, border-width',
            'transition-duration': 0.25,
            'border-width': 2,
            'background-color': '#1e293b',
            'border-color': '#475569',
            'width': 36,
            'height': 36,
          },
        },
        // Suspect Root Node
        {
          selector: 'node[type = "suspect"]',
          style: {
            'background-color': '#7f1d1d',
            'border-color': '#ef4444',
            'border-width': 3.5,
            'width': 46,
            'height': 46,
          },
        },
        // Intermediate Node
        {
          selector: 'node[type = "intermediate"]',
          style: {
            'background-color': '#0369a1',
            'border-color': '#38bdf8',
            'border-width': 2.5,
            'width': 36,
            'height': 36,
          },
        },
        // Endpoint Node
        {
          selector: 'node[type = "endpoint"]',
          style: {
            'background-color': '#064e3b',
            'border-color': '#10b981',
            'border-width': 3,
            'width': 40,
            'height': 40,
          },
        },
        // Edges Base
        {
          selector: 'edge',
          style: {
            'curve-style': 'bezier',
            'target-arrow-shape': 'triangle',
            'target-arrow-color': '#64748b',
            'line-color': '#475569',
            'width': 2.5,
            'arrow-scale': 1.1,
            'label': 'data(label)',
            'font-size': '10px',
            'font-family': 'ui-monospace, monospace',
            'font-weight': 'bold',
            'color': '#38bdf8',
            'text-background-color': '#090d16',
            'text-background-opacity': 0.9,
            'text-background-padding': '2px',
            'text-background-shape': 'roundrectangle',
            'text-rotation': 'autorotate',
            'text-margin-y': -8,
            'transition-property': 'line-color, target-arrow-color, opacity, width',
            'transition-duration': 0.25,
          },
        },
        // Selected element styling
        {
          selector: 'node:selected',
          style: {
            'border-color': '#f59e0b',
            'border-width': 4,
            'background-color': '#b45309',
          },
        },
        {
          selector: 'edge:selected',
          style: {
            'line-color': '#f59e0b',
            'target-arrow-color': '#f59e0b',
            'width': 4.5,
          },
        },
        // Highlighted path elements
        {
          selector: 'node.highlighted',
          style: {
            'border-color': '#38bdf8',
            'border-width': 4,
            'opacity': 1.0,
            'z-index': 999,
          },
        },
        {
          selector: 'edge.highlighted',
          style: {
            'line-color': '#38bdf8',
            'target-arrow-color': '#38bdf8',
            'width': 4.5,
            'opacity': 1.0,
            'z-index': 999,
          },
        },
        // Faded unselected elements
        {
          selector: '.faded',
          style: {
            'opacity': 0.15,
          },
        },
      ],
      layout: {
        name: 'breadthfirst',
        directed: true,
        roots: rootSuspectAddress ? [rootSuspectAddress] : undefined,
        padding: 50,
        spacingFactor: 1.6,
        animate: false,
      },
    });

    // Tap node event
    cy.on('tap', 'node', (evt: EventObject) => {
      const node = evt.target;
      const raw = node.data('rawNode') as GraphNode;
      onSelectNode(raw);
      onSelectEdge(null);
      highlightPathToRoot(node.id());
    });

    // Tap edge event
    cy.on('tap', 'edge', (evt: EventObject) => {
      const edge = evt.target;
      const raw = edge.data('rawEdge') as GraphEdge;
      onSelectEdge(raw);
      onSelectNode(null);

      // Highlight only the edge and its direct endpoints
      cy.elements().addClass('faded');
      edge.removeClass('faded').addClass('highlighted');
      edge.source().removeClass('faded').addClass('highlighted');
      edge.target().removeClass('faded').addClass('highlighted');
    });

    // Tap canvas background
    cy.on('tap', (evt: EventObject) => {
      if (evt.target === cy) {
        onSelectNode(null);
        onSelectEdge(null);
        cy.elements().removeClass('highlighted faded');
      }
    });

    cyRef.current = cy;

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [graph, onSelectNode, onSelectEdge, highlightPathToRoot]);

  // Handle label visibility toggle
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    if (showLabels) {
      cy.edges().style('label', 'data(label)');
      cy.nodes().style('label', 'data(label)');
    } else {
      cy.edges().style('label', '');
      cy.nodes().style('label', '');
    }
  }, [showLabels]);

  // Handle external selection update
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    if (!selectedNode && !selectedEdge) {
      cy.elements().removeClass('highlighted faded selected');
    }
  }, [selectedNode, selectedEdge]);

  // Toolbar Actions
  const handleZoomIn = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.3);
  const handleZoomOut = () => cyRef.current?.zoom(cyRef.current.zoom() * 0.7);
  const handleFit = () => cyRef.current?.fit(undefined, 40);
  const handleCenterRoot = () => {
    const root = cyRef.current?.nodes('[type = "suspect"]');
    if (root && root.length > 0) {
      cyRef.current?.center(root);
      cyRef.current?.zoom(1.2);
    }
  };
  const handleResetLayout = () => {
    if (!cyRef.current || !graph) return;
    const rootAddr = graph.meta.source_wallet || graph.nodes.find(n => n.node_type === 'suspect')?.address;
    cyRef.current.layout({
      name: 'breadthfirst',
      directed: true,
      roots: rootAddr ? [rootAddr] : undefined,
      padding: 50,
      spacingFactor: 1.6,
      animate: true,
      animationDuration: 400,
    }).run();
  };

  if (!graph || graph.nodes.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-12 bg-police-950/60 border border-police-700/60 rounded-xl space-y-3 text-slate-400">
        <Layers className="h-10 w-10 text-slate-600 animate-pulse" />
        <p className="text-sm font-semibold text-slate-300">No Graph Data Available</p>
        <p className="text-xs text-slate-500 max-w-sm text-center">
          Run an automated multi-hop trace to visualize the money trail from suspect to VASP endpoints.
        </p>
      </div>
    );
  }

  // Handle single-node graph (e.g. 0 outgoing transfers found)
  const isSingleNode = graph.nodes.length === 1 && graph.edges.length === 0;

  return (
    <div className="relative flex-1 w-full h-[600px] min-h-[500px] bg-police-950 border border-police-700/80 rounded-xl overflow-hidden shadow-inner flex flex-col">
      {/* Visual Canvas */}
      <div ref={containerRef} className="flex-1 w-full h-full cursor-grab active:cursor-grabbing" />

      {/* Single node / 0 transfer notice banner */}
      {isSingleNode && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 px-4 py-2 rounded-lg bg-amber-950/90 border border-amber-800 text-amber-200 text-xs flex items-center gap-2 shadow-lg backdrop-blur">
          <Info className="h-4 w-4 text-amber-400 shrink-0" />
          <span>Root suspect wallet has 0 relevant outgoing transfers matching current threshold (&gt;= ${graph.meta.min_relevant_usd}).</span>
        </div>
      )}

      {/* Floating Toolbar */}
      <div className="absolute top-4 right-4 z-10 flex flex-col gap-1.5 p-1 rounded-lg bg-police-900/90 border border-police-700/80 shadow-lg backdrop-blur">
        <button
          onClick={handleZoomIn}
          className="p-2 rounded hover:bg-police-800 text-slate-300 hover:text-white transition"
          title="Zoom In"
        >
          <ZoomIn className="h-4 w-4" />
        </button>
        <button
          onClick={handleZoomOut}
          className="p-2 rounded hover:bg-police-800 text-slate-300 hover:text-white transition"
          title="Zoom Out"
        >
          <ZoomOut className="h-4 w-4" />
        </button>
        <button
          onClick={handleFit}
          className="p-2 rounded hover:bg-police-800 text-slate-300 hover:text-white transition"
          title="Fit to Screen"
        >
          <Maximize2 className="h-4 w-4" />
        </button>
        <button
          onClick={handleCenterRoot}
          className="p-2 rounded hover:bg-police-800 text-slate-300 hover:text-white transition"
          title="Center on Root Suspect"
        >
          <Crosshair className="h-4 w-4" />
        </button>
        <button
          onClick={handleResetLayout}
          className="p-2 rounded hover:bg-police-800 text-slate-300 hover:text-white transition"
          title="Re-run Directed Layout"
        >
          <RotateCcw className="h-4 w-4" />
        </button>
        <button
          onClick={() => setShowLabels(!showLabels)}
          className={`p-2 rounded transition ${
            showLabels ? 'text-blue-400 bg-blue-950/40' : 'text-slate-400 hover:bg-police-800'
          }`}
          title={showLabels ? 'Hide Amount Labels' : 'Show Amount Labels'}
        >
          <Tag className="h-4 w-4" />
        </button>
      </div>

      {/* Legend Badge */}
      <div className="absolute bottom-4 left-4 z-10 p-2.5 rounded-lg bg-police-900/90 border border-police-700/80 shadow-lg backdrop-blur flex items-center gap-3 text-[11px]">
        <div className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-full bg-red-600 border border-red-400" />
          <span className="text-slate-300 font-semibold">Suspect</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-full bg-sky-600 border border-sky-400" />
          <span className="text-slate-300 font-semibold">Intermediate</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-full bg-emerald-600 border border-emerald-400" />
          <span className="text-slate-300 font-semibold">Endpoint / Deposit</span>
        </div>
        <div className="flex items-center gap-1 text-slate-400 pl-1 border-l border-police-700">
          <span>Click any node or edge to inspect & highlight path</span>
        </div>
      </div>
    </div>
  );
};
