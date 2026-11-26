---
name: Beakdown
description: Evidence and executable analysis on a Starchy Gooey drafting ground.
colors:
  signal: "#ff3b30"
  focus: "#c5251d"
  black: "#000000"
  ink: "#1a1a1a"
  muted: "#626262"
  paper: "#f2f2f2"
  stage: "#e9e9e9"
  white: "#ffffff"
  observed: "#4d7398"
  inferred: "#987327"
  unknown: "#897098"
typography:
  headline:
    fontFamily: "Geist, sans-serif"
    fontSize: "21px"
    fontWeight: 600
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Geist, sans-serif"
    fontSize: "18px"
    fontWeight: 600
  body:
    fontFamily: "Geist, sans-serif"
    fontSize: "12px"
    lineHeight: 1.7
  finding:
    fontFamily: "Geist, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.5
  code:
    fontFamily: "Geist Mono, monospace"
    fontSize: "11px"
    lineHeight: 1.6
rounded:
  panel: "16px"
  card: "12px"
  field: "10px"
  editor: "8px"
  capsule: "100px"
spacing:
  compact: "7px"
  gutter: "10px"
  shell: "12px"
  inset: "16px"
  generous: "20px"
components:
  button-primary:
    backgroundColor: "{colors.black}"
    textColor: "{colors.white}"
    rounded: "{rounded.capsule}"
    padding: "12px 20px"
  button-primary-hover:
    backgroundColor: "#262626"
  button-secondary:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.capsule}"
    padding: "10px 16px"
  filter-selected:
    backgroundColor: "{colors.black}"
    textColor: "{colors.white}"
    rounded: "{rounded.capsule}"
    padding: "7px 9px"
  search:
    backgroundColor: "#ffffff90"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: "10px 12px"
  pane:
    backgroundColor: "linear-gradient(160deg, #ffffffe0, #ffffffa3 60%)"
    rounded: "{rounded.panel}"
  analysis-node:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "10px 12px"
    width: "210px"
---

# Design System: Beakdown

## Overview

**Creative North Star: "Starchy Gooey drafting ground"**

Beakdown adopts the selected shared Starchy Gooey system. A neutral drafting ground holds heavy translucent chrome, crisp black actions and restrained red signals. Soft material and fluid selection frame a precise, information-dense tool; evidence and computed results remain the foreground.

The system supports inspection and correction. Screenshots, confidence labels, provenance and real execution results must remain distinguishable and legible inside the same material language. The product commitments are recorded in [PRODUCT.md](PRODUCT.md).

**Key Characteristics:**
- Neutral drafting ground and black ink.
- Heavy glass for chrome; opaque surfaces for evidence and computation.
- Fluid capsule selection with explicit selected states.
- Geist for reading; Geist Mono for code and execution facts.

## Colors

The single identity accent is signal red, supported by neutral surfaces and a separate semantic confidence vocabulary.

### Primary

- **Signal red:** brand marks, selected screenshot outlines, evidence links and capture signals. The darker focus token supplies keyboard outlines and caret emphasis.

### Neutral

- **Black and ink:** decisive actions, active computation nodes and readable text.
- **Muted:** secondary explanations and supporting metadata.
- **Paper and stage:** the architectural ground and inset canvas.
- **White:** evidence cards, computation results and glass highlights.

Confidence annotations retain their implemented blue observed, ochre inferred and mauve unknown colors. Their light fills are semantic context, not additional brand accents; words and annotation patterns carry the same meaning.

**The Signal Rule.** Use red to locate a selected item or an evidence connection; keep long reading surfaces neutral.

## Typography

**Body Font:** Geist, with sans-serif fallback. **Label/Mono Font:** Geist Mono, with monospace fallback. Local font imports live in [src/main.tsx](src/main.tsx).

Geist keeps dense interface text quiet and direct. Mono distinguishes executable expressions and measured facts from findings. There is no display or hero type role in the workbench.

### Hierarchy

- **Headline:** inspector headings; tighter tracking provides hierarchy without decorative type.
- **Title:** report heading.
- **Finding:** finding titles; analysis node titles share the size with medium emphasis.
- **Body:** descriptions, controls and findings. Supporting text is compact; do not inherit tiny table metadata as a universal label size.
- **Code:** editable SQL with a generous line height. Tables and execution metadata use Mono at their own compact sizes.

**The Readable Graph Rule.** Preserve readable node titles when fitting a graph. The current graph reserves (180px) height and initially fits between (0.85) and (1) zoom; overflow remains navigable.

## Layout

The shell uses a compact outer inset, narrow gutters and independently bounded panes. At desktop widths the investigation uses three columns: screen navigation, a flexible connected stage, and findings. The stage can show evidence, computation, or both; both mode stacks screenshot evidence over the real graph and table. A review dock sits below the workspace.

Default desktop columns are (196px / minmax(0, 1fr) / 324px). At the wide breakpoint they become (220px / minmax(0, 1fr) / 360px); at intermediate widths they tighten to (154px / minmax(0, 1fr) / 275px). These are the current workbench composition, not a requirement for every future surface.

At (760px) and below, panes stack, screen navigation becomes a horizontal strip, and the review dock participates in normal document flow. The compact shell uses the compact spacing token. Short desktop viewports scroll the connected stage rather than shrinking the graph into illegibility. Preserve overflow for screenshots, graphs and tables.

## Elevation & Depth

Depth combines translucent gradients, substantial backdrop blur and soft, recessed shadows. Header and review dock use panel glass: `linear-gradient(160deg, #ffffffeb, #ffffffb3 60%)` with `blur(34px) saturate(1.3)`. Side panes use pane glass: the pane background token with `blur(20px) saturate(1.2)`. Evidence cards and analysis results remain opaque.

### Shadow Vocabulary

- **Panel glass:** `inset 0 1px #fffffff5, 0 20px 60px -48px #00000073`.
- **Pane highlight:** `inset 0 1px #ffffffe6`.
- **Evidence lift:** `0 10px 28px -18px #0005`.
- **Selected navigation:** `0 5px 20px -12px #0005`.

**The Material Boundary Rule.** Apply glass to framing chrome; keep captured evidence, code and results sharp on opaque surfaces.

## Shapes

Panels have generous rounded corners, cards and navigation rows use the smaller card radius, and fields step down again. Buttons and selection controls are capsules. Findings remain editorial rows divided by a fine rule rather than repeated elevated cards.

Hairline black alpha borders separate content without adding a second frame around every pane. Selected screenshots use a red outline. Region annotations use bordered rectangles, with a dashed boundary for unknown evidence; preserve these purposeful rectangular forms within the rounded chrome.

## Components

### Buttons

Black capsule primary actions are decisive; white secondary capsules remain quiet. Primary review hover darkens and scales to (1.025); generic press scales to (0.98). Disabled controls use reduced opacity (0.45). Keyboard focus uses a darker red outline (2px) with (3px) offset.

### Chips

Confidence chips use named semantic colors, light fills and compact corners. Filter chips become black with white text when selected. Always retain textual state labels.

### Cards / Containers

Opaque evidence cards and computation nodes use the card radius and fine borders. Selected evidence gains a red border; active analysis nodes invert to ink with white text. Findings use transparent rows, fine bottom dividers and generous vertical separation.

### Inputs / Fields

Search uses translucent white, a fine black alpha stroke and the field radius. SQL uses Mono, the editor radius and a resizable multiline field. Focus remains visible against both glass and opaque surfaces.

### Navigation

Screen rows carry thumbnail, order and title; selected rows gain a white surface and soft lift. On mobile they become horizontally scrollable title controls. Journey and execution scrubbers share black range accents while keeping their separate purposes visible.

### Fluid mode switch

The three-way mode switch is the signature control: a black capsule and smaller trailing droplet move through an SVG blur-and-threshold filter behind the labels. Selected text is white. The main capsule moves over (520ms), the trailing droplet over (720ms), with the rise easing. Keep this fusion inside the selection track so labels remain crisp. Reduced-motion preference removes transitions and animation.

## Do's and Don'ts

### Do:

- **Do** reuse the selected Starchy Gooey materials, Geist pairing and neutral ground.
- **Do** distinguish semantic confidence, evidence selection and computation selection through words and state as well as color.
- **Do** preserve navigable overflow and readable graph text across viewport sizes.
- **Do** keep keyboard focus and reduced-motion behavior on new controls.

### Don't:

- **Don't** substitute a new visual identity for the adopted shared system.
- **Don't** blur screenshots, code, table values or selected labels with the glass treatment.
- **Don't** promote incidental tiny metadata sizes or unused legacy selectors into reusable system roles.
