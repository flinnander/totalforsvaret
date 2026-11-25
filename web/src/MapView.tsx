import React, { useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Download, KeyRound, Layers } from 'lucide-react';

export interface GeoInfo {
  city: string;
  lat: number;
  lon: number;
  precision: string;
}

export interface MapGraphNode {
  id: string;
  name: string;
  shortName: string;
  type: string;
  typeLabel: string;
  color: string;
  iconUrl?: string | null;
  geo?: GeoInfo | null;
  activeDegree?: number;
  activeIn?: number;
  activeOut?: number;
  radius2D?: number;
}

export interface MapGraphLink {
  source: string | MapGraphNode;
  target: string | MapGraphNode;
  relation: string;
  weight: number;
}

interface MapViewProps {
  nodes: MapGraphNode[];
  links: MapGraphLink[];
  selectedNodeId: string | null;
  onSelectNode: (node: MapGraphNode) => void;
}

type BaseLayerStyle = 'dark' | 'satellite' | 'light';

const DARK_GOOGLE_MAP_STYLE = [
  { elementType: 'geometry', stylers: [{ color: '#0f172a' }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: '#0f172a' }] },
  { elementType: 'labels.text.fill', stylers: [{ color: '#94a3b8' }] },
  { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#020617' }] },
  { featureType: 'administrative', elementType: 'geometry.stroke', stylers: [{ color: '#334155' }] },
  { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#1e293b' }] },
];

function endId(x: string | MapGraphNode): string {
  return typeof x === 'string' ? x : x.id;
}

// Deklarera minimal typ för window.google så vi inte behöver extra typ-paket
declare global {
  interface Window {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    google?: any;
  }
}

export default function MapView({ nodes, links, selectedNodeId, onSelectNode }: MapViewProps) {
  const envKey = (import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string | undefined) ?? '';
  const [googleApiKey, setGoogleApiKey] = useState<string>(
    () => localStorage.getItem('tf_google_maps_key') || envKey
  );
  const [googleReady, setGoogleReady] = useState<boolean>(false);
  const [showKeyModal, setShowKeyModal] = useState<boolean>(false);
  const [draftKey, setDraftKey] = useState<string>(googleApiKey);
  const [baseStyle, setBaseStyle] = useState<BaseLayerStyle>('dark');
  const [showLinksOnMap, setShowLinksOnMap] = useState<boolean>(true);

  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const leafletMapRef = useRef<L.Map | null>(null);
  const leafletLayerGroupRef = useRef<L.LayerGroup | null>(null);
  const leafletTileRef = useRef<L.TileLayer | null>(null);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const gMapRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const gOverlaysRef = useRef<any[]>([]);

  const geoNodes = useMemo(() => nodes.filter((n) => n.geo && typeof n.geo.lat === 'number'), [nodes]);
  const geoNodeById = useMemo(() => new Map(geoNodes.map((n) => [n.id, n])), [geoNodes]);

  const geoLinks = useMemo(() => {
    if (!showLinksOnMap) return [];
    return links
      .map((l) => {
        const s = geoNodeById.get(endId(l.source));
        const t = geoNodeById.get(endId(l.target));
        if (!s || !t || s.id === t.id) return null;
        return { s, t, relation: l.relation, weight: l.weight };
      })
      .filter((x): x is NonNullable<typeof x> => x !== null);
  }, [links, geoNodeById, showLinksOnMap]);

  // Ladda Google Maps JS API dynamiskt om användaren angivit en API-nyckel
  useEffect(() => {
    if (!googleApiKey.trim()) {
      setGoogleReady(false);
      return;
    }
    if (window.google?.maps) {
      setGoogleReady(true);
      return;
    }
    const existing = document.getElementById('google-maps-sdk');
    if (existing) existing.remove();

    const script = document.createElement('script');
    script.id = 'google-maps-sdk';
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(googleApiKey.trim())}`;
    script.async = true;
    script.onload = () => setGoogleReady(Boolean(window.google?.maps));
    script.onerror = () => {
      console.error('Kunde inte ladda Google Maps JS API – faller tillbaka till inbyggd karta.');
      setGoogleReady(false);
    };
    document.head.appendChild(script);
  }, [googleApiKey]);

  const useGoogleMaps = Boolean(googleApiKey.trim() && googleReady && window.google?.maps);

  // =========================================================================
  // LÄGE A: Native Google Maps JS API (när API-nyckel finns)
  // =========================================================================
  useEffect(() => {
    if (!useGoogleMaps || !mapContainerRef.current) return;

    // Städa bort eventuell Leaflet-instans
    if (leafletMapRef.current) {
      leafletMapRef.current.remove();
      leafletMapRef.current = null;
      leafletLayerGroupRef.current = null;
      leafletTileRef.current = null;
    }

    const gmaps = window.google.maps;
    if (!gMapRef.current) {
      gMapRef.current = new gmaps.Map(mapContainerRef.current, {
        center: { lat: 60.4, lng: 16.2 },
        zoom: 5,
        mapTypeId: baseStyle === 'satellite' ? 'hybrid' : 'roadmap',
        styles: baseStyle === 'dark' ? DARK_GOOGLE_MAP_STYLE : [],
        disableDefaultUI: false,
        streetViewControl: false,
        fullscreenControl: false,
      });
    } else {
      gMapRef.current.setMapTypeId(baseStyle === 'satellite' ? 'hybrid' : 'roadmap');
      gMapRef.current.setOptions({ styles: baseStyle === 'dark' ? DARK_GOOGLE_MAP_STYLE : [] });
    }

    // Rensa tidigare markörer/linjer
    gOverlaysRef.current.forEach((ov) => ov.setMap(null));
    gOverlaysRef.current = [];

    for (const gl of geoLinks) {
      const isRegional =
        gl.relation.includes('CIVILOMRADE') || gl.relation.includes('REGIONAL');
      const line = new gmaps.Polyline({
        path: [
          { lat: gl.s.geo!.lat, lng: gl.s.geo!.lon },
          { lat: gl.t.geo!.lat, lng: gl.t.geo!.lon },
        ],
        geodesic: true,
        strokeColor: isRegional ? gl.t.color : '#64748b',
        strokeOpacity: isRegional ? 0.72 : 0.24,
        strokeWeight: isRegional ? 2.2 : 1.0,
        map: gMapRef.current,
      });
      gOverlaysRef.current.push(line);
    }

    for (const n of geoNodes) {
      const sz = Math.round(Math.max(24, Math.min(48, (n.radius2D ?? 8) * 3.2)));
      const marker = new gmaps.Marker({
        position: { lat: n.geo!.lat, lng: n.geo!.lon },
        map: gMapRef.current,
        title: `${n.name} (${n.geo!.city})`,
        icon: n.iconUrl
          ? {
              url: n.iconUrl,
              scaledSize: new gmaps.Size(sz, sz),
              anchor: new gmaps.Point(sz / 2, sz / 2),
            }
          : undefined,
        zIndex: n.id === selectedNodeId ? 1000 : sz,
      });
      marker.addListener('click', () => onSelectNode(n));
      gOverlaysRef.current.push(marker);
    }
  }, [useGoogleMaps, geoNodes, geoLinks, baseStyle, selectedNodeId, onSelectNode]);

  // =========================================================================
  // LÄGE B: Zero-Config Interaktiv Karta (fungerar direkt utan API-nyckel!)
  // =========================================================================
  useEffect(() => {
    if (useGoogleMaps || !mapContainerRef.current) return;

    gMapRef.current = null;

    if (!leafletMapRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: [61.2, 16.2],
        zoom: 5,
        zoomControl: false,
      });
      L.control.zoom({ position: 'bottomright' }).addTo(map);
      leafletMapRef.current = map;
      leafletLayerGroupRef.current = L.layerGroup().addTo(map);
    }

    const tileUrls: Record<BaseLayerStyle, { url: string; attribution: string }> = {
      dark: {
        url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
        attribution: '&copy; OpenStreetMap &copy; CARTO',
      },
      light: {
        url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
        attribution: '&copy; OpenStreetMap &copy; CARTO',
      },
      satellite: {
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attribution: '&copy; Esri World Imagery',
      },
    };

    if (leafletTileRef.current) {
      leafletTileRef.current.remove();
    }
    const chosen = tileUrls[baseStyle];
    leafletTileRef.current = L.tileLayer(chosen.url, {
      attribution: chosen.attribution,
      maxZoom: 18,
    }).addTo(leafletMapRef.current);

    const group = leafletLayerGroupRef.current!;
    group.clearLayers();

    // 1. Kopplingslinjer (t.ex. Civilområde -> Län, Militärregion -> Civilområde, Sektor -> Myndighet)
    for (const gl of geoLinks) {
      const isRegional =
        gl.relation.includes('CIVILOMRADE') || gl.relation.includes('REGIONAL');
      L.polyline(
        [
          [gl.s.geo!.lat, gl.s.geo!.lon],
          [gl.t.geo!.lat, gl.t.geo!.lon],
        ],
        {
          color: isRegional ? gl.t.color : '#64748b',
          weight: isRegional ? 2.4 : 1.1,
          opacity: isRegional ? 0.78 : 0.25,
          dashArray: gl.relation === 'SAMVERKAR_REGIONAL_MED' ? '5, 5' : undefined,
        }
      )
        .bindTooltip(`${gl.s.shortName} → ${gl.relation} → ${gl.t.shortName}`, { sticky: true })
        .addTo(group);
    }

    // 2. Heraldiska vapen / logotyp-markörer viktade efter nodens kopplingsgrad
    for (const n of geoNodes) {
      const sz = Math.round(Math.max(24, Math.min(48, (n.radius2D ?? 8) * 3.1)));
      const isSelected = n.id === selectedNodeId;
      const border = isSelected ? `3px solid #ffffff` : `2px solid ${n.color}`;
      const shadow = isSelected ? `0 0 16px #ffffff` : `0 2px 8px rgba(0,0,0,0.65)`;

      const htmlIcon = L.divIcon({
        className: 'tf-map-marker',
        iconSize: [sz, sz],
        iconAnchor: [sz / 2, sz / 2],
        html: `<div style="
          width:${sz}px;
          height:${sz}px;
          border-radius:50%;
          background:rgba(15,23,42,0.92);
          border:${border};
          box-shadow:${shadow};
          display:flex;
          align-items:center;
          justify-content:center;
          overflow:hidden;
          padding:2px;
        ">
          ${
            n.iconUrl
              ? `<img src="${n.iconUrl}" alt="" style="width:100%;height:100%;object-fit:contain;" />`
              : `<span style="width:65%;height:65%;border-radius:50%;background:${n.color};display:block;"></span>`
          }
        </div>`,
      });

      L.marker([n.geo!.lat, n.geo!.lon], {
        icon: htmlIcon,
        zIndexOffset: isSelected ? 1000 : sz,
      })
        .bindTooltip(
          `<strong>${n.name}</strong><br/>Sätesort: ${n.geo!.city} • ${n.activeDegree ?? 0} kopplingar`,
          { direction: 'top', offset: [0, -sz / 2] }
        )
        .on('click', () => onSelectNode(n))
        .addTo(group);
    }
  }, [useGoogleMaps, geoNodes, geoLinks, baseStyle, selectedNodeId, onSelectNode]);

  // Panorera till vald nod när selectedNodeId ändras
  useEffect(() => {
    if (!selectedNodeId) return;
    const n = geoNodeById.get(selectedNodeId);
    if (!n?.geo) return;
    if (useGoogleMaps && gMapRef.current) {
      gMapRef.current.panTo({ lat: n.geo.lat, lng: n.geo.lon });
    } else if (!useGoogleMaps && leafletMapRef.current) {
      leafletMapRef.current.panTo([n.geo.lat, n.geo.lon], { animate: true });
    }
  }, [selectedNodeId, geoNodeById, useGoogleMaps]);

  useEffect(() => {
    return () => {
      if (leafletMapRef.current) {
        leafletMapRef.current.remove();
        leafletMapRef.current = null;
      }
    };
  }, []);

  const saveGoogleKey = () => {
    const trimmed = draftKey.trim();
    if (trimmed) {
      localStorage.setItem('tf_google_maps_key', trimmed);
    } else {
      localStorage.removeItem('tf_google_maps_key');
    }
    setGoogleApiKey(trimmed);
    setShowKeyModal(false);
  };

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <div ref={mapContainerRef} style={{ width: '100%', height: '100%' }} />

      {/* Flytande kartverktygsrad nere till vänster */}
      <div className="map-toolbar">
        <button
          className={`btn ${baseStyle === 'dark' ? 'active' : ''}`}
          onClick={() => setBaseStyle('dark')}
        >
          Mörk karta
        </button>
        <button
          className={`btn ${baseStyle === 'satellite' ? 'active' : ''}`}
          onClick={() => setBaseStyle('satellite')}
        >
          Satellit
        </button>
        <button
          className={`btn ${baseStyle === 'light' ? 'active' : ''}`}
          onClick={() => setBaseStyle('light')}
        >
          Ljus karta
        </button>
        <button
          className={`btn ${showLinksOnMap ? 'active' : ''}`}
          onClick={() => setShowLinksOnMap((v) => !v)}
          title="Visa/dölj regionala och organisatoriska kopplingslinjer på kartan"
        >
          <Layers size={14} /> Kopplingslinjer
        </button>
        <a
          className="btn"
          href="./data/totalforsvaret.kml"
          download="totalforsvaret.kml"
          style={{ textDecoration: 'none' }}
          title="Ladda ner KML-fil för import direkt i Google My Maps eller Google Earth"
        >
          <Download size={14} /> Google Earth / My Maps (.kml)
        </a>
        <button
          className={`btn ${useGoogleMaps ? 'active' : ''}`}
          onClick={() => {
            setDraftKey(googleApiKey);
            setShowKeyModal((s) => !s);
          }}
          title="Anslut egen Google Maps JavaScript API-nyckel"
        >
          <KeyRound size={14} />
          {useGoogleMaps ? 'Google Maps JS aktiv' : 'Google Maps API-nyckel'}
        </button>
      </div>

      {showKeyModal && (
        <div className="map-key-modal">
          <strong>Google Maps JavaScript API-nyckel (valfritt)</strong>
          <p>
            Kartan fungerar direkt utan nyckel, men anger du en <code>Google Maps API Key</code> växlar vyn automatiskt till native Google Maps JS (sparas endast i din webbläsares localStorage).
          </p>
          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
            <input
              type="password"
              placeholder="AIzaSy..."
              value={draftKey}
              onChange={(e) => setDraftKey(e.target.value)}
              style={{
                flex: 1,
                background: '#020617',
                border: '1px solid rgba(148,163,184,0.3)',
                borderRadius: 6,
                padding: '6px 10px',
                color: '#f8fafc',
              }}
            />
            <button className="btn active" onClick={saveGoogleKey}>
              Spara
            </button>
            <button className="btn" onClick={() => setShowKeyModal(false)}>
              Stäng
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
