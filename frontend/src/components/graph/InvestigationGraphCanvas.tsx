import React, { useEffect, useRef, useState, useCallback } from 'react';
import cytoscape from 'cytoscape';
import type { Core, EventObject } from 'cytoscape';
import { 
  ZoomIn, 
  ZoomOut, 
  Maximize2, 
  RotateCcw, 
  Crosshair, 
  Tag, 
  Info,
  Layers,
  Sparkles
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
  const [isDarkMode, setIsDarkMode] = useState<boolean>(() => {
    return typeof document !== 'undefined' && document.documentElement.classList.contains('dark');
  });

  // Observe theme changes on documentElement
  useEffect(() => {
    const checkTheme = () => {
      setIsDarkMode(document.documentElement.classList.contains('dark'));
    };
    checkTheme();
    const observer = new MutationObserver(checkTheme);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

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

  // Generate theme-appropriate Cytoscape stylesheet
  const getCytoscapeStyles = useCallback((dark: boolean): cytoscape.StylesheetStyle[] => {
    if (dark) {
      // Reactor Cyber Dark
      return [
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'color': '#f8fafc',
            'font-size': '10px',
            'font-family': 'JetBrains Mono, monospace',
            'font-weight': 'bold',
            'text-wrap': 'wrap',
            'text-valign': 'bottom',
            'text-margin-y': 7,
            'text-background-color': '#040507',
            'text-background-opacity': 0.9,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
            'text-border-width': 1,
            'text-border-color': '#293972',
            'text-border-opacity': 0.8,
            'transition-property': 'background-color, line-color, target-arrow-color, opacity, width, height, border-color, border-width',
            'transition-duration': 0.2,
            'border-width': 2.5,
            'background-color': '#122149',
            'border-color': '#293972',
            'width': 38,
            'height': 38,
          },
        },
        {
          selector: 'node[type = "suspect"]',
          style: {
            'background-color': '#450a0a',
            'border-color': '#ef4444',
            'border-width': 3.5,
            'width': 46,
            'height': 46,
            'color': '#fca5a5',
            'text-border-color': '#7f1d1d',
          },
        },
        {
          selector: 'node[type = "intermediate"]',
          style: {
            'background-color': '#122149',
            'border-color': '#38bdf8',
            'border-width': 2.5,
            'width': 38,
            'height': 38,
            'color': '#93c5fd',
            'text-border-color': '#1e293b',
          },
        },
        {
          selector: 'node[type = "endpoint"]',
          style: {
            'background-color': '#064e3b',
            'border-color': '#27FFBE',
            'border-width': 3.5,
            'width': 44,
            'height': 44,
            'color': '#27FFBE',
            'text-border-color': '#065f46',
          },
        },
        {
          selector: 'edge',
          style: {
            'curve-style': 'bezier',
            'target-arrow-shape': 'triangle',
            'target-arrow-color': '#475569',
            'line-color': '#334155',
            'width': 2.5,
            'arrow-scale': 1.2,
            'label': 'data(label)',
            'font-size': '10px',
            'font-family': 'JetBrains Mono, monospace',
            'font-weight': 'bold',
            'color': '#38bdf8',
            'text-background-color': '#040507',
            'text-background-opacity': 0.9,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
            'text-border-width': 1,
            'text-border-color': '#1e293b',
            'text-rotation': 'autorotate',
            'text-margin-y': -8,
            'transition-property': 'line-color, target-arrow-color, opacity, width',
            'transition-duration': 0.2,
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-color': '#FF5300',
            'border-width': 4,
            'background-color': '#122149',
          },
        },
        {
          selector: 'edge:selected',
          style: {
            'line-color': '#FF5300',
            'target-arrow-color': '#FF5300',
            'width': 4.5,
          },
        },
        {
          selector: 'node.highlighted',
          style: {
            'border-color': '#27FFBE',
            'border-width': 4,
            'opacity': 1.0,
            'z-index': 999,
          },
        },
        {
          selector: 'edge.highlighted',
          style: {
            'line-color': '#27FFBE',
            'target-arrow-color': '#27FFBE',
            'width': 4,
            'opacity': 1.0,
            'z-index': 999,
            'color': '#27FFBE',
            'text-border-color': '#27FFBE',
          },
        },
        {
          selector: '.faded',
          style: {
            'opacity': 0.12,
          },
        },
      ];
    } else {
      // Reactor Clean Light
      return [
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'color': '#122149',
            'font-size': '10px',
            'font-family': 'JetBrains Mono, monospace',
            'font-weight': 'bold',
            'text-wrap': 'wrap',
            'text-valign': 'bottom',
            'text-margin-y': 7,
            'text-background-color': '#ffffff',
            'text-background-opacity': 0.95,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
            'text-border-width': 1,
            'text-border-color': '#d1d3e0',
            'transition-property': 'background-color, line-color, target-arrow-color, opacity, width, height, border-color, border-width',
            'transition-duration': 0.2,
            'border-width': 2.5,
            'background-color': '#ffffff',
            'border-color': '#293972',
            'width': 38,
            'height': 38,
          },
        },
        {
          selector: 'node[type = "suspect"]',
          style: {
            'background-color': '#FFE4DF',
            'border-color': '#B50004',
            'border-width': 3.5,
            'width': 46,
            'height': 46,
            'color': '#B50004',
            'text-background-color': '#FFE4DF',
            'text-border-color': '#B50004',
          },
        },
        {
          selector: 'node[type = "intermediate"]',
          style: {
            'background-color': '#ffffff',
            'border-color': '#293972',
            'border-width': 2.5,
            'width': 38,
            'height': 38,
            'color': '#122149',
            'text-background-color': '#ffffff',
            'text-border-color': '#d1d3e0',
          },
        },
        {
          selector: 'node[type = "endpoint"]',
          style: {
            'background-color': '#E6F9F0',
            'border-color': '#007D04',
            'border-width': 3.5,
            'width': 44,
            'height': 44,
            'color': '#005602',
            'text-background-color': '#E6F9F0',
            'text-border-color': '#007D04',
          },
        },
        {
          selector: 'edge',
          style: {
            'curve-style': 'bezier',
            'target-arrow-shape': 'triangle',
            'target-arrow-color': '#626e82',
            'line-color': '#8c96a8',
            'width': 2.5,
            'arrow-scale': 1.2,
            'label': 'data(label)',
            'font-size': '10px',
            'font-family': 'JetBrains Mono, monospace',
            'font-weight': 'bold',
            'color': '#122149',
            'text-background-color': '#ffffff',
            'text-background-opacity': 0.95,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
            'text-border-width': 1,
            'text-border-color': '#d1d3e0',
            'text-rotation': 'autorotate',
            'text-margin-y': -8,
            'transition-property': 'line-color, target-arrow-color, opacity, width',
            'transition-duration': 0.2,
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-color': '#FF5300',
            'border-width': 4,
            'background-color': '#FFF3EB',
          },
        },
        {
          selector: 'edge:selected',
          style: {
            'line-color': '#FF5300',
            'target-arrow-color': '#FF5300',
            'width': 4.5,
          },
        },
        {
          selector: 'node.highlighted',
          style: {
            'border-color': '#FF5300',
            'border-width': 4,
            'opacity': 1.0,
            'z-index': 999,
          },
        },
        {
          selector: 'edge.highlighted',
          style: {
            'line-color': '#FF5300',
            'target-arrow-color': '#FF5300',
            'width': 4,
            'opacity': 1.0,
            'z-index': 999,
            'color': '#FF5300',
            'text-border-color': '#FF5300',
          },
        },
        {
          selector: '.faded',
          style: {
            'opacity': 0.12,
          },
        },
      ];
    }
  }, []);

  // Update Cytoscape styles when theme changes
  useEffect(() => {
    if (cyRef.current) {
      cyRef.current.style(getCytoscapeStyles(isDarkMode)).update();
    }
  }, [isDarkMode, getCytoscapeStyles]);

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
        const sentAmount = n.total_sent ? formatAmount(n.total_sent) : '';
        labelText = `🚨 SUSPECT\n${shortAddr(n.address)}${sentAmount ? `\nSent: ${sentAmount}` : ''}`;
      } else if (n.node_type === 'endpoint') {
        const recAmount = n.total_received ? formatAmount(n.total_received) : '';
        labelText = `🎯 VASP ENDPOINT\n${shortAddr(n.address)}${recAmount ? `\nRec: ${recAmount}` : ''}`;
      } else {
        const recAmount = n.total_received ? formatAmount(n.total_received) : '';
        labelText = `Hop ${n.hop}\n${shortAddr(n.address)}${recAmount ? `\n${recAmount}` : ''}`;
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
      style: getCytoscapeStyles(isDarkMode),
      layout: {
        name: 'breadthfirst',
        directed: true,
        roots: (rootSuspectAddress ? `[id = "${rootSuspectAddress}"]` : undefined) as any,
        padding: 60,
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
  }, [graph, onSelectNode, onSelectEdge, highlightPathToRoot, getCytoscapeStyles, isDarkMode]);

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
    } else if (selectedNode) {
      highlightPathToRoot(selectedNode.address);
      const el = cy.getElementById(selectedNode.address);
      if (el && el.length > 0) {
        cy.center(el);
        cy.zoom(1.2);
        el.addClass('selected');
      }
    } else if (selectedEdge) {
      cy.elements().addClass('faded');
      const edgeEl = cy.getElementById(selectedEdge.id) || cy.edges(`[source = "${selectedEdge.from_address}"][target = "${selectedEdge.to_address}"]`);
      if (edgeEl && edgeEl.length > 0) {
        edgeEl.removeClass('faded').addClass('highlighted selected');
      }
    }
  }, [selectedNode, selectedEdge, highlightPathToRoot]);

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
      roots: (rootAddr ? `[id = "${rootAddr}"]` : undefined) as any,
      padding: 60,
      spacingFactor: 1.6,
      animate: true,
      animationDuration: 400,
    }).run();
  };

  if (!graph || graph.nodes.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-12 bg-surface-50 border border-surface-200 rounded-xl space-y-3 text-surface-400">
        <Layers className="h-10 w-10 text-surface-400 animate-pulse" />
        <p className="text-lg font-semibold text-surface-700">No Graph Data Available</p>
        <p className="text-base text-surface-500 max-w-sm text-center">
          Run an automated multi-hop trace to visualize the money trail from suspect to VASP endpoints.
        </p>
      </div>
    );
  }

  // Handle single-node graph (e.g. 0 outgoing transfers found)
  const isSingleNode = graph.nodes.length === 1 && graph.edges.length === 0;

  return (
    <div className="relative flex-1 w-full h-full min-h-[520px] bg-surface-50 border border-surface-200 rounded-lg overflow-hidden flex flex-col transition-colors">
      {/* Visual Canvas */}
      <div ref={containerRef} className="flex-1 w-full h-full cursor-grab active:cursor-grabbing" />

      {/* Single node / 0 transfer notice banner */}
      {isSingleNode && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 px-4 py-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-700 dark:text-amber-300 text-sm flex items-center gap-2 shadow-lg backdrop-blur z-20">
          <Info className="h-4 w-4 text-amber-500 shrink-0" />
          <span>Root suspect wallet has 0 relevant outgoing transfers matching current threshold (&gt;= ${graph.meta.min_relevant_usd}).</span>
        </div>
      )}

      {/* Floating Reactor Graph Toolbar */}
      <div className="absolute top-4 right-4 z-10 flex flex-col gap-1 p-1 rounded-lg bg-surface-default/95 dark:bg-surface-100/95 border border-surface-200 dark:border-surface-300 shadow-lg backdrop-blur">
        <button
          onClick={handleZoomIn}
          className="p-2 rounded hover:bg-surface-100 dark:hover:bg-surface-200 text-surface-600 dark:text-surface-300 hover:text-surface-900 dark:hover:text-white transition"
          title="Zoom In"
          aria-label="Zoom In"
        >
          <ZoomIn className="h-4 w-4" />
        </button>
        <button
          onClick={handleZoomOut}
          className="p-2 rounded hover:bg-surface-100 dark:hover:bg-surface-200 text-surface-600 dark:text-surface-300 hover:text-surface-900 dark:hover:text-white transition"
          title="Zoom Out"
          aria-label="Zoom Out"
        >
          <ZoomOut className="h-4 w-4" />
        </button>
        <button
          onClick={handleFit}
          className="p-2 rounded hover:bg-surface-100 dark:hover:bg-surface-200 text-surface-600 dark:text-surface-300 hover:text-surface-900 dark:hover:text-white transition"
          title="Fit to Screen"
          aria-label="Fit to Screen"
        >
          <Maximize2 className="h-4 w-4" />
        </button>
        <button
          onClick={handleCenterRoot}
          className="p-2 rounded hover:bg-surface-100 dark:hover:bg-surface-200 text-surface-600 dark:text-surface-300 hover:text-surface-900 dark:hover:text-white transition"
          title="Center on Root Suspect"
          aria-label="Center on Root Suspect"
        >
          <Crosshair className="h-4 w-4" />
        </button>
        <button
          onClick={handleResetLayout}
          className="p-2 rounded hover:bg-surface-100 dark:hover:bg-surface-200 text-surface-600 dark:text-surface-300 hover:text-surface-900 dark:hover:text-white transition"
          title="Re-run Directed Layout"
          aria-label="Re-run Directed Layout"
        >
          <RotateCcw className="h-4 w-4" />
        </button>
        <div className="w-full h-px bg-surface-200 dark:bg-surface-300 my-0.5" />
        <button
          onClick={() => setShowLabels(!showLabels)}
          className={`p-2 rounded transition ${
            showLabels 
              ? 'text-reactor-orange bg-orange-500/10 dark:bg-orange-500/20' 
              : 'text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-200'
          }`}
          title={showLabels ? 'Hide Amount Labels' : 'Show Amount Labels'}
          aria-label="Toggle Amount Labels"
        >
          <Tag className="h-4 w-4" />
        </button>
      </div>

      {/* Legend Badge Bar */}
      <div className="absolute bottom-4 left-4 z-10 p-2 rounded-lg bg-surface-default/95 dark:bg-surface-100/95 border border-surface-200 dark:border-surface-300 shadow-lg backdrop-blur flex flex-wrap items-center gap-3 text-xs">
        <div className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-full bg-red-600 border border-red-400" />
          <span className="text-surface-700 dark:text-surface-300 font-semibold">Suspect Root</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-full bg-blue-600 border border-blue-400" />
          <span className="text-surface-700 dark:text-surface-300 font-semibold">Intermediate Mule</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-full bg-emerald-600 border border-emerald-400" />
          <span className="text-surface-700 dark:text-surface-300 font-semibold">VASP Endpoint</span>
        </div>
        <div className="hidden sm:flex items-center gap-1 text-surface-500 pl-2 border-l border-surface-200 dark:border-surface-300 font-medium">
          <Sparkles className="h-3 w-3 text-reactor-orange" />
          <span>Click entity or edge to trace path to root</span>
        </div>
      </div>
    </div>
  );
};
