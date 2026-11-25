import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import ForceGraph3D from 'react-force-graph-3d';
import SpriteText from 'three-spritetext';
import {
  Box,
  Compass,
  ExternalLink,
  Focus,
  Layers,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  RotateCcw,
  Scale,
  Search,
  Share2,
} from 'lucide-react';

interface GraphNode {
  id: string;
  name: string;
  shortName: string;
  type: string;
  typeLabel: string;
  color: string;
  val: number;
  degree: number;
  inDegree?: number;
  outDegree?: number;
  weightedDegree?: number;
  activeIn?: number;
  activeOut?: number;
  activeDegree?: number;
  activeWeight?: number;
  radius3D?: number;
  radius2D?: number;
  domain?: string | null;
  url?: string | null;
  description: string;
  aliases: string[];
  x?: number;
  y?: number;
  z?: number;
}

interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  relation: string;
  weight: number;
}

interface Perspective {
  id: string;
  title: string;
  description: string;
  node_types: string[];
}

interface ForceGraphPayload {
  metadata: {
    project: string;
    repo: string;
    nodeCount: number;
    linkCount: number;
    scopePolicy: string;
  };
  perspectives: Perspective[];
  nodeTypes: Record<string, { color: string; val: number; label_sv: string }>;
  nodes: GraphNode[];
  links: GraphLink[];
}

type DagLayout = '' | 'radialout' | 'td' | 'lr';

function endpointId(end: string | GraphNode): string {
  return typeof end === 'string' ? end : end.id;
}

export default function App() {
  const [rawData, setRawData] = useState<ForceGraphPayload | null>(null);
  const [activePerspective, setActivePerspective] = useState<string>('helhetsbild');
  // 3D som default!
  const [is3D, setIs3D] = useState<boolean>(true);
  const [weightByDegree, setWeightByDegree] = useState<boolean>(true);
  const [dagMode, setDagMode] = useState<DagLayout>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set());
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>('totalforsvaret');
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [egoCenterId, setEgoCenterId] = useState<string | null>(null);
  const [leftOpen, setLeftOpen] = useState<boolean>(true);
  const [rightOpen, setRightOpen] = useState<boolean>(true);
  const [dimensions, setDimensions] = useState({ width: window.innerWidth, height: window.innerHeight });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fg2dRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fg3dRef = useRef<any>(null);
  const inspectorRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const onResize = () => setDimensions({ width: window.innerWidth, height: window.innerHeight });
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  useEffect(() => {
    fetch('./data/force_graph.json')
      .then((r) => r.json())
      .then((data: ForceGraphPayload) => setRawData(data))
      .catch((err) => console.error('Kunde inte ladda force_graph.json:', err));
  }, []);

  const filteredGraph = useMemo(() => {
    if (!rawData) return { nodes: [] as GraphNode[], links: [] as GraphLink[] };

    const persp =
      rawData.perspectives.find((p) => p.id === activePerspective) ?? rawData.perspectives[0];
    const allowedByPerspective = new Set(persp.node_types);

    let candidateIds = new Set(
      rawData.nodes
        .filter((n) => allowedByPerspective.has(n.type) && !hiddenTypes.has(n.type))
        .map((n) => n.id)
    );

    if (egoCenterId) {
      const egoSet = new Set<string>([egoCenterId]);
      let frontier = new Set<string>([egoCenterId]);
      for (let hop = 0; hop < 2; hop++) {
        const next = new Set<string>();
        for (const l of rawData.links) {
          const s = endpointId(l.source);
          const t = endpointId(l.target);
          if (frontier.has(s) && !egoSet.has(t)) next.add(t);
          if (frontier.has(t) && !egoSet.has(s)) next.add(s);
        }
        next.forEach((id) => egoSet.add(id));
        frontier = next;
      }
      candidateIds = egoSet;
    }

    const q = searchQuery.trim().toLowerCase();
    if (q) {
      const matched = new Set<string>();
      for (const n of rawData.nodes) {
        if (!candidateIds.has(n.id)) continue;
        const hay = `${n.name} ${n.shortName} ${n.description} ${n.aliases.join(' ')}`.toLowerCase();
        if (hay.includes(q)) matched.add(n.id);
      }
      const withNeighbors = new Set<string>(matched);
      for (const l of rawData.links) {
        const s = endpointId(l.source);
        const t = endpointId(l.target);
        if (matched.has(s) && candidateIds.has(t)) withNeighbors.add(t);
        if (matched.has(t) && candidateIds.has(s)) withNeighbors.add(s);
      }
      candidateIds = withNeighbors;
    }

    const links = rawData.links
      .filter((l) => candidateIds.has(endpointId(l.source)) && candidateIds.has(endpointId(l.target)))
      .map((l) => ({
        source: endpointId(l.source),
        target: endpointId(l.target),
        relation: l.relation,
        weight: l.weight,
      }));

    // Beräkna inkommande, utgående och viktad grad dynamiskt för aktuellt perspektiv!
    const inCount = new Map<string, number>();
    const outCount = new Map<string, number>();
    const weightSum = new Map<string, number>();
    for (const l of links) {
      outCount.set(l.source, (outCount.get(l.source) ?? 0) + 1);
      inCount.set(l.target, (inCount.get(l.target) ?? 0) + 1);
      const w = l.weight || 1;
      weightSum.set(l.source, (weightSum.get(l.source) ?? 0) + w);
      weightSum.set(l.target, (weightSum.get(l.target) ?? 0) + w);
    }

    const nodes = rawData.nodes
      .filter((n) => candidateIds.has(n.id))
      .map(({ x: _x, y: _y, z: _z, ...rest }) => {
        const actIn = inCount.get(rest.id) ?? 0;
        const actOut = outCount.get(rest.id) ?? 0;
        const actDeg = actIn + actOut;
        const actWeight = weightSum.get(rest.id) ?? 0.5;

        // I 3D är klotets radie kubikroten ur val (r = cbrt(val) * nodeRelSize).
        // Genom att kubera önskad radie får vi en tydlig och rättvis visuell storleksskillnad
        // mellan noder med få kopplingar (t.ex. 1) och centrala nav (t.ex. 15–37 kopplingar)!
        const r3d = weightByDegree
          ? 2.4 + Math.pow(actWeight, 0.58) * 1.95
          : 4.5;
        const r2d = weightByDegree
          ? 4.0 + Math.pow(actWeight, 0.56) * 2.9
          : 7.5;
        const dynamicVal = is3D ? Math.pow(r3d / 2.2, 3) : Math.pow(r2d, 2);

        return {
          ...rest,
          val: dynamicVal,
          activeIn: actIn,
          activeOut: actOut,
          activeDegree: actDeg,
          activeWeight: Math.round(actWeight * 10) / 10,
          radius3D: r3d,
          radius2D: r2d,
        };
      });

    return { nodes, links };
  }, [rawData, activePerspective, hiddenTypes, egoCenterId, searchQuery, is3D, weightByDegree]);

  // Ge lite mer utrymme mellan stora viktade klot i 3D så allt är lättklickat
  useEffect(() => {
    if (is3D && fg3dRef.current) {
      const charge = fg3dRef.current.d3Force?.('charge');
      if (charge?.strength) {
        charge.strength(-155);
      }
    }
  }, [is3D, filteredGraph]);

  const selectedNode = useMemo(() => {
    if (!rawData || !selectedNodeId) return null;
    return (
      filteredGraph.nodes.find((n) => n.id === selectedNodeId) ??
      rawData.nodes.find((n) => n.id === selectedNodeId) ??
      null
    );
  }, [rawData, filteredGraph.nodes, selectedNodeId]);

  const selectedRelations = useMemo(() => {
    if (!rawData || !selectedNodeId) return { outgoing: [], incoming: [] };
    const nodeById = new Map(rawData.nodes.map((n) => [n.id, n]));
    const outgoing: { relation: string; other: GraphNode }[] = [];
    const incoming: { relation: string; other: GraphNode }[] = [];

    for (const l of rawData.links) {
      const s = endpointId(l.source);
      const t = endpointId(l.target);
      if (s === selectedNodeId && nodeById.has(t)) {
        outgoing.push({ relation: l.relation, other: nodeById.get(t)! });
      } else if (t === selectedNodeId && nodeById.has(s)) {
        incoming.push({ relation: l.relation, other: nodeById.get(s)! });
      }
    }
    return { outgoing, incoming };
  }, [rawData, selectedNodeId]);

  const handleSelectAndFocusNode = useCallback(
    (node: GraphNode) => {
      setSelectedNodeId(node.id);
      // Öppna alltid högerkolumnen när användaren klickar på ett objekt för att läsa om det!
      setRightOpen(true);
      requestAnimationFrame(() => {
        inspectorRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
      });

      if (
        is3D &&
        fg3dRef.current &&
        typeof node.x === 'number' &&
        typeof node.y === 'number' &&
        typeof node.z === 'number'
      ) {
        const cam = fg3dRef.current.camera?.();
        const nx = node.x;
        const ny = node.y;
        const nz = node.z;
        let dx = (cam?.position?.x ?? 0) - nx;
        let dy = (cam?.position?.y ?? 0) - ny;
        let dz = (cam?.position?.z ?? 240) - nz;
        const len = Math.hypot(dx, dy, dz) || 1;
        dx /= len;
        dy /= len;
        dz /= len;
        const viewDistance = Math.max(130, (node.radius3D ?? 5) * 11);
        fg3dRef.current.cameraPosition(
          {
            x: nx + dx * viewDistance,
            y: ny + dy * viewDistance,
            z: nz + dz * viewDistance,
          },
          { x: nx, y: ny, z: nz },
          800
        );
      } else if (!is3D && fg2dRef.current && typeof node.x === 'number' && typeof node.y === 'number') {
        fg2dRef.current.centerAt(node.x, node.y, 650);
        fg2dRef.current.zoom(2.4, 650);
      }
    },
    [is3D]
  );

  const toggleNodeType = (t: string) => {
    setHiddenTypes((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });
  };

  const resetView = () => {
    setEgoCenterId(null);
    setSearchQuery('');
    setHiddenTypes(new Set());
    const activeRef = is3D ? fg3dRef.current : fg2dRef.current;
    if (activeRef?.zoomToFit) {
      activeRef.zoomToFit(600, 70);
    }
  };

  return (
    <div className="app-shell" style={{ cursor: hoveredNodeId ? 'pointer' : 'default' }}>
      {/* Topbar */}
      <header className="topbar">
        <div className="brand">
          <div className="brand-badge" />
          <div>
            <h1>Svenskt Totalförsvar & NATO – Kunskapsgraf</h1>
            <span>
              {filteredGraph.nodes.length} noder • {filteredGraph.links.length} relationer • Klicka på en nod för att läsa mer
            </span>
          </div>
        </div>

        <div className="controls-row">
          <div className="search-box">
            <Search size={15} color="#94a3b8" />
            <input
              id="graph-search"
              name="graph-search"
              type="text"
              placeholder="Sök myndighet, sektor, MSB, KTH, NCRS, SFS..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <select
            id="dag-layout"
            name="dag-layout"
            value={dagMode}
            onChange={(e) => setDagMode(e.target.value as DagLayout)}
            title="Välj graf-layout"
          >
            <option value="">Layout: Fri nätverksfysik</option>
            <option value="radialout">Layout: Koncentriska ringar (Radial)</option>
            <option value="td">Layout: Hierarki (Uppifrån-ner)</option>
            <option value="lr">Layout: Flöde (Vänster-höger)</option>
          </select>

          <button
            className={`btn ${weightByDegree ? 'active' : ''}`}
            onClick={() => setWeightByDegree((w) => !w)}
            title="Vikta nodernas storlek efter antal in- och utgående kopplingar"
          >
            <Scale size={14} /> {weightByDegree ? 'Viktad storlek' : 'Jämn storlek'}
          </button>

          <button
            className={`btn ${is3D ? 'active' : ''}`}
            onClick={() => setIs3D(true)}
            title="3D Force Graph (WebGL)"
          >
            <Box size={14} /> 3D
          </button>
          <button
            className={`btn ${!is3D ? 'active' : ''}`}
            onClick={() => setIs3D(false)}
            title="2D Force Graph"
          >
            <Share2 size={14} /> 2D
          </button>

          <button className="btn" onClick={resetView} title="Återställ filter & zoom">
            <RotateCcw size={14} /> Återställ
          </button>
        </div>
      </header>

      {/* Vänsterkolumn: utfällbar / infällbar */}
      {!leftOpen ? (
        <button
          className="drawer-toggle-left"
          onClick={() => setLeftOpen(true)}
          title="Fäll ut vänsterkolumn (Perspektiv & Filter)"
        >
          <PanelLeftOpen size={16} />
          <span>Perspektiv & Filter</span>
        </button>
      ) : (
        <aside className="perspective-bar">
          <div className="panel-header">
            <div className="section-label">
              <Compass size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />
              Välj Perspektiv
            </div>
            <button
              className="icon-btn"
              onClick={() => setLeftOpen(false)}
              title="Fäll in vänsterkolumn"
              aria-label="Fäll in vänsterkolumn"
            >
              <PanelLeftClose size={15} />
            </button>
          </div>

          {rawData?.perspectives.map((p) => (
            <button
              key={p.id}
              className={`persp-btn ${activePerspective === p.id && !egoCenterId ? 'active' : ''}`}
              onClick={() => {
                setEgoCenterId(null);
                setActivePerspective(p.id);
              }}
            >
              <strong>{p.title}</strong>
              <small>{p.description}</small>
            </button>
          ))}

          <div className="section-label" style={{ marginTop: 10 }}>
            <Layers size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />
            Filtrera Nodtyper (Klicka)
          </div>
          <div className="legend-list">
            {rawData &&
              Object.entries(rawData.nodeTypes).map(([typeKey, cfg]) => (
                <div
                  key={typeKey}
                  className={`legend-item ${hiddenTypes.has(typeKey) ? 'muted' : ''}`}
                  onClick={() => toggleNodeType(typeKey)}
                >
                  <span className="legend-dot" style={{ background: cfg.color }} />
                  <span>{cfg.label_sv}</span>
                </div>
              ))}
          </div>
        </aside>
      )}

      {/* Högerkolumn: utfällbar / infällbar – öppnas automatiskt vid klick på nod */}
      {selectedNode && !rightOpen && (
        <button
          className="drawer-toggle-right"
          onClick={() => setRightOpen(true)}
          title="Fäll ut högerkolumn (Detaljpanel)"
        >
          <PanelRightOpen size={16} />
          <span className="legend-dot" style={{ background: selectedNode.color }} />
          <span className="truncate">{selectedNode.shortName}</span>
        </button>
      )}

      {selectedNode && rightOpen && (
        <aside className="inspector" ref={inspectorRef}>
          <div className="panel-header">
            <div className="type-pill">
              <span className="legend-dot" style={{ background: selectedNode.color }} />
              {selectedNode.typeLabel}
            </div>
            <button
              className="icon-btn"
              onClick={() => setRightOpen(false)}
              title="Fäll in högerkolumn"
              aria-label="Fäll in högerkolumn"
            >
              <PanelRightClose size={15} />
            </button>
          </div>

          <h2>{selectedNode.name}</h2>
          {selectedNode.aliases.length > 0 && (
            <div style={{ fontSize: '0.73rem', color: '#94a3b8', marginBottom: 4 }}>
              Tidigare / Alias: {selectedNode.aliases.join(', ')}
            </div>
          )}

          {/* Kopplings- och viktstatistik */}
          <div className="metrics-grid">
            <div className="metric-card" title="Totalt antal kopplingar till och från enheten">
              <strong>{selectedRelations.incoming.length + selectedRelations.outgoing.length}</strong>
              <span>Kopplingar totalt</span>
            </div>
            <div className="metric-card" title="Antal relationer som pekar in mot enheten">
              <strong>← {selectedRelations.incoming.length}</strong>
              <span>Inkommande</span>
            </div>
            <div className="metric-card" title="Antal relationer som utgår från enheten">
              <strong>→ {selectedRelations.outgoing.length}</strong>
              <span>Utgående</span>
            </div>
          </div>

          <p>{selectedNode.description}</p>

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              className={`btn ${egoCenterId === selectedNode.id ? 'active' : ''}`}
              onClick={() =>
                setEgoCenterId((prev) => (prev === selectedNode.id ? null : selectedNode.id))
              }
            >
              <Focus size={14} />
              {egoCenterId === selectedNode.id ? 'Visa hela perspektivet' : 'Fokusera grannskap (2 hopp)'}
            </button>

            {selectedNode.url && (
              <a
                className="btn"
                href={selectedNode.url}
                target="_blank"
                rel="noreferrer"
                style={{ textDecoration: 'none' }}
              >
                <ExternalLink size={14} /> Officiell källa
              </a>
            )}
          </div>

          {selectedRelations.outgoing.length > 0 && (
            <div className="rel-group">
              <div className="section-label">Utgående kopplingar ({selectedRelations.outgoing.length})</div>
              {selectedRelations.outgoing.map((item, idx) => (
                <div
                  key={`out-${idx}`}
                  className="rel-item"
                  onClick={() => {
                    const live = filteredGraph.nodes.find((n) => n.id === item.other.id) ?? item.other;
                    handleSelectAndFocusNode(live);
                  }}
                >
                  <span className="rel-tag">→ {item.relation}</span>
                  <strong>{item.other.shortName}</strong>
                </div>
              ))}
            </div>
          )}

          {selectedRelations.incoming.length > 0 && (
            <div className="rel-group">
              <div className="section-label">Inkommande kopplingar ({selectedRelations.incoming.length})</div>
              {selectedRelations.incoming.map((item, idx) => (
                <div
                  key={`in-${idx}`}
                  className="rel-item"
                  onClick={() => {
                    const live = filteredGraph.nodes.find((n) => n.id === item.other.id) ?? item.other;
                    handleSelectAndFocusNode(live);
                  }}
                >
                  <span className="rel-tag">← {item.relation}</span>
                  <strong>{item.other.shortName}</strong>
                </div>
              ))}
            </div>
          )}
        </aside>
      )}

      <div className="hint-banner">
        {is3D
          ? 'Klicka på ett klot för att läsa om enheten • Vänsterdrag: rotera • Scroll: zooma • Högerdrag: panorera'
          : 'Klicka på en cirkel för att läsa om enheten • Dra: panorera • Scroll: zooma'}
      </div>

      {/* Huvudcanvas: react-force-graph 2D eller 3D */}
      {rawData && !is3D && (
        <ForceGraph2D
          ref={fg2dRef}
          width={dimensions.width}
          height={dimensions.height}
          backgroundColor="#070b14"
          graphData={filteredGraph}
          dagMode={dagMode || undefined}
          dagLevelDistance={95}
          onDagError={() => true}
          nodeRelSize={1}
          nodeVal={(n) => (n as GraphNode).val}
          nodeColor={(n) => (n as GraphNode).color}
          nodeLabel={(n) => {
            const g = n as GraphNode;
            return `${g.name} (${g.typeLabel}) — ${g.activeDegree ?? g.degree} kopplingar (←${g.activeIn ?? 0} / →${g.activeOut ?? 0})`;
          }}
          linkColor={() => 'rgba(148, 163, 184, 0.28)'}
          linkWidth={(l) => Math.max(0.8, ((l as GraphLink).weight || 1) * 0.65)}
          linkDirectionalArrowLength={4}
          linkDirectionalArrowRelPos={1}
          linkLabel={(l) => (l as GraphLink).relation}
          onNodeHover={(n) => setHoveredNodeId(n ? (n as GraphNode).id : null)}
          onNodeClick={(n) => handleSelectAndFocusNode(n as GraphNode)}
          nodeCanvasObject={(node, ctx, globalScale) => {
            const gNode = node as GraphNode;
            const r = gNode.radius2D ?? 6;
            const isSelected = gNode.id === selectedNodeId;
            const isHovered = gNode.id === hoveredNodeId;

            ctx.beginPath();
            ctx.arc(gNode.x || 0, gNode.y || 0, r, 0, 2 * Math.PI, false);
            ctx.fillStyle = gNode.color;
            ctx.fill();

            if (isSelected || isHovered) {
              ctx.lineWidth = (isSelected ? 2.8 : 1.8) / globalScale;
              ctx.strokeStyle = '#ffffff';
              ctx.stroke();
            }

            if (globalScale >= 0.85 || (gNode.activeDegree ?? 0) >= 5 || isSelected || isHovered) {
              const fontSize = Math.max(10 / globalScale, Math.min(13 / globalScale, 4.5));
              ctx.font = `${isSelected || (gNode.activeDegree ?? 0) >= 8 ? '600' : '400'} ${fontSize}px Inter, sans-serif`;
              ctx.textAlign = 'center';
              ctx.textBaseline = 'top';
              ctx.fillStyle = isSelected ? '#ffffff' : 'rgba(241, 245, 249, 0.92)';
              ctx.fillText(gNode.shortName, gNode.x || 0, (gNode.y || 0) + r + 2 / globalScale);
            }
          }}
        />
      )}

      {rawData && is3D && (
        <ForceGraph3D
          ref={fg3dRef}
          width={dimensions.width}
          height={dimensions.height}
          backgroundColor="#070b14"
          graphData={filteredGraph}
          dagMode={dagMode || undefined}
          dagLevelDistance={85}
          onDagError={() => true}
          showNavInfo={false}
          nodeRelSize={2.2}
          nodeResolution={20}
          nodeOpacity={0.92}
          nodeVal={(n) => (n as GraphNode).val}
          nodeColor={(n) => {
            const g = n as GraphNode;
            if (g.id === selectedNodeId) return '#ffffff';
            return g.color;
          }}
          nodeLabel={(n) => {
            const g = n as GraphNode;
            return `${g.name} • ${g.activeDegree ?? g.degree} kopplingar (←${g.activeIn ?? 0} in / →${g.activeOut ?? 0} ut)`;
          }}
          linkColor={() => 'rgba(148, 163, 184, 0.38)'}
          linkWidth={(l) => Math.max(0.5, ((l as GraphLink).weight || 1) * 0.5)}
          linkDirectionalParticles={1}
          linkDirectionalParticleWidth={1.6}
          linkLabel={(l) => (l as GraphLink).relation}
          onNodeHover={(n) => setHoveredNodeId(n ? (n as GraphNode).id : null)}
          onNodeClick={(n) => handleSelectAndFocusNode(n as GraphNode)}
          nodeThreeObjectExtend={true}
          nodeThreeObject={(node) => {
            const gNode = node as GraphNode;
            const sprite = new SpriteText(gNode.shortName);
            // Släpp igenom musklick rakt till 3D-klotet bakom textetiketten så att klick aldrig missar!
            sprite.raycast = () => {};
            sprite.color = gNode.id === selectedNodeId ? '#ffffff' : gNode.color;
            const r3d = gNode.radius3D ?? 4.5;
            sprite.textHeight = Math.max(2.4, Math.min(5.8, r3d * 0.42));
            sprite.position.y = -(r3d + 3.8);
            return sprite;
          }}
        />
      )}
    </div>
  );
}
