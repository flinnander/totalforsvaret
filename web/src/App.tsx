import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import ForceGraph3D from 'react-force-graph-3d';
import * as THREE from 'three';
import SpriteText from 'three-spritetext';
import {
  Box,
  CheckSquare,
  Compass,
  ExternalLink,
  Focus,
  Layers,
  Map as MapIcon,
  MapPin,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  RotateCcw,
  Scale,
  Search,
  Share2,
} from 'lucide-react';
import MapView, { GeoInfo } from './MapView';

interface GraphNode {
  id: string;
  name: string;
  shortName: string;
  type: string;
  typeLabel: string;
  sourceGroup: string;
  sourceGroupTitle: string;
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
  iconUrl?: string | null;
  geo?: GeoInfo | null;
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

interface SourceGroupConfig {
  id: string;
  title: string;
  shortTitle: string;
  description: string;
  color: string;
  defaultEnabled: boolean;
}

interface Perspective {
  id: string;
  title: string;
  description: string;
  source_groups?: string[];
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
  sourceGroups: SourceGroupConfig[];
  perspectives: Perspective[];
  nodeTypes: Record<string, { color: string; val: number; label_sv: string }>;
  nodes: GraphNode[];
  links: GraphLink[];
}

type ViewMode = '3d' | '2d' | 'map';
type DagLayout = '' | 'radialout' | 'td' | 'lr';

// Modulglobala textur- och bildcachar för 60 FPS utan omladdningar
const threeTextureCache = new Map<string, THREE.Texture>();
const textureLoader = new THREE.TextureLoader();

function getThreeTexture(url: string): THREE.Texture {
  let tex = threeTextureCache.get(url);
  if (!tex) {
    tex = textureLoader.load(url);
    tex.colorSpace = THREE.SRGBColorSpace;
    threeTextureCache.set(url, tex);
  }
  return tex;
}

const image2dCache = new Map<string, HTMLImageElement>();
function get2dImage(url: string): HTMLImageElement {
  let img = image2dCache.get(url);
  if (!img) {
    img = new Image();
    img.src = url;
    image2dCache.set(url, img);
  }
  return img;
}

function endpointId(end: string | GraphNode): string {
  return typeof end === 'string' ? end : end.id;
}

export default function App() {
  const [rawData, setRawData] = useState<ForceGraphPayload | null>(null);
  // 3D är standardvy!
  const [viewMode, setViewMode] = useState<ViewMode>('3d');
  const [enabledGroups, setEnabledGroups] = useState<Set<string>>(new Set());
  const [showEmblems, setShowEmblems] = useState<boolean>(true);
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
      .then((data: ForceGraphPayload) => {
        setRawData(data);
        setEnabledGroups(new Set(data.sourceGroups.map((g) => g.id)));
      })
      .catch((err) => console.error('Kunde inte ladda force_graph.json:', err));
  }, []);

  // Antal noder per källgrupp (för tydliga räknare i vänsterpanelen)
  const groupCounts = useMemo(() => {
    const counts = new Map<string, number>();
    if (!rawData) return counts;
    for (const n of rawData.nodes) {
      counts.set(n.sourceGroup, (counts.get(n.sourceGroup) ?? 0) + 1);
    }
    return counts;
  }, [rawData]);

  const filteredGraph = useMemo(() => {
    if (!rawData) return { nodes: [] as GraphNode[], links: [] as GraphLink[] };

    let candidateIds = new Set(
      rawData.nodes
        .filter((n) => enabledGroups.has(n.sourceGroup) && !hiddenTypes.has(n.type))
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
        const cityStr = n.geo?.city ?? '';
        const hay = `${n.name} ${n.shortName} ${cityStr} ${n.description} ${n.aliases.join(' ')}`.toLowerCase();
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

    const is3D = viewMode === '3d';
    const nodes = rawData.nodes
      .filter((n) => candidateIds.has(n.id))
      .map(({ x: _x, y: _y, z: _z, ...rest }) => {
        const actIn = inCount.get(rest.id) ?? 0;
        const actOut = outCount.get(rest.id) ?? 0;
        const actDeg = actIn + actOut;
        const actWeight = weightSum.get(rest.id) ?? 0.5;

        const r3d = weightByDegree ? 2.8 + Math.pow(actWeight, 0.56) * 2.0 : 4.8;
        const r2d = weightByDegree ? 4.8 + Math.pow(actWeight, 0.54) * 2.9 : 8.5;
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
  }, [rawData, enabledGroups, hiddenTypes, egoCenterId, searchQuery, viewMode, weightByDegree]);

  useEffect(() => {
    if (viewMode === '3d' && fg3dRef.current) {
      const charge = fg3dRef.current.d3Force?.('charge');
      if (charge?.strength) {
        charge.strength(-175);
      }
    }
  }, [viewMode, filteredGraph]);

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
      setRightOpen(true);
      requestAnimationFrame(() => {
        inspectorRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
      });

      if (
        viewMode === '3d' &&
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
      } else if (viewMode === '2d' && fg2dRef.current && typeof node.x === 'number' && typeof node.y === 'number') {
        fg2dRef.current.centerAt(node.x, node.y, 650);
        fg2dRef.current.zoom(2.4, 650);
      }
    },
    [viewMode]
  );

  const toggleSourceGroup = (groupId: string) => {
    setEgoCenterId(null);
    setEnabledGroups((prev) => {
      const next = new Set(prev);
      if (next.has(groupId)) next.delete(groupId);
      else next.add(groupId);
      return next;
    });
  };

  const selectAllGroups = () => {
    if (!rawData) return;
    setEgoCenterId(null);
    setHiddenTypes(new Set());
    setEnabledGroups(new Set(rawData.sourceGroups.map((g) => g.id)));
  };

  const selectCoreGroupsOnly = () => {
    setEgoCenterId(null);
    setHiddenTypes(new Set());
    setEnabledGroups(
      new Set([
        'styrning_lagrum',
        'nato_allians',
        'militart_och_karnmyndigheter',
        'beredskapssektorer',
        'geografi_civilomraden',
      ])
    );
  };

  const clearAllGroups = () => {
    setEgoCenterId(null);
    setEnabledGroups(new Set());
  };

  const applyPerspectivePreset = (p: Perspective) => {
    setEgoCenterId(null);
    setHiddenTypes(new Set());
    if (p.source_groups && p.source_groups.length > 0) {
      setEnabledGroups(new Set(p.source_groups));
    } else if (rawData) {
      setEnabledGroups(new Set(rawData.sourceGroups.map((g) => g.id)));
    }
  };

  const toggleNodeType = (t: string) => {
    setHiddenTypes((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });
  };

  const resetView = () => {
    selectAllGroups();
    setSearchQuery('');
    const activeRef = viewMode === '3d' ? fg3dRef.current : fg2dRef.current;
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
            <h1>Svenskt Totalförsvar & NATO – Kunskapsgraf & Karta</h1>
            <span>
              {filteredGraph.nodes.length} enheter • {filteredGraph.links.length} relationer • Klicka på objekt för detaljer
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
              placeholder="Sök myndighet, stad, MSB, KTH, NCRS..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          {viewMode !== 'map' && (
            <select
              id="dag-layout"
              name="dag-layout"
              value={dagMode}
              onChange={(e) => setDagMode(e.target.value as DagLayout)}
              title="Välj graf-layout"
            >
              <option value="">Layout: Fri nätverksfysik</option>
              <option value="radialout">Layout: Koncentriska ringar</option>
              <option value="td">Layout: Hierarki (Uppifrån-ner)</option>
              <option value="lr">Layout: Flöde (Vänster-höger)</option>
            </select>
          )}

          <button
            className={`btn ${weightByDegree ? 'active' : ''}`}
            onClick={() => setWeightByDegree((w) => !w)}
            title="Vikta storlek efter antal kopplingar"
          >
            <Scale size={14} /> {weightByDegree ? 'Viktad' : 'Jämn'}
          </button>

          {viewMode !== 'map' && (
            <button
              className={`btn ${showEmblems ? 'active' : ''}`}
              onClick={() => setShowEmblems((s) => !s)}
              title="Visa/dölj heraldiska vapen och logotyper på planeterna"
            >
              🛡️ Vapen
            </button>
          )}

          <button
            className={`btn ${viewMode === '3d' ? 'active' : ''}`}
            onClick={() => setViewMode('3d')}
            title="3D Force Graph (WebGL)"
          >
            <Box size={14} /> 3D
          </button>
          <button
            className={`btn ${viewMode === '2d' ? 'active' : ''}`}
            onClick={() => setViewMode('2d')}
            title="2D Force Graph"
          >
            <Share2 size={14} /> 2D
          </button>
          <button
            className={`btn ${viewMode === 'map' ? 'active' : ''}`}
            onClick={() => setViewMode('map')}
            title="Geografisk vy över Sverige & Google Maps"
          >
            <MapIcon size={14} /> Karta
          </button>

          <button className="btn" onClick={resetView} title="Återställ alla källgrupper & zoom">
            <RotateCcw size={14} /> Återställ
          </button>
        </div>
      </header>

      {/* Vänsterkolumn: Källgrupper (kryssrutor) + Snabbperspektiv + Nodtyper */}
      {!leftOpen ? (
        <button
          className="drawer-toggle-left"
          onClick={() => setLeftOpen(true)}
          title="Fäll ut vänsterkolumn (Källgrupper & Perspektiv)"
        >
          <PanelLeftOpen size={16} />
          <span>Källgrupper ({enabledGroups.size}/{rawData?.sourceGroups.length ?? 7})</span>
        </button>
      ) : (
        <aside className="perspective-bar">
          <div className="panel-header">
            <div className="section-label">
              <CheckSquare size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />
              Källgrupper (Markera i / ur)
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

          <div className="preset-chips">
            <button className="btn btn-xs" onClick={selectAllGroups}>
              Alla (7)
            </button>
            <button className="btn btn-xs" onClick={selectCoreGroupsOnly} title="Dölj de 37 lärosätena och 18 FFO för renare kärnöversikt">
              Endast kärna (5)
            </button>
            <button className="btn btn-xs" onClick={clearAllGroups}>
              Töm val
            </button>
          </div>

          <div className="source-group-list">
            {rawData?.sourceGroups.map((sg) => {
              const checked = enabledGroups.has(sg.id);
              const count = groupCounts.get(sg.id) ?? 0;
              return (
                <label
                  key={sg.id}
                  className={`source-group-card ${checked ? 'checked' : 'unchecked'}`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleSourceGroup(sg.id)}
                  />
                  <div className="sg-body">
                    <div className="sg-title-row">
                      <strong style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span className="legend-dot" style={{ background: sg.color }} />
                        {sg.shortTitle}
                      </strong>
                      <span className="sg-count">{count}</span>
                    </div>
                    <small>{sg.description}</small>
                  </div>
                </label>
              );
            })}
          </div>

          <div className="section-label" style={{ marginTop: 10 }}>
            <Compass size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />
            Snabbperspektiv
          </div>
          <div className="preset-chips">
            {rawData?.perspectives.map((p) => (
              <button
                key={p.id}
                className="btn btn-xs"
                onClick={() => applyPerspectivePreset(p)}
                title={p.description}
              >
                {p.title.split('–')[0].split(':')[0].trim()}
              </button>
            ))}
          </div>

          <div className="section-label" style={{ marginTop: 10 }}>
            <Layers size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />
            Finhantera Nodtyper
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

      {/* Högerkolumn: Detaljpanel med heraldiskt vapen/logotyp & Google Maps-länk */}
      {selectedNode && !rightOpen && (
        <button
          className="drawer-toggle-right"
          onClick={() => setRightOpen(true)}
          title="Fäll ut högerkolumn (Detaljpanel)"
        >
          <PanelRightOpen size={16} />
          {selectedNode.iconUrl ? (
            <img src={selectedNode.iconUrl} alt="" style={{ width: 18, height: 18, objectFit: 'contain' }} />
          ) : (
            <span className="legend-dot" style={{ background: selectedNode.color }} />
          )}
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

          <div className="inspector-hero">
            {selectedNode.iconUrl && (
              <img
                className="inspector-crest"
                src={selectedNode.iconUrl}
                alt={selectedNode.shortName}
              />
            )}
            <div>
              <h2>{selectedNode.name}</h2>
              {selectedNode.geo && (
                <div className="city-badge">
                  <MapPin size={12} /> Sätesort: {selectedNode.geo.city}
                </div>
              )}
            </div>
          </div>

          {selectedNode.aliases.length > 0 && (
            <div style={{ fontSize: '0.73rem', color: '#94a3b8', marginBottom: 4 }}>
              Tidigare / Alias: {selectedNode.aliases.join(', ')}
            </div>
          )}

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

          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <button
              className={`btn ${egoCenterId === selectedNode.id ? 'active' : ''}`}
              onClick={() =>
                setEgoCenterId((prev) => (prev === selectedNode.id ? null : selectedNode.id))
              }
            >
              <Focus size={14} />
              {egoCenterId === selectedNode.id ? 'Visa alla valda' : 'Fokusera (2 hopp)'}
            </button>

            {selectedNode.url && (
              <a
                className="btn"
                href={selectedNode.url}
                target="_blank"
                rel="noreferrer"
                style={{ textDecoration: 'none' }}
              >
                <ExternalLink size={14} /> Källa
              </a>
            )}

            {selectedNode.geo && (
              <a
                className="btn"
                href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
                  `${selectedNode.name}, ${selectedNode.geo.city}`
                )}`}
                target="_blank"
                rel="noreferrer"
                style={{ textDecoration: 'none' }}
                title="Öppna direkt i Google Maps"
              >
                <MapPin size={14} /> Google Maps
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
                  {item.other.iconUrl && (
                    <img className="rel-mini-icon" src={item.other.iconUrl} alt="" />
                  )}
                  <div>
                    <span className="rel-tag">→ {item.relation}</span>
                    <strong>{item.other.shortName}</strong>
                  </div>
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
                  {item.other.iconUrl && (
                    <img className="rel-mini-icon" src={item.other.iconUrl} alt="" />
                  )}
                  <div>
                    <span className="rel-tag">← {item.relation}</span>
                    <strong>{item.other.shortName}</strong>
                  </div>
                </div>
              ))}
            </div>
          )}
        </aside>
      )}

      {viewMode !== 'map' && (
        <div className="hint-banner">
          {viewMode === '3d'
            ? 'Klicka på en planet/vapensköld för att läsa om enheten • Vänsterdrag: rotera • Scroll: zooma • Högerdrag: panorera'
            : 'Klicka på en enhet för att läsa mer • Dra: panorera • Scroll: zooma'}
        </div>
      )}

      {/* VY 1: Kartläge (Inbyggd Karta + Google Maps JS + KML) */}
      {rawData && viewMode === 'map' && (
        <MapView
          nodes={filteredGraph.nodes}
          links={filteredGraph.links}
          selectedNodeId={selectedNodeId}
          onSelectNode={(n) => handleSelectAndFocusNode(n as GraphNode)}
        />
      )}

      {/* VY 2: 2D Force Graph med heraldiska vapen/logotyper */}
      {rawData && viewMode === '2d' && (
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
            return `${g.name} (${g.typeLabel}) — ${g.activeDegree ?? g.degree} kopplingar`;
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
            const r = gNode.radius2D ?? 7;
            const isSelected = gNode.id === selectedNodeId;
            const isHovered = gNode.id === hoveredNodeId;
            const x = gNode.x || 0;
            const y = gNode.y || 0;

            ctx.beginPath();
            ctx.arc(x, y, r, 0, 2 * Math.PI, false);
            ctx.fillStyle = showEmblems && gNode.iconUrl ? 'rgba(15, 23, 42, 0.92)' : gNode.color;
            ctx.fill();

            ctx.lineWidth = (isSelected ? 3.0 : isHovered ? 2.2 : 1.5) / globalScale;
            ctx.strokeStyle = isSelected ? '#ffffff' : gNode.color;
            ctx.stroke();

            if (showEmblems && gNode.iconUrl) {
              const img = get2dImage(gNode.iconUrl);
              if (img.complete && img.naturalWidth > 0) {
                const box = r * 1.42;
                ctx.drawImage(img, x - box / 2, y - box / 2, box, box);
              }
            }

            if (globalScale >= 0.85 || (gNode.activeDegree ?? 0) >= 5 || isSelected || isHovered) {
              const fontSize = Math.max(10 / globalScale, Math.min(13 / globalScale, 4.5));
              ctx.font = `${isSelected || (gNode.activeDegree ?? 0) >= 8 ? '600' : '400'} ${fontSize}px Inter, sans-serif`;
              ctx.textAlign = 'center';
              ctx.textBaseline = 'top';
              ctx.fillStyle = isSelected ? '#ffffff' : 'rgba(241, 245, 249, 0.92)';
              ctx.fillText(gNode.shortName, x, y + r + 2.5 / globalScale);
            }
          }}
        />
      )}

      {/* VY 3: 3D Force Graph (Default) med heraldiska vapen inuti glödande planeter */}
      {rawData && viewMode === '3d' && (
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
          nodeOpacity={showEmblems ? 0.34 : 0.92}
          nodeVal={(n) => (n as GraphNode).val}
          nodeColor={(n) => {
            const g = n as GraphNode;
            if (g.id === selectedNodeId) return '#ffffff';
            return g.color;
          }}
          nodeLabel={(n) => {
            const g = n as GraphNode;
            const cityPart = g.geo ? ` • ${g.geo.city}` : '';
            return `${g.name}${cityPart} • ${g.activeDegree ?? g.degree} kopplingar (←${g.activeIn ?? 0} / →${g.activeOut ?? 0})`;
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
            const r3d = gNode.radius3D ?? 4.8;
            const group = new THREE.Group();

            // 1. Heraldiskt vapen / logotyp svävande i planetens kärna (billboard-sprite)
            if (showEmblems && gNode.iconUrl) {
              const tex = getThreeTexture(gNode.iconUrl);
              const mat = new THREE.SpriteMaterial({
                map: tex,
                transparent: true,
                depthWrite: false,
              });
              const crestSprite = new THREE.Sprite(mat);
              const crestSize = r3d * 1.48;
              crestSprite.scale.set(crestSize, crestSize, 1);
              crestSprite.raycast = () => {};
              group.add(crestSprite);
            }

            // 2. Namnetikett under planeten
            const label = new SpriteText(gNode.shortName);
            label.raycast = () => {};
            label.color = gNode.id === selectedNodeId ? '#ffffff' : gNode.color;
            label.textHeight = Math.max(2.4, Math.min(5.8, r3d * 0.42));
            label.position.y = -(r3d + 4.0);
            group.add(label);

            return group;
          }}
        />
      )}
    </div>
  );
}
