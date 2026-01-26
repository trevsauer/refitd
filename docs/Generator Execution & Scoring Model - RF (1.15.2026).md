# ReFitd — Generator Execution & Scoring Model

*Canonical Specification · Revised*

This document defines how ReFitd's outfit generator executes deterministically using clean product data, canonical tags, and explicit user constraints.

> **The generator is not AI-driven.**
> It is rule-based, constraint-first, and deterministic.
> AI influences direction, never execution.

---

## Purpose

The generator:

- Retrieves eligible items from the catalog
- Enforces explicit constraints without exception
- Applies soft AI intent as scoring bias only
- Assembles coherent item stacks
- Ranks outcomes predictably
- Supports fast, lossless iteration (Generate / Lock / Pass)

The generator is designed to be:

- **Predictable**
- **Debuggable**
- **Auditable**
- **Trustworthy at scale**

---

## Core Principles

1. Constraints before creativity
2. Deterministic execution
3. Soft preferences, hard rules
4. No hidden state
5. Predictable iteration
6. Outfit quality > novelty

---

## Structural Inputs (Authoritative)

The generator consumes only canonical, policy-approved data.

### Authoritative inputs include:

| Input | Source |
|-------|--------|
| Product category and top-layer role | Ingestion |
| Canonical item tags | Confidence-free |
| Size availability snapshot | Freshness eligibility |
| User-defined hard filters | User input |
| Generator slot configuration | System config |
| Locked / passed items | Session state |

### The generator never consults:

- ❌ Raw AI output
- ❌ Tag confidence values
- ❌ Retailer metadata directly
- ❌ Affiliate data

---

## High-Level Execution Flow (Strict Order)

Every generation follows the same ordered pipeline:

```
1. Apply explicit constraints
2. Retrieve eligible candidates (per slot)
3. Apply slot and category inclusion rules
4. Apply locks and pass exclusions
5. Score candidate items
6. Assemble outfits
7. Score outfits
8. Rank and return results
```

> ⚠️ **No step may be skipped, reordered, or conditionally bypassed.**

---

## 1. Constraint Application (Hard Rules)

Hard constraints are authoritative and always enforced first.

### Hard constraints include:

- Size filters (if selected)
- Color include / exclude rules
- Brand include / exclude rules
- Retailer include / exclude rules
- Slot on/off state
- Locked items
- Per-item budget sliders (min / max)

### If an item violates any hard constraint:

- It is **excluded immediately**
- It is **never scored**

> **There are no exceptions.**

---

## 2. Candidate Retrieval (Per Slot)

Retrieval is slot-based, not free-form.

For each enabled slot (e.g. Top Base, Top Mid, Bottom, Shoes, Outerwear):

1. Query the catalog for items that:
   - Match the slot's structural category
   - Pass all hard constraints
   - Meet freshness eligibility thresholds
2. Use canonical item tags only
3. Never consult raw AI output

This produces a **candidate pool per slot**.

---

## 3. AI Intent Bias Application (Soft Preferences)

AI-derived intent from chat is translated into **scoring biases**, never filters.

### Examples:

| AI Signal | Scoring Impact |
|-----------|----------------|
| Climate | Fabric & silhouette weighting |
| Context | Formality weighting |
| Vibe | Style identity weighting |
| Color direction | Color-family weighting |

### Rules:

- AI biases can only **increase or decrease scores**
- AI biases can **never exclude items**
- Explicit user constraints **always override AI intent**

> **If a conflict occurs:** Explicit control wins; AI bias is clipped.

---

## 4. Price Topology Enforcement

Price logic is always active and mode-free.

### Per-Item Budget (Hard)

- Each slot has a min / max price slider
- Items outside the range are **excluded**

### Optional Total Budget (Convenience Only)

- If provided, the system distributes realistic starting weights
- Users may override freely
- Total price is always calculated, **never enforced**

### Spending Range (Scoring Only)

| Mode | Behavior |
|------|----------|
| Economy | Wider tolerance |
| Premium | Tighter tolerance |

> Used to **rank**, not exclude.

---

## 5. Item-Level Scoring

Each candidate item receives a normalized score.

### Scoring inputs may include:

- Style identity alignment
- Fit & silhouette compatibility
- Formality alignment
- Material relevance
- Color harmony
- Pairing / versatility tags (scoring-only)
- Price proximity to slider center
- Freshness confidence weighting

### Scoring rules:

- All components are weighted, bounded, and additive
- No single factor may dominate
- Structural violations are never scored (they are filtered earlier)

---

## 6. Outfit Assembly

Outfits are assembled by combining **exactly one item per enabled slot**.

### Assembly rules:

- Locked items are fixed
- Passed items are excluded for the current cycle
- Disabled slots are skipped
- No duplicate products within an outfit

> **The generator never hallucinates combinations:**
> - Only real catalog items
> - One instance per outfit

---

## 7. Outfit-Level Scoring

Each assembled outfit receives an aggregate score based on:

| Factor | Description |
|--------|-------------|
| Average item score | Baseline quality |
| Cross-slot silhouette balance | Proportional harmony |
| Formality coherence | Consistent register |
| Cross-item color harmony | Palette cohesion |
| Price distribution realism | Budget alignment |
| Penalties for extreme outliers | Quality control |

> Outfits that violate coherence guardrails are **discarded**.

---

## 8. Ranking & Output

Returned outfits are:

1. Sorted by final score
2. Deduplicated
3. Returned as a ranked list

The top result should feel:

- **Plausible**
- **Wearable**
- **Intentional**

> If it does not, the issue is scoring configuration, not randomness.

---

## 9. Iteration Mechanics (Critical)

### Generate

- Re-runs the full pipeline
- Preserves locked items
- Clears pass exclusions

### Lock Item

- Item remains fixed
- All other items in that slot are excluded

### Pass / Single-Item Regenerate

- Passed item is excluded
- Only that slot regenerates
- All other slots remain unchanged

### Turn Off Slot

- Slot removed from retrieval and assembly
- No scoring occurs for that slot

> **Iteration must feel fast, deterministic, and lossless.**

---

## 10. Determinism Guarantees

Given the same:

- Style Profile state
- Catalog snapshot
- Slot configuration
- Locks and passes

The generator **must**:

- Return the same results
- In the same order

> ⚠️ **Randomness is not allowed.**
> If variation is desired, it must be explicit and user-invoked.

---

## 11. What the Generator Explicitly Does Not Do

- ❌ No AI product selection
- ❌ No learning at generation time
- ❌ No hidden personalization
- ❌ No sponsored bias
- ❌ No visual composition tricks

> **Learning happens between sessions, not during execution.**

---

## 12. Failure Modes & Debugging

If outfits feel off, check in order:

1. Hard constraints too tight?
2. Tag quality or policy suppression issues?
3. Scoring weights misbalanced?
4. Freshness pool too stale?

> ⚠️ **Never fix issues by introducing randomness.**

---

## Mental Model

```
┌─────────────────────────────────────────────────────────────┐
│  Ingestion   →  defines structure                           │
│  Tags        →  describe items                              │
│  Policy      →  decides what is safe                        │
│  AI          →  nudges direction                            │
│  Scoring     →  ranks plausibility                          │
│  Users       →  converge deliberately                       │
└─────────────────────────────────────────────────────────────┘
```

This makes the system feel:

- **Intelligent**
- **Predictable**
- **Trustworthy**

---

## Audience & Ownership

### Audience

- Backend engineering
- Core product
- QA / taste review

### Ownership

- Generator service
- Scoring configuration
- Determinism guarantees

---

## One-Line Summary

> **The generator is a deterministic decision engine that assembles coherent outfits by enforcing structural constraints first and ranking what works best — not what merely looks good.**

```
Ingestion → Tagging → Policy → Generator → Ranking
```
