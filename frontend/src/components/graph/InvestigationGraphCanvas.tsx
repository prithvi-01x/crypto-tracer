import React, { useEffect, useRef, useState, useCallback } from 'react';
import cytoscape from 'cytoscape';
import type { Core, EventObject } from 'cytoscape';
import { 
  ZoomIn, 
  ZoomOut, 
  Maximize2, 
  Minimize2,
  RotateCcw, 
  Crosshair, 
  Tag, 
  Info,
  Layers,
  Sparkles
} from 'lucide-react';
import type { InvestigationGraph, GraphNode, GraphEdge } from '../../types/graph';
import type { AttributionResponse } from '../../types/attribution';

interface InvestigationGraphCanvasProps {
  graph: InvestigationGraph | null;
  onSelectNode: (node: GraphNode | null) => void;
  onSelectEdge: (edge: GraphEdge | null) => void;
  selectedNode: GraphNode | null;
  selectedEdge: GraphEdge | null;
  attribution?: AttributionResponse | null;
  onToggleMaximize?: () => void;
  isMaximized?: boolean;
}

export const InvestigationGraphCanvas: React.FC<InvestigationGraphCanvasProps> = ({
  graph,
  onSelectNode,
  onSelectEdge,
  selectedNode,
  selectedEdge,
  attribution,
  onToggleMaximize,
  isMaximized = false,
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
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
  };

  // Helper to format currency
  const formatAmount = (val: number | string) => {
    const num = typeof val === 'string' ? parseFloat(val) : val;
    if (isNaN(num)) return `$${val}`;
    if (num >= 1000000) {
      return `$${(num / 1000000).toFixed(2)}M`;
    }
    if (num >= 1000) {
      return `$${(num / 1000).toFixed(1)}k`;
    }
    return `$${num.toFixed(2)}`;
  };

  // Generate theme-appropriate Cytoscape stylesheet
  const getCytoscapeStyles = useCallback((dark: boolean): cytoscape.StylesheetStyle[] => {
    if (dark) {
      // Reactor Cyber Dark - Presentation Scaled
      return [
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'color': '#f1f5f9',
            'font-size': '11px',
            'font-family': 'JetBrains Mono, monospace',
            'font-weight': 'bold',
            'text-wrap': 'wrap',
            'text-max-width': '150px',
            'text-valign': 'bottom',
            'text-margin-y': 9,
            'text-background-color': '#030712',
            'text-background-opacity': 0.95,
            'text-background-padding': '4px 7px',
            'text-background-shape': 'roundrectangle',
            'text-border-width': 1,
            'text-border-color': '#1e293b',
            'text-border-opacity': 0.9,
            'transition-property': 'background-color, line-color, target-arrow-color, opacity, width, height, border-color, border-width',
            'transition-duration': 0.2,
            'border-width': 3,
            'background-color': '#0f172a',
            'border-color': '#334155',
            'width': 58,
            'height': 58,
          },
        },
        {
          selector: 'node[type = "suspect"]',
          style: {
            'background-color': '#3b0707',
            'border-color': '#ef4444',
            'border-width': 4.5,
            'width': 76,
            'height': 76,
            'color': '#fca5a5',
            'font-size': '11.5px',
            'text-background-color': '#1f0404',
            'text-border-color': '#7f1d1d',
            'text-margin-y': 10,
          },
        },
        {
          selector: 'node[type = "candidate"]',
          style: {
            'background-color': '#2e1065',
            'border-color': '#c084fc',
            'border-width': 4,
            'width': 72,
            'height': 72,
            'color': '#e9d5ff',
            'font-size': '11.5px',
            'text-background-color': '#190638',
            'text-border-color': '#6b21a8',
            'text-margin-y': 10,
          },
        },
        {
          selector: 'node[type = "endpoint"]',
          style: {
            'background-color': '#064e3b',
            'border-color': '#27FFBE',
            'border-width': 4,
            'width': 72,
            'height': 72,
            'color': '#27FFBE',
            'font-size': '11.5px',
            'text-background-color': '#022c22',
            'text-border-color': '#065f46',
            'text-margin-y': 10,
          },
        },
        {
          selector: 'node[type = "consolidation"]',
          style: {
            'background-color': '#1e1b4b',
            'border-color': '#818cf8',
            'border-width': 3.5,
            'width': 64,
            'height': 64,
            'color': '#c7d2fe',
            'font-size': '11px',
            'text-background-color': '#0f0e2a',
            'text-border-color': '#3730a3',
            'text-margin-y': 9,
          },
        },
        {
          selector: 'node[type = "intermediate"]',
          style: {
            'background-color': '#0f172a',
            'border-color': '#38bdf8',
            'border-width': 3,
            'width': 58,
            'height': 58,
            'color': '#bae6fd',
            'font-size': '11px',
            'text-background-color': '#030712',
            'text-border-color': '#1e293b',
            'text-margin-y': 8,
          },
        },
        {
          selector: 'edge',
          style: {
            'curve-style': 'bezier',
            'target-arrow-shape': 'triangle',
            'target-arrow-color': '#64748b',
            'line-color': '#475569',
            'width': 3.5,
            'arrow-scale': 1.45,
            'label': 'data(label)',
            'font-size': '11px',
            'font-family': 'JetBrains Mono, monospace',
            'font-weight': 'bold',
            'color': '#38bdf8',
            'text-background-color': '#030712',
            'text-background-opacity': 0.95,
            'text-background-padding': '3px 7px',
            'text-background-shape': 'roundrectangle',
            'text-border-width': 1,
            'text-border-color': '#1e293b',
            'text-rotation': 'autorotate',
            'text-margin-y': -10,
            'transition-property': 'line-color, target-arrow-color, opacity, width',
            'transition-duration': 0.2,
          },
        },
        {
          selector: 'edge[amount > 25000]',
          style: {
            'width': 4.5,
            'line-color': '#0284c7',
            'target-arrow-color': '#0284c7',
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-color': '#FF5300',
            'border-width': 6,
            'z-index': 999,
          },
        },
        {
          selector: 'edge:selected',
          style: {
            'line-color': '#FF5300',
            'target-arrow-color': '#FF5300',
            'width': 6,
            'z-index': 999,
          },
        },
        {
          selector: 'node.highlighted',
          style: {
            'border-color': '#27FFBE',
            'border-width': 5.5,
            'opacity': 1.0,
            'z-index': 999,
          },
        },
        {
          selector: 'edge.highlighted',
          style: {
            'line-color': '#27FFBE',
            'target-arrow-color': '#27FFBE',
            'width': 5.5,
            'opacity': 1.0,
            'z-index': 999,
            'color': '#27FFBE',
            'text-border-color': '#27FFBE',
          },
        },
        {
          selector: '.faded',
          style: {
            'opacity': 0.14,
          },
        },
      ];
    } else {
      // Clean Light - High Contrast
      return [
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'color': '#0f172a',
            'font-size': '11px',
            'font-family': 'JetBrains Mono, monospace',
            'font-weight': 'bold',
            'text-wrap': 'wrap',
            'text-max-width': '150px',
            'text-valign': 'bottom',
            'text-margin-y': 9,
            'text-background-color': '#ffffff',
            'text-background-opacity': 0.96,
            'text-background-padding': '4px 7px',
            'text-background-shape': 'roundrectangle',
            'text-border-width': 1,
            'text-border-color': '#cbd5e1',
            'transition-property': 'background-color, line-color, target-arrow-color, opacity, width, height, border-color, border-width',
            'transition-duration': 0.2,
            'border-width': 3,
            'background-color': '#ffffff',
            'border-color': '#94a3b8',
            'width': 58,
            'height': 58,
          },
        },
        {
          selector: 'node[type = "suspect"]',
          style: {
            'background-color': '#fef2f2',
            'border-color': '#dc2626',
            'border-width': 4.5,
            'width': 76,
            'height': 76,
            'color': '#991b1b',
            'font-size': '11.5px',
            'text-background-color': '#fff1f2',
            'text-border-color': '#fecaca',
            'text-margin-y': 10,
          },
        },
        {
          selector: 'node[type = "candidate"]',
          style: {
            'background-color': '#faf5ff',
            'border-color': '#7c3aed',
            'border-width': 4,
            'width': 72,
            'height': 72,
            'color': '#5b21b6',
            'font-size': '11.5px',
            'text-background-color': '#fdf4ff',
            'text-border-color': '#e9d5ff',
            'text-margin-y': 10,
          },
        },
        {
          selector: 'node[type = "endpoint"]',
          style: {
            'background-color': '#ecfdf5',
            'border-color': '#059669',
            'border-width': 4,
            'width': 72,
            'height': 72,
            'color': '#065f46',
            'font-size': '11.5px',
            'text-background-color': '#f0fdf4',
            'text-border-color': '#a7f3d0',
            'text-margin-y': 10,
          },
        },
        {
          selector: 'node[type = "consolidation"]',
          style: {
            'background-color': '#eef2ff',
            'border-color': '#4f46e5',
            'border-width': 3.5,
            'width': 64,
            'height': 64,
            'color': '#3730a3',
            'font-size': '11px',
            'text-background-color': '#f5f3ff',
            'text-border-color': '#c7d2fe',
            'text-margin-y': 9,
          },
        },
        {
          selector: 'node[type = "intermediate"]',
          style: {
            'background-color': '#f0f9ff',
            'border-color': '#0284c7',
            'border-width': 3,
            'width': 58,
            'height': 58,
            'color': '#0369a1',
            'font-size': '11px',
            'text-background-color': '#ffffff',
            'text-border-color': '#cbd5e1',
            'text-margin-y': 8,
          },
        },
        {
          selector: 'edge',
          style: {
            'curve-style': 'bezier',
            'target-arrow-shape': 'triangle',
            'target-arrow-color': '#64748b',
            'line-color': '#94a3b8',
            'width': 3.5,
            'arrow-scale': 1.45,
            'label': 'data(label)',
            'font-size': '11px',
            'font-family': 'JetBrains Mono, monospace',
            'font-weight': 'bold',
            'color': '#0369a1',
            'text-background-color': '#ffffff',
            'text-background-opacity': 0.96,
            'text-background-padding': '3px 7px',
            'text-background-shape': 'roundrectangle',
            'text-border-width': 1,
            'text-border-color': '#cbd5e1',
            'text-rotation': 'autorotate',
            'text-margin-y': -10,
            'transition-property': 'line-color, target-arrow-color, opacity, width',
            'transition-duration': 0.2,
          },
        },
        {
          selector: 'edge[amount > 25000]',
          style: {
            'width': 4.5,
            'line-color': '#0284c7',
            'target-arrow-color': '#0284c7',
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-color': '#FF5300',
            'border-width': 6,
            'z-index': 999,
          },
        },
        {
          selector: 'edge:selected',
          style: {
            'line-color': '#FF5300',
            'target-arrow-color': '#FF5300',
            'width': 6,
            'z-index': 999,
          },
        },
        {
          selector: 'node.highlighted',
          style: {
            'border-color': '#2563eb',
            'border-width': 5.5,
            'opacity': 1.0,
            'z-index': 999,
          },
        },
        {
          selector: 'edge.highlighted',
          style: {
            'line-color': '#2563eb',
            'target-arrow-color': '#2563eb',
            'width': 5.5,
            'opacity': 1.0,
            'z-index': 999,
            'color': '#2563eb',
            'text-border-color': '#2563eb',
          },
        },
        {
          selector: '.faded',
          style: {
            'opacity': 0.14,
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

  // Highlight path from root suspect to given target node (with upstream/downstream context)
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
      targetNode.connectedEdges().addClass('highlighted');
      return;
    }

    if (targetNode.id() === rootNode.id()) {
      // Root suspect selected: highlight root and all outgoing flows
      cy.elements().addClass('faded');
      rootNode.removeClass('faded').addClass('highlighted');
      rootNode.outgoers().removeClass('faded').addClass('highlighted');
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
      // Also highlight target's immediate outgoers for downstream visibility
      targetNode.outgoers().removeClass('faded').addClass('highlighted');
    } else {
      // If no direct forward path, highlight the selected node and its connected edges
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

    // Compute in-degree count to identify consolidation points
    const inDegreeMap: Record<string, number> = {};
    graph.edges.forEach((e) => {
      inDegreeMap[e.to_address] = (inDegreeMap[e.to_address] || 0) + 1;
    });

    const candidateAddr = attribution?.best_candidate?.candidate_address;
    const vaspName = (attribution?.best_candidate?.exchange_name || 'VASP').toUpperCase();
    const isRootSuspect = (addr: string, type: string) =>
      type === 'suspect' || addr === graph.meta.source_wallet;

    // Add Nodes
    graph.nodes.forEach((n) => {
      let assignedType = n.node_type;
      let labelText = `${shortAddr(n.address)}`;

      if (isRootSuspect(n.address, n.node_type)) {
        assignedType = 'suspect';
        const sentAmount = n.total_sent ? formatAmount(n.total_sent) : '';
        labelText = `🚨 ROOT SUSPECT
${shortAddr(n.address)}${sentAmount ? `
Sent: ${sentAmount}` : ''}`;
      } else if (candidateAddr && n.address === candidateAddr) {
        assignedType = 'candidate';
        const recAmount = n.total_received ? formatAmount(n.total_received) : '';
        labelText = `🎯 ${vaspName} CANDIDATE
${shortAddr(n.address)}${recAmount ? `
Rec: ${recAmount}` : ''}`;
      } else if (n.node_type === 'endpoint') {
        assignedType = 'endpoint';
        const recAmount = n.total_received ? formatAmount(n.total_received) : '';
        labelText = `🏦 VASP DESTINATION
${shortAddr(n.address)}${recAmount ? `
Rec: ${recAmount}` : ''}`;
      } else if ((inDegreeMap[n.address] || 0) > 1 || (n.hop === 2 && (typeof n.total_received === 'number' ? n.total_received : parseFloat(n.total_received || '0')) >= 40000)) {
        assignedType = 'consolidation';
        const recAmount = n.total_received ? formatAmount(n.total_received) : '';
        labelText = `🔄 CONSOLIDATION
${shortAddr(n.address)}${recAmount ? `
Rec: ${recAmount}` : ''}`;
      } else {
        assignedType = 'intermediate';
        const recAmount = n.total_received ? formatAmount(n.total_received) : '';
        labelText = `🔗 HOP ${n.hop} MULE
${shortAddr(n.address)}${recAmount ? `
${recAmount}` : ''}`;
      }

      elements.push({
        group: 'nodes',
        data: {
          id: n.address,
          label: labelText,
          type: assignedType,
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
        padding: 40,
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
  }, [graph, attribution, onSelectNode, onSelectEdge, highlightPathToRoot, getCytoscapeStyles, isDarkMode]);

  // Observe container size changes (e.g. dynamic slider resize) and trigger Cytoscape resize
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver(() => {
      if (cyRef.current) {
        cyRef.current.resize();
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

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
  const handleZoomIn = useCallback(() => {
    if (!cyRef.current) return;
    cyRef.current.zoom(cyRef.current.zoom() * 1.3);
  }, []);

  const handleZoomOut = useCallback(() => {
    if (!cyRef.current) return;
    cyRef.current.zoom(cyRef.current.zoom() * 0.7);
  }, []);

  const handleFit = useCallback(() => {
    if (!cyRef.current) return;
    cyRef.current.fit(undefined, 40);
  }, []);

  const handleCenterRoot = useCallback(() => {
    const root = cyRef.current?.nodes('[type = "suspect"]');
    if (root && root.length > 0) {
      cyRef.current?.center(root);
      cyRef.current?.zoom(1.2);
    }
  }, []);

  const handleResetLayout = useCallback(() => {
    if (!cyRef.current || !graph) return;
    const rootAddr = graph.meta.source_wallet || graph.nodes.find(n => n.node_type === 'suspect')?.address;
    cyRef.current.layout({
      name: 'breadthfirst',
      directed: true,
      roots: (rootAddr ? `[id = "${rootAddr}"]` : undefined) as any,
      padding: 40,
      spacingFactor: 1.6,
      animate: true,
      animationDuration: 400,
    }).run();
  }, [graph]);

  // Keyboard navigation shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable)
      ) {
        return;
      }

      if (e.key === 'f' || e.key === 'F') {
        e.preventDefault();
        handleFit();
      } else if (e.key === 'r' || e.key === 'R') {
        e.preventDefault();
        handleResetLayout();
      } else if (e.key === 'c' || e.key === 'C') {
        e.preventDefault();
        handleCenterRoot();
      } else if (e.key === 'l' || e.key === 'L') {
        e.preventDefault();
        setShowLabels(prev => !prev);
      } else if (e.key === '+' || e.key === '=') {
        e.preventDefault();
        handleZoomIn();
      } else if (e.key === '-' || e.key === '_') {
        e.preventDefault();
        handleZoomOut();
      } else if ((e.key === 'm' || e.key === 'M') && onToggleMaximize) {
        e.preventDefault();
        onToggleMaximize();
      } else if (e.key === 'Escape') {
        onSelectNode(null);
        onSelectEdge(null);
        cyRef.current?.elements().removeClass('highlighted faded selected');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleFit, handleResetLayout, handleCenterRoot, handleZoomIn, handleZoomOut, onToggleMaximize, onSelectNode, onSelectEdge]);

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
    <div className="relative flex-1 w-full h-full min-h-[500px] bg-surface-50 dark:bg-[#070b14] overflow-hidden flex flex-col transition-colors select-none">
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
      <div className="absolute top-4 right-4 z-10 flex flex-col gap-1.5 p-1.5 rounded-lg bg-surface-default/95 dark:bg-surface-100/95 border border-surface-200 dark:border-surface-300 shadow-lg backdrop-blur">
        {onToggleMaximize && (
          <>
            <button
              onClick={onToggleMaximize}
              className="p-2 rounded hover:bg-surface-100 dark:hover:bg-surface-200 text-surface-600 dark:text-surface-300 hover:text-surface-900 dark:hover:text-white transition"
              title={isMaximized ? "Restore Split View" : "Maximize Canvas"}
              aria-label={isMaximized ? "Restore Split View" : "Maximize Canvas"}
            >
              {isMaximized ? <Minimize2 className="h-4.5 w-4.5 text-reactor-orange" /> : <Maximize2 className="h-4.5 w-4.5" />}
            </button>
            <div className="w-full h-px bg-surface-200 dark:bg-surface-300 my-0.5" />
          </>
        )}
        <button
          onClick={handleZoomIn}
          className="p-2 rounded hover:bg-surface-100 dark:hover:bg-surface-200 text-surface-600 dark:text-surface-300 hover:text-surface-900 dark:hover:text-white transition"
          title="Zoom In"
          aria-label="Zoom In"
        >
          <ZoomIn className="h-4.5 w-4.5" />
        </button>
        <button
          onClick={handleZoomOut}
          className="p-2 rounded hover:bg-surface-100 dark:hover:bg-surface-200 text-surface-600 dark:text-surface-300 hover:text-surface-900 dark:hover:text-white transition"
          title="Zoom Out"
          aria-label="Zoom Out"
        >
          <ZoomOut className="h-4.5 w-4.5" />
        </button>
        <button
          onClick={handleFit}
          className="p-2 rounded hover:bg-surface-100 dark:hover:bg-surface-200 text-surface-600 dark:text-surface-300 hover:text-surface-900 dark:hover:text-white transition"
          title="Fit to Screen"
          aria-label="Fit to Screen"
        >
          <Maximize2 className="h-4.5 w-4.5" />
        </button>
        <button
          onClick={handleCenterRoot}
          className="p-2 rounded hover:bg-surface-100 dark:hover:bg-surface-200 text-surface-600 dark:text-surface-300 hover:text-surface-900 dark:hover:text-white transition"
          title="Center on Root Suspect"
          aria-label="Center on Root Suspect"
        >
          <Crosshair className="h-4.5 w-4.5" />
        </button>
        <button
          onClick={handleResetLayout}
          className="p-2 rounded hover:bg-surface-100 dark:hover:bg-surface-200 text-surface-600 dark:text-surface-300 hover:text-surface-900 dark:hover:text-white transition"
          title="Re-run Directed Layout"
          aria-label="Re-run Directed Layout"
        >
          <RotateCcw className="h-4.5 w-4.5" />
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
          <Tag className="h-4.5 w-4.5" />
        </button>
      </div>

      {/* Legend Badge Bar */}
      <div className="absolute bottom-4 left-4 z-10 p-2.5 rounded-lg bg-surface-default/95 dark:bg-surface-100/95 border border-surface-200 dark:border-surface-300 shadow-lg backdrop-blur flex flex-wrap items-center gap-3.5 text-xs">
        <div className="flex items-center gap-2">
          <span className="h-3.5 w-3.5 rounded-full bg-red-600 border border-red-400 shrink-0" />
          <span className="text-surface-800 dark:text-surface-200 font-bold">Suspect Root</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-3.5 w-3.5 rounded-full bg-sky-500 border border-sky-400 shrink-0" />
          <span className="text-surface-800 dark:text-surface-200 font-bold">Intermediate Hop</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-3.5 w-3.5 rounded-full bg-indigo-600 border border-indigo-400 shrink-0" />
          <span className="text-surface-800 dark:text-surface-200 font-bold">Consolidation Mule</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-3.5 w-3.5 rounded-full bg-purple-600 border border-purple-400 shrink-0" />
          <span className="text-surface-800 dark:text-surface-200 font-bold">VASP Candidate</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-3.5 w-3.5 rounded-full bg-emerald-600 border border-emerald-400 shrink-0" />
          <span className="text-surface-800 dark:text-surface-200 font-bold">VASP Endpoint</span>
        </div>
        <div className="hidden xl:flex items-center gap-1.5 text-surface-500 pl-2.5 border-l border-surface-200 dark:border-surface-300 font-medium">
          <Sparkles className="h-3.5 w-3.5 text-reactor-orange shrink-0" />
          <span>Hotkeys: F (fit) &bull; R (reset) &bull; C (suspect) &bull; L (labels) &bull; M (expand)</span>
        </div>
      </div>
    </div>
  );
};
