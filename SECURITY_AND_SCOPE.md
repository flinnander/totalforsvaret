# Avgränsning, Etik & Säkerhetsskydd (Scope Policy)

Detta projekt ([`flinnander/totalforsvaret`](https://github.com/flinnander/totalforsvaret)) samlar in och strukturerar **uteslutande offentlig, öppen information** för att förklara **vad det svenska totalförsvaret är, hur det är organiserat och vilka formella krav och regelverk som styr det**.

---

## Grundprincip: "Struktur & Krav JA – Uppfyllnad & Sårbarhet NEJ"

Även när enskilda dokument är offentliga kan en automatiserad sammanställning av brister, förmågebedömningar eller lokala sårbarheter ge upphov till så kallad **aggregeringsproblematik**. Projektets inhämtningspipeline och datamodell följer därför en strikt gränsdragning:

### Vad vi SAMLAR IN (Normativt, organisatoriskt & utbildande)
* **Lagstiftning och författningar:** Lagar (SFS), förordningar, propositioner, kommittédirektiv och allmänna föreskrifter.
* **Organisation och roller:** Vilka myndigheter, beredskapssektorer (12 st), civilområden (6 st), län/regioner, kommuner, frivilliga försvarsorganisationer (18 st) och lärosäten (Campus totalförsvar, 37 st) som ingår och vilket formellt ansvar de har.
* **Formella uppdrag och styrning:** Vad regeringen ger för offentliga uppdrag i t.ex. regleringsbrev och strategier.
* **Internationella ramverk (NATO):** Vad NATO:s offentliga ramverk innebär konceptuellt och förvaltningsmässigt (t.ex. Artikel 3 / *Seven Baseline Requirements*, hur NCRS/NRS och värdlandsstöd/HNS definieras i öppen svensk lagstiftning och doktrin).
* **Utbildning och forskning:** Öppna handböcker, begreppsförklaringar och utbildningsinitiativ.

### Vad vi AKTIVT EXKLUDERAR (Utfall, förmåga & fysisk detaljdata)
* **Hur aktörer svarar upp mot kraven:** Vi samlar **inte** in granskningar, mognadsmätningar, tillsynsbeslut, återrapporteringar av brister eller bedömningar av hur väl myndigheter, regioner, kommuner eller företag faktiskt uppfyller beredskaps- eller NATO-krav.
* **Risk- och sårbarhetsanalyser (RSA):** Inga kommunala, regionala eller myndighetsspecifika RSA-dokument eller sårbarhetskartläggningar indexeras.
* **Fysisk och geografisk infrastruktur:** Inga koordinater, kartlager, kapacitetssiffror eller placeringar för skyddsobjekt, reservkraft, beredskapslager, dricksvattentäkter, ledningscentraler, baser eller kritiska noder. *(Kartvyn i projektet använder uteslutande offentliga administrativa stadscentrumkoordinater för residensstäder, universitetsorter och myndigheters officiella säteskommuner.)*
* **Personuppgifter på individnivå:** Endast institutionella roller och offentliga kontaktvägar på myndighets-/organisationsnivå hanteras; aldrig listor över enskilda befattningshavare i krigsorganisation eller liknande.

---

## Teknisk tillämpning i pipelinen

I [`config/sources.yaml`](config/sources.yaml) implementeras denna policy genom:
1. **Kurerad källstyrning (Allowlist):** Inhämtning sker endast från godkända domäner och dokumenttyper.
2. **Exkluderingsfilter (`exclusion_rules`):** Dokument och sidor vars titel, URL eller metadata indikerar *risk- och sårbarhetsanalys*, *tillsynsrapport*, *förmågebedömning*, *återrapportering av brister* eller *geografiska anläggningsdata* filtreras bort automatiskt före bearbetning och indexering.
