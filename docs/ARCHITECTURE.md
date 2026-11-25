# Teknisk Arkitektur: Från helikopterperspektiv till paragrafdetalj

Målet med `totalforsvaret` är att både människor och AI-agenter ska kunna få svar om det svenska totalförsvaret **på valfri detaljnivå** och **i valfritt format** – utan trösklar.

---

## 1. Rekommenderad teknikstack

Eftersom projektet ska hantera både strikta organisationsstrukturer, svenska lagtexter/PDF:er och AI-integration via MCP rekommenderas en ren, portabel **Python-baserad arkitektur**:

* **Pakethantering & Körtid:** Python 3.12+ med **`uv`** (gör att hela MCP-servern kan startas av vem som helst med ett enda kommando: `uvx totalforsvaret-mcp`).
* **Datamotor (Allt-i-en-fil):** **SQLite** med tre kombinerade lager i samma databasfil (`totalforsvaret.db`):
  1. **Relations-/Kunskapsgraf-tabeller:** Aktörer, beredskapssektorer, civilområden, län, FFO:er, lärosäten (Campus totalförsvar), lagrum och NATO:s 7 grundkrav.
  2. **`FTS5` (Full-Text Search med BM25):** Exakt sökning på SFS-nummer (`2022:524`), paragrafer, propositioner och fackbegrepp.
  3. **`sqlite-vec` (Vektorsökning):** Semantisk sökning över regleringsbrev, propositioner, handböcker och webbsidor med en flerspråkig embeddingmodell.
* **Inhämtning & Parsning:** `httpx` (API/webb), `trafilatura` (ren HTML-till-Markdown utan menybrus), `pymupdf4llm` (snabb PDF-till-Markdown med bibehållna rubriker/tabeller) samt `Pydantic` för strikt validering och filtrering enligt [`SECURITY_AND_SCOPE.md`](../SECURITY_AND_SCOPE.md).
* **MCP-ramverk:** `mcp` (officiella Python SDK:t / `FastMCP`).
* **Automatisering:** **GitHub Actions** som schemalagt övervakar [`config/sources.yaml`](../config/sources.yaml), uppdaterar de versionshanterade sammanställningarna i repot och publicerar en ny `totalforsvaret.db` under *GitHub Releases*.

---

## 2. Fyra detaljnivåer ("Zoom-nivåer" L1–L4)

För att kunna återge totalförsvaret såväl översiktligt som extremt detaljerat struktureras all data och alla MCP-verktyg i **fyra zoom-nivåer**:

| Nivå | Namn | Vad som återges | Typisk mottagare / användning |
| :--- | :--- | :--- | :--- |
| **L1** | **Exekutiv helhetsbild** | Övergripande sammanfattning av militärt + civilt försvar, de 12 beredskapssektorerna, 6 civilområdena, 18 FFO, 37 lärosäten och NATO:s 7 resilienskrav. | Snabb introduktion, presentationer, onboarding. |
| **L2** | **Struktur- & Aktörskarta** | Fullständig roll- och ansvarskarta för en specifik sektor, myndighet, civilområde eller NATO-krav (inkl. samverkande aktörer och styrande förordningar). | Verksamhetsutvecklare, handläggare, arkitekter, journalister. |
| **L3** | **Styrning, Krav & Regleringsbrev** | De konkreta formella kraven och uppdragen i lagar, förordningar, propositioner, regleringsbrev (per budgetår) och öppna NATO/HNS-ramverk. | Djupanalys av formella uppdrag och ansvarsgränser. |
| **L4** | **Källtext & Paragrafdetalj** | Ordagranna utdrag på paragraf-/styckenivå med exakt källhänvisning (SFS-nummer, propositionssida, URL och hämtningsdatum). | Juridisk/förvaltningsmässig faktagranskning och källkritik. |

---

## 3. Utdata i flera former och format

Samma strukturerade databas genererar och levererar innehåll i fyra parallella format:

1. **Interaktivt via MCP-server (`tools` + `resources` + `prompts`):**
   - `get_overview(format="markdown"|"json"|"mermaid")` *(L1)*
   - `get_actor_or_sector(id, detail_level="L2"|"L3", format=...)` *(L2–L3)*
   - `get_nato_framework(topic="baseline_requirements"|"ncrs"|"hns")` *(L2–L3)*
   - `get_regleringsbrev_assignments(agency, year)` *(L3)*
   - `search_sources(query, doc_type, year_from, detail_level="L4")` *(L4 Hybrid-RAG)*
2. **Läsbart direkt på GitHub (`exports/markdown/` & Mermaid-grafer):**
   - Automatgenererade faktablad per beredskapssektor, civilområde och NATO-krav så att besökare på GitHub kan läsa allt direkt i webbläsaren.
3. **Maskinläsbara öppna dataset (`exports/json/` & `exports/csv/`):**
   - Kompletta listor över beredskapsmyndigheter, sektorer, civilområden, FFO:er, Campus totalförsvar-lärosäten och SFS-kopplingar redo att importeras i Excel, Power BI eller egna appar.
4. **Portabel kunskapsdatabas (`totalforsvaret.db`):**
   - Nedladdningsbar SQLite-fil för offline-sökning och lokal RAG.
5. **Interaktiv 2D/3D-grafvisualisering (`web/` med `vasturiano/react-force-graph`):**
   - Bygger på [`exports/graph/force_graph.json`](../exports/graph/force_graph.json) och låter användaren växla sömlöst mellan **2D Canvas** och **3D WebGL**, välja mellan **6 domänperspektiv** (t.ex. *NATO & Resiliens*, *12 Beredskapssektorer*, *6 Civilområden*, *Campus Totalförsvar & FFO*), byta graf-layout (*Fri fysik*, *Radial*, *Top-Down*, *Left-Right*) samt filtrera fram enskilda aktörers 2-hopps grannskap (ego-graf). Publiceras automatiskt via GitHub Actions till GitHub Pages.

