# Svenskt Totalförsvar – Öppen Kunskapsgraf, RAG, `react-force-graph` & MCP

Ett öppet kunskaps- och verktygsprojekt som samlar in, strukturerar och tillgängliggör **offentlig, normativ information om det svenska totalförsvaret och kopplingen till NATO** – från interaktiva 2D/3D-nätverksgrafer och översikter ner till djupaste paragraf- och regleringsbrevsdetalj.

---

## Interaktiv Visualisering med `react-force-graph` (2D & 3D)

Projektet inkluderar en interaktiv webbapplikation i [`web/`](web/) byggd med **[vasturiano/react-force-graph](https://github.com/vasturiano/react-force-graph)** (`ForceGraph2D` + `ForceGraph3D` i WebGL) där datat kan utforskas ur **6 färdiga perspektiv** och **4 graf-layouter** (*Fri nätverksfysik*, *Koncentriska ringar*, *Hierarki uppifrån-ner*, *Flöde vänster-höger*):

1. **Helhetsbild** – Hela det svenska totalförsvaret och dess kopplingar.
2. **12 Beredskapssektorer & Myndigheter** – Sektorsansvariga myndigheter och ingående beredskapsmyndigheter enligt *SFS 2022:524*.
3. **NATO, NCRS/CRM & 7 Resilienskrav** – Hur Sveriges totalförsvar och beredskapssektorer mappar mot NATO:s 7 grundkrav (Artikel 3), *NCRS/NRS* och *Värdlandsstöd (HNS)*.
4. **Geografi: 6 Civilområden, 21 Län & Kommuner** – Regional ledning via civilområdesansvariga länsstyrelser, samtliga 21 län och SKR/LEH.
5. **Styrning, Lagrum (SFS) & Regleringsbrev** – Riksdagen, Regeringen, regleringsbrev och centrala totalförsvarsförfattningar.
6. **Campus Totalförsvar (37 lärosäten), 18 FFO & Näringsliv** – Akademi, folkrörelseförankring och försörjningsberedskap.

---

## Snabbstart

### 1. Bygg kunskapsgrafen, hämta SFS-lagtexter & generera alla format
Kräver [uv](https://docs.astral.sh/uv/):
```bash
uv run totalforsvaret build
```
Detta bygger SQLite-databasen (`data/totalforsvaret.db`), hämtar centrala lagtexter från **Riksdagens Öppna Data API**, indexerar dem i `FTS5` (BM25) och exporterar:
* [`exports/graph/force_graph.json`](exports/graph/force_graph.json) & `web/public/data/force_graph.json` (för `react-force-graph`)
* [`exports/markdown/OVERSIKT_L1.md`](exports/markdown/OVERSIKT_L1.md) (med Mermaid-systemkarta)
* [`exports/markdown/BEREDSKAPSSEKTORER_L2.md`](exports/markdown/BEREDSKAPSSEKTORER_L2.md)
* [`exports/markdown/NATO_OCH_NCRS_L2.md`](exports/markdown/NATO_OCH_NCRS_L2.md)
* [`exports/markdown/CIVILOMRADEN_L2.md`](exports/markdown/CIVILOMRADEN_L2.md)
* [`exports/json/actors.json`](exports/json/actors.json) & [`exports/csv/actors.csv`](exports/csv/actors.csv)

### 2. Starta den interaktiva `react-force-graph`-utforskaren lokalt
```bash
cd web
npm install
npm run dev
```

### 3. Koppla in MCP-servern (Claude, Antigravity, Cursor, Copilot)
```json
{
  "mcpServers": {
    "totalforsvaret": {
      "command": "uv",
      "args": ["--directory", "D:/Antigravity/Totalförsvar MCP", "run", "totalforsvaret-mcp"]
    }
  }
}
```
MCP-verktyg som exponeras:
* `get_overview` *(Nivå L1 – Markdown/Mermaid eller JSON)*
* `explore_actor_or_sector` *(Nivå L2–L3 – Hanterar även alias som `MSB` → `MCF`)*
* `get_nato_mapping` *(Nivå L2–L3 – NATO Artikel 3, NCRS/CRM, HNS)*
* `get_force_graph_data` *(Genererar skräddarsydd `react-force-graph`-JSON för valfritt perspektiv eller ego-graf runt en nod)*
* `search_totalforsvar_sources` *(Nivå L4 – Sökning på paragrafnivå i SFS och källtexter)*

---

## Etik, Säkerhetsskydd & Avgränsning

> **Grundprincip:** Vi samlar in **vad kraven, rollerna och strukturerna är** – aldrig **hur väl aktörer svarar upp mot kraven eller vilka sårbarheter som finns**.

Projektet exkluderar aktivt risk- och sårbarhetsanalyser (RSA), förmågebedömningar, tillsynsbeslut om brister, återrapporteringar av måluppfyllnad samt fysiska infrastrukturdata. Se [`SECURITY_AND_SCOPE.md`](SECURITY_AND_SCOPE.md).

---

## Dokumentation

* [`config/sources.yaml`](config/sources.yaml) – Maskinläsbar masterlista över övervakade domäner, API:er, SFS-författningar och exkluderingsfilter.
* [`docs/SOURCES.md`](docs/SOURCES.md) – Översikt över de 7 källkategorierna och NATO-mappningen.
* [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) – Teknisk arkitektur (Python, SQLite Kunskapsgraf + FTS5, FastMCP och `react-force-graph`).
* [`SECURITY_AND_SCOPE.md`](SECURITY_AND_SCOPE.md) – Principer för informationssäkerhet och avgränsning.
