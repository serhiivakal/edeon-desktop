**Edeon Knowledge Hub — Exhaustive Build Plan**

***1. Strategic Vision***
The current Knowledge tab is positioned as a "searchable reference database." That framing is the problem — under it, you will always lose to PPDB, OECD QSAR Toolbox, and the underlying databases themselves. PPDB has 20 years of curated content; you will not out-content them.
The position that wins is fundamentally different: the Knowledge Hub is Edeon's connective tissue, not a reference book. Every compound in the Inspector, every target in the 3D viewer, every model in the QSAR Studio is the entry point to a context-aware, multi-source, citation-traced knowledge view. The tab's value isn't its content — it's that it knows what you're working on and pulls the right context, from the right sources, with the right provenance, automatically.
North-star user story: "A chemist drops a SMILES into the Inspector. The Knowledge Hub instantly shows: this scaffold's HRAC/IRAC/FRAC class, the most similar commercial pesticides with their regulatory status, the known target with linked PDB structure, recent resistance reports, key patents and their expiration dates, and three relevant papers — every fact citation-traced, every source dated. Then the user asks 'how does cross-resistance look in this class?' and Claude answers from the integrated content, citing specific sources."
That product is not PPDB. It's also not what StarDrop or DataWarrior do. It's defensible.

***2. Architecture: Three Layers***
The Hub must be designed as three independently maintainable layers:
LayerWhat it holdsRefresh cadenceStorageL1 — Static / CuratedVersioned reference content: HRAC/IRAC/FRAC tables, regulatory frameworks explained, target dossiers, educational primersPer release (annual+)Bundled SQLite, versioned in codeL2 — Live / SyncedAPI-backed: PubChem, ChEMBL, Europe PMC, EFSA OpenFoodTox snapshots, EPA CompTox, ECOTOX, PDBDaily / weekly background syncCached SQLite with TTLL3 — IntelligentRAG + Claude-powered Q&A, knowledge graph navigation, agentic workflowsOn-demandEmbeddings in DuckDB/SQLite-VSS or LanceDB; LLM via Anthropic API
The separation matters because L1 ships offline (regulatory clients need this), L2 degrades gracefully when offline, and L3 is opt-in with explicit user consent (LLM data egress is a real procurement question).

***3. Phased Roadmap***
Phase 1 — Foundations (Weeks 1–4)
Goal: turn the static reference into a structured, navigable, citation-traced knowledge base.

Knowledge entity model. Define five canonical entity types: Compound, Target, MoA_Class, Regulatory_Status, Reference. Every entity has a stable ID, provenance metadata (source, date, version), and bidirectional relationships. Schema lives in SQLite with foreign keys.
HRAC / IRAC / FRAC atlas. Populate the full mode-of-action classifications (HRAC 2020 numbering for herbicides, IRAC 11.1+ for insecticides, FRAC 2025 for fungicides) as structured data. Each class has: code, target, mechanism description, representative actives, year of first registration, resistance status. This alone is a significant content upgrade.
Citation-traced facts. Every fact in the database has a source field pointing to a Reference entity. No claim without provenance. Build the UI to show citations on hover.
Universal search. Replace whatever the current search is with a federated search over all entity types, ranked by relevance, with type-faceted filters. Use SQLite FTS5 for full-text indexing.
Knowledge Card component. A unified card UI for displaying any entity's complete record, with tabs (Overview, Properties, Relationships, References, History). Compound cards include 2D depiction; target cards include PDB thumbnails.

Phase 2 — Live Data Integration (Weeks 5–9)
Goal: stop being static.
SourceIntegrationUsePubChemREST API (free, no key)Compound lookup, synonyms, CAS, vendor linksChEMBLREST API + DuckDB snapshotsBioactivity, targets, assay metadataPDB / RCSBREST APITarget structures, ligand dataEurope PMCREST API (free)Literature search, full text where OAEFSA OpenFoodToxZenodo CSV (annual)EU pesticide hazard dataEPA CompTox Chemicals DashboardREST APIUS chemical info, predicted propertiesECOTOXBulk download (EPA, free)Ecotoxicity literature dataSureChEMBLREST API (free)Patent literatureNORMAN SusDatBulk downloadEmerging contaminants, transformation productsEU Pesticides DatabaseWeb scrape / structured exportsActive substance regulatory status
Each source gets a dedicated connector module with: rate limiting, error handling, version pinning, schema mapping into Edeon's entity model, and a per-source last_synced timestamp surfaced in the UI. Sync jobs run as background tasks via the Tauri runtime.
Critical licensing note: PPDB is not freely redistributable. Do not scrape it. Either license it (commercial agreement with the University of Hertfordshire) or work entirely from open sources. The good news is the open sources collectively cover ~80% of what PPDB offers.

***Phase 3 — Knowledge Graph & Cross-Module Glue (Weeks 10–14)***
Goal: make the Hub the central nervous system of Edeon.

- Relationship layer. Beyond simple foreign keys, build a true graph: compound → target → MoA class → resistance mechanism → cross-resistant compounds → analogs in pipeline. Use a lightweight embedded graph store (Kuzu is excellent and embeds cleanly) or a dedicated relationships table with edge types if you want to avoid the dependency.
- Inspector ↔ Knowledge integration. When a compound is selected anywhere in Edeon, a "Knowledge" accordion in the Inspector pulls its full card: HRAC class, similar marketed compounds (Tanimoto search over the local compound table), regulatory status, recent papers. Click-through opens the full card in the Knowledge tab.
Target ↔ 3D viewer integration. The 3D viewer's preset targets each get a target Knowledge Card linking PDB structures, known inhibitor classes, resistance mutations, key residues, and the relevant HRAC/IRAC/FRAC entries.
QSAR Studio ↔ Knowledge integration. When training a model, the Studio can pull a ChEMBL-curated training set for a known target ("train a bee LD50 model on ApisTox") with one click. Model cards (Phase 3 of QSAR Studio) cite their training data via the Knowledge entities.
Resistance mutation database. A structured table of documented target-site resistance mutations: target → mutation → first reported (year, location, organism) → cross-resistance pattern → references. This is genuinely scarce in open form and would be a differentiator.

Phase 4 — Intelligent Layer (Weeks 15–20)
Goal: ship the agentic / LLM-augmented features the market expects in 2026.

RAG over integrated content. Embed every Knowledge entity (descriptions, paper abstracts, regulatory summaries) using a local sentence-transformer model — all-MiniLM-L6-v2 for speed, nomic-embed-text-v1.5 for quality. Store embeddings in SQLite-VSS or LanceDB.
Claude-powered Q&A. A dedicated chat panel in the Knowledge tab where users ask natural-language questions. The system retrieves top-k relevant entities, builds a context, calls the Anthropic API (Claude Sonnet 4.6 or Haiku 4.5 depending on user preference for speed/quality), and returns citation-anchored answers. Every answer shows its sources as clickable Knowledge Cards. Crucially, no hallucinated facts — the system prompt is strict about answering only from retrieved context.
Saved research threads. Q&A sessions are persisted as Research_Thread entities — chemists can return to their investigations, share them with colleagues, attach them to projects.
Agentic workflows. Higher-level capabilities exposed as agent tools: "find me all SDHI fungicides with documented Zymoseptoria tritici resistance, sorted by year of first report" → the agent decomposes into ChEMBL queries, literature searches, and structured filtering. This is where Edeon stops looking like every other tool.
Compound briefing reports. One-click generation of a structured briefing document for any compound: discovery history, MoA, regulatory status, environmental profile, resistance management, key references, recent literature. Exportable as PDF — directly usable for project meetings.

Phase 5 — Regulatory & Project Layers (Weeks 21–28)
Goal: turn the Hub into a workspace, not just a viewer.

Regulatory tracker. Per-jurisdiction status tracking: EU (Reg 1107/2009 active substance status, expiry dates, re-registration windows), EPA (registration review schedule), China, Brazil, India. Surface as a calendar/timeline view. Alert system for upcoming changes affecting compounds in the user's library.
MRL lookup. Maximum residue limits per crop, per jurisdiction. Critical for formulation and market strategy.
Patent landscape view. For any scaffold, pull SureChEMBL/Lens patents covering it. Show: composition-of-matter coverage, geographic scope, expiration timeline, assignees. Visualised as a Gantt-style chart.
Project knowledge layer. Private user notes attachable to any entity. Project bundles that group compounds + targets + research threads + private annotations. Exportable as a project package for collaboration.
News & alerts. Subscribable feeds: new active substance approvals (EFSA RSS, EPA Federal Register), pesticide bans/withdrawals, new resistance reports (CropLife resistance reporting). Filter by user-defined keywords or library contents.
Compound history timeline. Visual timeline for any commercial pesticide: synthesis discovery → first patent → first registration → key resistance reports → bans/restrictions → re-registration outcomes. Powerful for both regulatory and competitive intelligence work.


***4. Per-Feature Detail (Selected Highlights)***
Knowledge Card design
Each entity card should have a consistent structure:

Header: name, structure (compounds), identifiers (CAS, InChIKey, UniProt, PDB)
Quick facts: 4–6 key data points at a glance
Tabs: Overview · Properties · Relationships · References · History · Notes
Provenance footer: data sources, last sync date, citation count
Actions: "View in 3D" (targets), "Send to QSAR Studio" (compound sets), "Add to project", "Generate briefing"

Mode-of-Action Atlas
An interactive navigator: tree view (HRAC/IRAC/FRAC top level → group → MoA → target → representative actives) plus a graph view showing cross-resistance relationships. Each node is a Knowledge Card entry point.
Resistance Intelligence
The single feature most likely to be missing in competitive products. Maintain a structured database of:

Target-site mutations (gene, codon, mutation, organism, year, location, reference)
Metabolic resistance mechanisms (CYP, GST, ABC transporter overexpression)
Cross-resistance matrices within and across MoA classes
Field resistance reports with geographic distribution

Surface as both filterable tables and visualisations (resistance heatmap by region × MoA class).
Compound Similarity Graph
For any compound, render a graph of structurally similar compounds (Tanimoto ≥ 0.7) from PubChem/ChEMBL, color-coded by regulatory status and MoA class. Hovering reveals the activity profile. Clicking navigates to that compound's card. This is genuinely useful for scaffold-hopping ideation and competitive analysis.
Citation Manager
Every reference shown in the Hub can be added to a user's reference library, exported as BibTeX/RIS, and surfaced when generating briefing reports.

***5. LLM Integration — Specifics***
Given your Anthropic API access:

Model selection: default to Claude Haiku 4.5 for cost/speed on standard Q&A; offer Claude Sonnet 4.6 / Opus for deep research questions. Surface the choice in Settings.
System prompt design: strict "answer only from provided context; if not in context, say so explicitly; cite every fact with the source ID." This is the difference between a trustworthy research tool and a hallucination generator.
Context window management: cap retrieved context at ~30k tokens; if a question demands broader synthesis, fall back to multi-turn retrieval (agentic loop).
Token cost transparency: show users an indicator of API cost per query. Critical for enterprise procurement conversations.
Local-LLM fallback (Phase 4+): integrate Ollama or llama.cpp for offline operation. Quality drops but data never leaves the machine — a hard requirement for some regulatory clients. Edeon would be one of very few agrochemistry tools offering this.
Data governance: explicit user consent for API calls; option to redact compound structures from prompts (use IDs only with local-only structure resolution); audit log of all LLM calls.


***6. Data Sources & Licensing Reality Check***
SourceLicenseRiskPubChemPublic domainNoneChEMBLCC BY-SA 3.0Attribution required, downstream share-alikePDBCC0NoneECOTOXUS public dataNoneEFSA OpenFoodToxCC BY 4.0Attribution requiredEPA CompToxUS public dataNoneEurope PMCMixed; OA subset freeRespect per-article licensesHRAC/IRAC/FRAC classificationsFree reference but check redistribution termsVerify before bundlingPPDBLicensed, not freely redistributableDo not integrate without commercial agreementSureChEMBLEBI termsFree for non-commercial; check commercial termsLens.orgTiered APIFree tier limited; paid for production
The licensing summary alone is worth getting right early — it determines what can ship in the open-source/community version vs. what stays behind enterprise licensing.

***7. Technical Implementation Notes***
Given your stack (Tauri/Rust + React + Python via IPC + SQLite):

L1 storage: ship a knowledge.db SQLite file with bundled curated content. Versioned with code releases.
L2 storage: separate knowledge_cache.db for synced content with TTLs.
L3 storage: embeddings.db (SQLite-VSS) or embeddings.lance (LanceDB) for vectors.
Sync jobs: implement in Rust using tokio for concurrency; background tasks run on schedule (daily for ChEMBL/PubChem, weekly for OpenFoodTox).
Connectors: structured as one Rust module per source, each implementing a KnowledgeSource trait (fetch, map, store, last_synced). Adding a new source = implementing one trait.
LLM module: Python service via your existing IPC; uses the Anthropic SDK; streams responses back to the React UI via Tauri events.
Search: SQLite FTS5 for full-text; combined with vector search for semantic queries (the two are complementary, not competing).
UI: a three-pane layout — entity browser (left) + Knowledge Card (center) + research thread / chat (right). Resizable, collapsible.


***8. Risks & Considerations***

Stale content is worse than no content. Build the last_synced timestamps and freshness warnings into the UI from day one. Nothing destroys credibility faster than confidently displaying outdated regulatory status.
PPDB temptation. It's the obvious target and the obvious mistake. Stay clean on licensing or pay for a commercial integration. A cease-and-desist would be a major setback.
LLM hallucination liability. Strict context-bounded RAG, visible citations, clear "I don't know" behavior. Test extensively on edge cases. A confidently wrong regulatory claim in an Edeon-generated briefing is a serious problem.
API cost at scale. If enterprise users run thousands of queries, Anthropic API costs add up. Model the unit economics; expose token costs; offer the local-LLM fallback for cost-sensitive deployments.
Offline mode. Many regulatory clients require air-gapped operation. The L1 + L2-with-cache architecture supports this; the LLM layer is opt-in. Make this a marketed feature.
Maintenance burden. Connectors need updating as APIs change. Budget for ongoing maintenance — this is not build-once code.


***9. Connection to the Wider Edeon Story***
This is where the Knowledge Hub becomes strategically central rather than a side tab:

It makes the LogP-based predictor modules less embarrassing. When the honeycomb shows a bee LD50 prediction, the Knowledge Card for that compound can show the measured LD50 from EFSA/ECOTOX if available. The prediction becomes "first estimate, here's the real data when we have it" — a defensible position rather than a fragile one.
It powers the QSAR Studio. "Train on ApisTox" becomes one click because the Hub has the data already curated and entity-linked.
It anchors the publication papers. Paper 3's open benchmarks become part of the Hub. Each dataset is a Knowledge entity; each model card cites it.
It's the most natural place for the Claude-powered agentic experience. This is where Edeon stops looking like a clean version of legacy tools and starts looking like a 2026 product.


***10. Commercial Impact***
Honest assessment:

Academic / educational: meaningfully improved. The Mode-of-Action atlas alone is a teaching tool. Strong.
Small CRO / agtech startup: significantly improved. The integration (one place for compound data, regulatory status, similar compounds, papers) saves real time. This is the segment where the Hub flips from "moderate interest" to "actively useful."
Enterprise R&D: improved, but they have internal knowledge graphs. The differentiator here is the integration with the rest of Edeon — knowledge that's context-aware of your QSAR model, your 3D viewer, your project. That story they don't get from internal tools.
Regulatory affairs: this is the segment that benefits most. Citation-traced facts, regulatory tracker, MRL lookup, briefing report generation — these map directly to dossier preparation work. With Phase 5, this segment moves from "low interest" to "potentially the highest-value buyer."

The Knowledge Hub upgrade isn't as foundational as the QSAR Studio fix (which addressed an outright scientific defect), but it's the highest-leverage feature for broadening the addressable market — particularly into regulatory affairs, which has the deepest budgets in the segments you can realistically reach.