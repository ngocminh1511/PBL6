---
name: LexGraph Judicial Precision
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#45464d'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#76777d'
  outline-variant: '#c6c6cd'
  surface-tint: '#565e74'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#131b2e'
  on-primary-container: '#7c839b'
  inverse-primary: '#bec6e0'
  secondary: '#4b41e1'
  on-secondary: '#ffffff'
  secondary-container: '#645efb'
  on-secondary-container: '#fffbff'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#002114'
  on-tertiary-container: '#069669'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae2fd'
  primary-fixed-dim: '#bec6e0'
  on-primary-fixed: '#131b2e'
  on-primary-fixed-variant: '#3f465c'
  secondary-fixed: '#e2dfff'
  secondary-fixed-dim: '#c3c0ff'
  on-secondary-fixed: '#0f0069'
  on-secondary-fixed-variant: '#3323cc'
  tertiary-fixed: '#85f8c4'
  tertiary-fixed-dim: '#68dba9'
  on-tertiary-fixed: '#002114'
  on-tertiary-fixed-variant: '#005137'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 30px
    fontWeight: '700'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: -0.005em
  body-lg:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: 0em
  body-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0.005em
  label-code:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: -0.01em
  label-statute:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.02em
  metric-num:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 18px
    letterSpacing: -0.02em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  margin: 1.25rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1.25rem
  space-xl: 2rem
---

## Brand & Style

### Personality & Design Archetype
The design system establishes an institutional, authoritative, and mathematically rigorous aesthetic tailored for high-stakes legal intelligence. Drawing inspiration from modern technical workbenches like Linear and premium legal AI platforms like Harvey AI and Lexis+ AI, the interface prioritizes evidentiary clarity, structural hierarchy, and high information density without visual clutter.

The visual narrative relies on **Engineered Minimalism**:
- Crisp, clinical micro-borders replace heavy structural shadows.
- Structural taxonomy matches statutory codification (Văn bản / Chương / Điều / Khoản / Điểm).
- High visual accountability: every AI claim directly surfaces its graph traversal path and verification state.

### Emotional Response
The interface evokes absolute judicial certitude, procedural trust, and technical precision. Legal practitioners, judges, and researchers must feel that they are interacting with an immutable, verifiable ledger of statutory law rather than an ungrounded generative black box.

## Colors

### System Palette Roles
- **Brand & Structural Anchor (`#0F172A` / Slate-900)**: Deployed for the primary command bar, top-level navigation, and highest-priority statutory headings. Communicates institutional authority.
- **Canvas Base (`#F8FAFC` / Slate-50) & Surface Panels (`#FFFFFF`)**: Provides a stark, high-legibility backdrop for reading extensive legal provisions.
- **Subtle Boundaries (`#E2E8F0` / Slate-200)**: Serves as low-contrast structural rules separating panels, graph columns, and citation inspect cards.

### Functional Legal Verification & Graph Semantics
The color system operates with strict semantic integrity to represent GraphRAG states:
- **Citation Verified / Retained (`#059669` / Emerald-600, background: `#ECFDF5`)**: Applied to confirmed legal citations, validated evidentiary nodes, and provisions that survive verification pruning.
- **Pipeline & Hierarchical Structure (`#4F46E5` / Indigo-600, background: `#EEF2FF`)**: Denotes query rewrite stages, syntactic parsing, vector-to-graph hops, and strict hierarchical structural edges (`PART_OF`).
- **Graph Cross-Reference (`#D97706` / Amber-600, background: `#FFFBEB`)**: Reserved for statutory cross-citations (`REFERS_TO`), guiding decrees, and procedural circular cross-links.
- **Pruned / Voided Evidence (`#E11D48` / Rose-600, background: `#FFF1F2`)**: Signifies conflicting clauses, filtered noise, superseded legal provisions, and rejected reasoning branches.

## Typography

### Structural Font Pairing
- **Interface & Text (`Inter`)**: Applied universally across interactive controls, legal prose, summaries, and chat dialogues. Inter’s tall x-height and clear counters guarantee readability when reviewing dense, complex multi-paragraph legal decrees.
- **Statutory Identifiers & Provenance (`JetBrains Mono`)**: Applied to all legal metadata tags, article markers (`Điều 12, Khoản 3, Điểm b`), law identification numbers (`100/2015/QH13`), pipeline runtime indicators, similarity metrics, and graph relationship matrices.

### Rules of Usage
1. Never mix standard roman figures with monospaced numbers inside legal citation pill tags.
2. Headings use tight letter-spacing (`-0.01em` to `-0.02em`) to mirror high-end technical analytical software.
3. Statutory paragraphs in the answer pane must preserve standard `line-height: 24px` for reading stamina.

## Layout & Spacing

### 3-Column Cockpit Architecture
The viewport operates as a fixed-height, zero-body-scroll application frame segmented into three coordinated operational columns:

1. **Left Column — Legal Context & Query Threading (`width: 280px - 320px`)**:
   - Manages conversational history, query rewrites, scope limiters (Civil, Criminal, Corporate), and document sets.
2. **Center Column — Synthesis & Interactive Legal Reasoning (`flex: 1`, min-width `580px`)**:
   - Contains multi-turn conversational synthesis, interactive inline citation chips, verification badges, and prompt inputs.
3. **Right Column — Hybrid Graph & Evidentiary Inspector (`width: 380px - 440px`)**:
   - Features hierarchical statutory drilldowns (Điều / Khoản / Điểm), knowledge graph sub-network visualizations (`PART_OF`, `REFERS_TO`), and evidence pruning audits.

### Responsive Reflow Rules
- **Desktop (>= 1440px)**: Default 3-column view open simultaneously.
- **Compact Desktop / Tablet Landscape (1024px - 1439px)**: The Right Column folds into a collapsible side-drawer with slide-over inspection triggers triggered by citation chips.
- **Mobile (< 1024px)**: Single-column view with a segmented switch navigation across `[Lịch sử / Đối thoại / Căn cứ pháp lý]`.

## Elevation & Depth

### Flat Architectural Layering
The design system avoids heavy, atmospheric drop shadows. Instead, it creates depth through low-contrast linear borders and crisp chromatic surface tiers:

- **Level 0 (Canvas Base)**: `#F8FAFC` — App layout framing and inactive gutters.
- **Level 1 (Panels & Workspaces)**: `#FFFFFF`, bounded by `1px solid #E2E8F0`.
- **Level 2 (Active Cards & Modals)**: `#FFFFFF` with a hair-line border `1px solid #CBD5E1` combined with a soft, clinical drop shadow: `0 1px 3px rgba(15, 23, 42, 0.04), 0 4px 8px -2px rgba(15, 23, 42, 0.02)`.
- **Level 3 (Citation Popovers & Floating Inspectors)**: `#FFFFFF` with `backdrop-filter: blur(8px)`, framed by `1px solid #0F172A/10`, elevated by `0 10px 25px -5px rgba(15, 23, 42, 0.08), 0 8px 10px -6px rgba(15, 23, 42, 0.04)`.

## Shapes

### Engineered Geometric Contours
The system uses subtle, tight radius geometries (`roundedness: 1`, `0.25rem` / `4px` baseline) to maintain a serious, data-dense, analytical posture.

- **Micro Controls & Badges**: `4px` corner radii for code chips, verification labels, and graph node indicators.
- **Input Fields & Action Triggers**: `6px` (`rounded-md`) corner radii to provide soft visual affordance without appearing informal.
- **Inspect Cards & Detail Overlays**: `8px` (`rounded-lg`) corner radii for structured statutory dossiers.

## Components

### 1. Citation Chips (Inline Interactive Tags)
- **Visuals**: Embedded inline within legal answers. Composed of an icon indicator, statutory tag (`Điều 32.1`), and status dot.
- **Verified State**: `#ECFDF5` background, `#059669` text, `1px solid #A7F3D0`.
- **Interaction**: Clicking locks the Inspector Column to that exact article, showing its full statutory text and surrounding graph linkages.

### 2. Hierarchical Statute Trees (Điều / Khoản / Điểm)
- **Visuals**: An indented vertical timeline/tree in the Inspector Column. Connected via structural guide tracks (`1px dashed #CBD5E1`).
- **Nodes**:
  - `Điều`: Heavy label, bold font, indigo-tinted node (`#4F46E5`).
  - `Khoản`: Medium label, prefixed with index indicator (`1.`, `2.`).
  - `Điểm`: Fine-grain terminal node, monospaced alphabet tag (`a)`, `b)`).

### 3. Graph Edge Cards (`PART_OF` vs `REFERS_TO`)
- **`PART_OF` (Structural Hierarchy)**: Crisp indigo card border, `#EEF2FF` edge badge, showing exact structural ancestry within a single codification.
- **`REFERS_TO` (Cross-Citation)**: Amber accented tag (`#FFFBEB`, border `#FDE68A`), displaying target decree/law with directional relationship arrow (`->`).

### 4. Evidence Pruning Ledger (Audit Row)
- **Pruned (Rose State)**: `#FFF1F2` background, `#E11D48` border highlight. Shows discarded text marked with strikethrough styling and reasons (e.g., *Hết hiệu lực*, *Không liên quan trực tiếp*).

### 5. Input Bar (Multi-turn Legal Reasoning)
- **Visuals**: Multi-line container with `#FFFFFF` background, elevated `1px solid #CBD5E1`. Houses inline filter selectors for legislative jurisdiction and dynamic query expansion badges.
- **Focus State**: `1px solid #4F46E5` with an outer ring of `3px rgba(79, 70, 229, 0.12)`.