# ReFitd — Item Tagging System

*Canonical, With Explicit Confidence Separation*

---

## Purpose

The tagging system converts raw retail inventory into trusted, structured signals that power ReFitd's outfit generator.

This system is **intentionally conservative**.

It prioritizes:

- **Correctness**
- **Consistency**
- **Debuggability**

Over expressiveness.

> **Tags are data — not opinions.**

---

## System Architecture (Critical Distinction)

The tagging system has **three distinct layers**.

These layers **must remain separate**.

### 1. AI Tag Output (Sensor Layer — With Confidence)

- Produced by the tagging model (GPT-5.2)
- Contains proposed tags with confidence scores
- Is **never** consumed directly by the generator
- Is immutable once stored

> **Purpose:** Capture the model's best estimate plus uncertainty.

### 2. Policy & Threshold Layer (Decision Layer)

- Runs in the scraper / worker service
- Applies:
  - Confidence thresholds
  - Schema validation
  - Category-aware rules
- Determines:
  - Which tags are accepted
  - Which are suppressed
  - Whether curator review is required

> **Purpose:** Decide what is safe to trust.

### 3. Canonical Item Tags (Execution Layer — No Confidence)

- Written only after policy evaluation
- Contain approved tags only
- Do **not** store confidence values
- Are the **only** tags the generator reads

> **Purpose:** Provide stable, predictable inputs for generation.

---

## Golden Rule

> **Confidence guides acceptance — not execution.**

---

---

# Tag Taxonomy (Used by All Layers)

Only the tags below are allowed.

> ⚠️ **No free-text tags are ever permitted.**

---

## 1. Style Identity

*Aesthetic / Cultural Layer — Primary Retrieval Signal*

### Allowed (1–2 max):

| Tag |
|-----|
| `minimal` |
| `classic` |
| `preppy` |
| `workwear` |
| `streetwear` |
| `rugged` |
| `tailoring` |
| `elevated-basics` |
| `normcore` |
| `sporty` |
| `outdoorsy` |
| `western` |
| `vintage` |
| `grunge` |
| `punk` |
| `utilitarian` |

### Rules:

- Captures aesthetic lineage, not dress code
- Must **not** encode formality
- Assigning 3 or more is **disallowed**
- Some combinations are rare but allowed (e.g. `minimal` + `elevated-basics`)

> Used heavily for retrieval and scoring. **This is the most important tagging layer.**

---

## 2. Fit

*Category-Aware, Exactly One*

### Allowed:

| Tag | Restrictions |
|-----|--------------|
| `skinny` | Bottoms only |
| `slim` | — |
| `regular` | — |
| `relaxed` | — |
| `oversized` | Tops and outerwear only |

### Rules:

- Exactly one fit tag per item
- `skinny` is **never** allowed on tops or outerwear
- `oversized` is **never** allowed on bottoms
- "tight" is not a canonical tag (map to `slim` / `skinny` internally)

---

## 3. Silhouette

*Category-Aware Shape — Exactly One*

### Bottoms (pants + shorts)

| Tag |
|-----|
| `straight` |
| `tapered` |
| `wide` |

### Tops & Outerwear

| Tag |
|-----|
| `boxy` |
| `structured` |
| `relaxed` |
| `longline` |
| `tailored` |

### Rules:

- Describes shape, not tightness
- Cropped is intentionally excluded in v1
- Exactly one silhouette per item

---

## 4. Formality

*Situational Appropriateness — Exactly One*

### Allowed (ordered scale):

| Level | Tag |
|-------|-----|
| 1 | `athletic` |
| 2 | `casual` |
| 3 | `smart-casual` |
| 4 | `business-casual` |
| 5 | `formal` |

### Rules:

- Formality is **independent** from Style Identity
- Used for compatibility and context alignment
- **Always required**

---

## 5. Context

*Optional, Supporting Layer*

### Allowed (0–2 max):

| Tag |
|-----|
| `everyday` |
| `work-appropriate` |
| `travel` |
| `evening` |
| `weekend` |

### Rules:

- Context is situational, not aesthetic
- Never used as a hard filter
- Used to support scoring and explanation

---

## 6. Materials

*Visible / Stated — 1–2 max*

### Allowed:

| Tag |
|-----|
| `denim` |
| `cotton` |
| `wool` |
| `linen` |
| `leather` |
| `synthetic` |
| `blend` |

### Rules:

- Must be visually obvious or explicitly stated
- Raw material text is stored separately; this layer is normalized

---

## 7. Construction / Details

*Optional, Highly Constrained*

### Allowed (0–2 max):

#### Bottoms

| Tag |
|-----|
| `pleated` |
| `flat-front` |
| `cargo` |
| `drawstring` |
| `elastic-waist` |

#### Upper-Body Structure (tops / outerwear)

| Tag |
|-----|
| `structured-shoulder` |
| `dropped-shoulder` |

### Rules:

- Only include high-signal, structural features
- **No garment archetypes** (e.g. bomber, chore-jacket)
- No closures or minor details
- Must materially affect fit, layering, or compatibility

---

## 8. Color Family

*Exactly One*

### Allowed:

| Tag |
|-----|
| `black` |
| `white` |
| `grey` |
| `navy` |
| `brown` |
| `beige` |
| `olive` |
| `blue` |
| `green` |
| `red` |
| `multi` |

---

## 9. Pattern

*Optional — 0–1*

### Allowed:

| Tag |
|-----|
| `solid` |
| `stripe` |
| `check` |
| `textured` |

---

## 10. Pairing & Versatility

*Scoring-Only — Never Filtered*

### Allowed (0–3 max):

| Tag |
|-----|
| `neutral-base` |
| `statement-piece` |
| `easy-dress-up` |
| `easy-dress-down` |
| `high-versatility` |

### Rules:

- Never used for filtering
- Never user-visible as a control
- Used only to guide scoring and explanation

---

## Explicitly Removed

The following concepts are **not** tagged or stored:

- ❌ Era / decade references (70s, 90s, Y2K, etc.)
- ❌ Garment archetypes (bomber, chore-jacket, field-jacket)
- ❌ Vibes or trend language
- ❌ Free-text descriptors

> These may be generated at explanation time only, never stored.

---

---

# ReFitd — Shoe Tagging System (v1)

Shoes are tagged to support:

- Outfit compatibility
- Formality alignment
- Context appropriateness

> They are **not** tagged for micro-style or trend nuance.

---

## 1. Shoe Type

*Primary structural tag — Exactly One*

This is the most important shoe tag.

### Allowed:

| Tag |
|-----|
| `sneakers` |
| `boots` |
| `loafers` |
| `derbies` |
| `oxfords` |
| `sandals` |
| `dress-shoes` (fallback bucket, rarely used) |

### Rules:

- Exactly one shoe type per item
- Chosen conservatively
- If ambiguous between derbies/oxfords, prefer `dress-shoes`

> **Why this works:** Shoe type is one of the strongest drivers of formality and outfit logic. This is a case where explicit categorization adds value (unlike bomber jackets).

---

## 2. Shoe Profile / Bulk

*Silhouette-equivalent — Exactly One*

This replaces shoe silhouette without exploding complexity.

### Allowed:

| Tag | Description |
|-----|-------------|
| `sleek` | Minimal leather sneaker |
| `standard` | Chuck 70 |
| `chunky` | Trail runner |

### Rules:

- Describes visual weight, not sole height
- Exactly one per shoe

> This matters a lot for balance with pants silhouettes.

---

## 3. Formality

*Exactly One — same ladder as apparel*

### Allowed:

| Level | Tag |
|-------|-----|
| 1 | `athletic` |
| 2 | `casual` |
| 3 | `smart-casual` |
| 4 | `business-casual` |
| 5 | `formal` |

### Rules:

- Required
- Same meaning as apparel formality
- Shoes often anchor the maximum formality of an outfit

---

## 4. Materials

*1–2 max — reuse global list*

### Allowed:

| Tag |
|-----|
| `leather` |
| `suede` |
| `canvas` |
| `knit` |
| `synthetic` |
| `blend` |

### Rules:

- Must be visually obvious or explicitly stated
- Material heavily influences formality scoring

---

## 5. Closure

*Optional — 0–1 max*

### Allowed:

| Tag |
|-----|
| `lace-up` |
| `slip-on` |
| `buckle` |

### Rules:

- Optional
- Useful for explanation, not core scoring
- Do not overuse

---

## 6. Style Identity

*Reuse global list — 1–2 max*

Shoes may receive:

| Tag |
|-----|
| `streetwear` |
| `classic` |
| `minimal` |
| `sporty` |
| `rugged` |
| `workwear` |
| `western` |
| `utilitarian` |
| `vintage` |

### Rules:

- Same identity set as apparel
- Shoes rarely get 2 identities unless very clear

---

## 7. Color Family

*Exactly One — same as apparel*

### Allowed:

`black`, `white`, `brown`, `beige`, `navy`, `grey`, `multi`, etc.

---

## 8. Pattern

*Optional — 0–1 max*

### Allowed:

| Tag |
|-----|
| `solid` |
| `textured` |

> Stripe/check are rare and usually decorative → skip v1

---

## Explicitly NOT Tagged for Shoes

These are intentionally excluded:

- ❌ Fit (tight/loose does not apply meaningfully)
- ❌ Toe shape (round/almond/square)
- ❌ Sole type (lugged, crepe, etc.)
- ❌ Heel height
- ❌ Vintage era
- ❌ Named styles (Chelsea, Chukka, Desert, etc.)
- ❌ Comfort language ("all-day", "walking shoe")

> All of these add noise, are brand-relative, or don't materially improve generation quality yet.

---

---

# Example: Outfit Item Tag Outputs (Sensor Layer)

## 1) Top — Base (T-Shirt)

```json
{
  "category": "top_base",
  "style_identity": [
    { "tag": "minimal", "confidence": 0.86 }
  ],
  "fit": { "tag": "regular", "confidence": 0.91 },
  "silhouette": { "tag": "relaxed", "confidence": 0.78 },
  "formality": { "tag": "casual", "confidence": 0.94 },
  "materials": [
    { "tag": "cotton", "confidence": 0.89 }
  ],
  "color_family": { "tag": "white", "confidence": 0.96 },
  "pattern": { "tag": "solid", "confidence": 0.92 }
}
```

## 2) Top — Mid (Sweater)

```json
{
  "category": "top_mid",
  "style_identity": [
    { "tag": "elevated-basics", "confidence": 0.81 }
  ],
  "fit": { "tag": "relaxed", "confidence": 0.84 },
  "silhouette": { "tag": "boxy", "confidence": 0.76 },
  "formality": { "tag": "smart-casual", "confidence": 0.79 },
  "materials": [
    { "tag": "wool", "confidence": 0.73 }
  ],
  "color_family": { "tag": "navy", "confidence": 0.88 }
}
```

## 3) Bottoms (Pants / Shorts)

```json
{
  "category": "bottom",
  "style_identity": [
    { "tag": "workwear", "confidence": 0.77 }
  ],
  "fit": { "tag": "relaxed", "confidence": 0.82 },
  "silhouette": { "tag": "straight", "confidence": 0.86 },
  "formality": { "tag": "casual", "confidence": 0.90 },
  "materials": [
    { "tag": "denim", "confidence": 0.88 }
  ],
  "construction_details": [
    { "tag": "flat-front", "confidence": 0.74 }
  ],
  "color_family": { "tag": "blue", "confidence": 0.93 }
}
```

## 4) Outerwear (Jacket / Coat / Vest)

```json
{
  "category": "outerwear",
  "style_identity": [
    { "tag": "streetwear", "confidence": 0.83 }
  ],
  "fit": { "tag": "regular", "confidence": 0.80 },
  "silhouette": { "tag": "boxy", "confidence": 0.87 },
  "formality": { "tag": "casual", "confidence": 0.91 },
  "materials": [
    { "tag": "synthetic", "confidence": 0.69 }
  ],
  "color_family": { "tag": "black", "confidence": 0.95 }
}
```

## 5) Shoes

```json
{
  "category": "shoes",
  "shoe_type": { "tag": "sneakers", "confidence": 0.92 },
  "profile": { "tag": "sleek", "confidence": 0.77 },
  "formality": { "tag": "casual", "confidence": 0.88 },
  "materials": [
    { "tag": "leather", "confidence": 0.71 }
  ],
  "closure": { "tag": "slip-on", "confidence": 0.68 },
  "style_identity": [
    { "tag": "minimal", "confidence": 0.74 }
  ],
  "color_family": { "tag": "white", "confidence": 0.94 }
}
```

### Important Reminder (as designed)

- This is **Sensor Layer** output
- Confidence **never** reaches the generator
- Policy layer will:
  - Drop low-confidence tags
  - Enforce category rules
  - Output clean Canonical Item Tags

---

---

# Policy & Threshold Layer (Worker Logic)

All thresholds are enforced **outside the model** in the worker / policy layer.

> **The model proposes; the system decides.**

Thresholds are category-aware and signal-strength–aware.

---

## Confidence Thresholds (by Tag Type)

### Style Identity

*Primary retrieval signal — conservative*

| Confidence | Action |
|------------|--------|
| ≥ 0.85 | Auto-approve |
| 0.70–0.84 | Allow, flag for passive review |
| < 0.70 | Suppress or require curator review |

**Rules:**

- Max 2 identities enforced post-approval
- Disallowed combinations are rejected regardless of confidence

### Fit

*Structural — required*

| Confidence | Action |
|------------|--------|
| ≥ 0.80 | Auto-approve |
| 0.65–0.79 | Allow |
| < 0.65 | Suppress (fallback required) |

**Rules:**

- Exactly one fit must exist post-policy
- Category constraints enforced (e.g. no oversized bottoms)

### Silhouette

*Structural — required*

| Confidence | Action |
|------------|--------|
| ≥ 0.80 | Auto-approve |
| 0.65–0.79 | Allow |
| < 0.65 | Suppress (fallback required) |

**Rules:**

- Exactly one silhouette per item
- Category-aware validation enforced

### Formality

*Guardrail — required*

| Confidence | Action |
|------------|--------|
| ≥ 0.80 | Auto-approve |
| 0.65–0.79 | Allow |
| < 0.65 | Suppress → default to conservative value (`casual`) |

**Rules:**

- Exactly one formality tag must exist
- Defaults are allowed to preserve generator stability

### Context

*Supporting — optional*

| Confidence | Action |
|------------|--------|
| ≥ 0.75 | Allow |
| < 0.75 | Suppress |

**Rules:**

- Max 2 contexts
- Never required
- Never used for hard filtering

### Materials

*Visible but noisy — optional*

| Confidence | Action |
|------------|--------|
| ≥ 0.85 | Auto-approve |
| 0.70–0.84 | Allow |
| < 0.70 | Suppress |

**Rules:**

- Max 2 materials
- Must be visually obvious or explicitly stated

### Construction / Details

*Optional, high-risk for hallucination*

| Confidence | Action |
|------------|--------|
| ≥ 0.85 | Allow |
| 0.70–0.84 | Allow, flag |
| < 0.70 | Suppress |

**Rules:**

- Max 2 details
- Category restrictions enforced
- Never required

---

## Shoe-Specific Fields

### Shoe Type (required)

| Confidence | Action |
|------------|--------|
| ≥ 0.80 | Auto-approve |
| < 0.80 | Suppress → route for review or default conservatively |

### Shoe Profile (required)

| Confidence | Action |
|------------|--------|
| ≥ 0.70 | Allow |
| < 0.70 | Default to `standard` |

### Shoe Closure (optional)

| Confidence | Action |
|------------|--------|
| ≥ 0.70 | Allow |
| < 0.70 | Suppress |

---

## Pairing & Versatility Tags

*Scoring-only*

| Confidence | Action |
|------------|--------|
| ≥ 0.60 | Allow |
| < 0.60 | Suppress |

**Rules:**

- Never used for filtering
- Never trigger review

---

---

# Canonical Item Tags (Execution Layer)

This is the **only** structure consumed by the generator.

### Properties:

- Approved tags only
- No confidence values
- No suppressed or defaulted tags unless required
- Fully schema-validated

### Example Canonical Output

```json
{
  "category": "bottom",
  "style_identity": ["workwear"],
  "fit": "regular",
  "silhouette": "straight",
  "formality": "casual",
  "context": ["everyday"],
  "materials": ["denim"],
  "construction_details": ["flat-front"],
  "color_family": "blue",
  "pattern": "solid",
  "pairing_tags": ["neutral-base", "easy-dress-down"]
}
```

> Note: shoes follow the same structure with shoe-specific fields added.

---

## Data Storage Contract (Required)

Each item stores:

| Field | Description |
|-------|-------------|
| `tags_ai_raw` | Full AI output with confidence (immutable) |
| `tags_final` | Canonical tags (confidence-free) |
| `tag_policy_version` | Version of policy applied |
| `curation_status` | Approval status |
| `curation_notes` | Curator comments |

> ⚠️ **Raw AI output is never overwritten.**

---

## Curator Workflow

Items are routed for curator review when:

- Primary style identity confidence < 0.70
- Required structural tags cannot be resolved
- Construction / silhouette conflicts occur
- Shoe type confidence is ambiguous

Curators may:

- ✅ Approve
- ✅ Adjust within allowed taxonomy
- ✅ Flag for exclusion

> Curators do **not** invent new tags or rewrite items from scratch.

---

## Retrieval vs Scoring Responsibility

| Tag Layer | Responsibility |
|-----------|----------------|
| Style Identity | Retrieval + Scoring |
| Fit | Scoring |
| Silhouette | Scoring |
| Formality | Guardrails |
| Context | Soft Guardrails |
| Materials | Retrieval + Scoring |
| Color Family | Hard Filtering |
| Pattern | Scoring |
| Construction / Details | Scoring |
| Pairing Tags | Scoring Only |
| Shoe Type | Guardrails + Scoring |

---

## Guardrails (Non-Negotiable)

- ✅ No confidence values in canonical tags
- ✅ No generator access to raw AI output
- ✅ No prompt-level policy logic
- ✅ No silent taxonomy changes
- ✅ No deprecated tags (e.g. era) retained

---

## Mental Model

```
┌─────────────────────────────────────────────────────────────┐
│  AI         →  senses                                       │
│  Policy     →  decides                                      │
│  Humans     →  verify                                       │
│  Generator  →  executes                                     │
└─────────────────────────────────────────────────────────────┘
```

> This separation keeps ReFitd's taste system stable, explainable, and scalable.

---

---

# Understanding Confidence Scores

## What the Confidence Score Is (and Is Not)

### It is NOT:

- ❌ A probability
- ❌ A guarantee
- ❌ An objective truth score
- ❌ Something you should expose to users
- ❌ Something you should directly use in generation

### It IS:

- ✅ A self-reported uncertainty signal
- ✅ A ranking heuristic
- ✅ A way to decide where human attention is most valuable

> **Think of it like:** "How sure am I relative to my other judgments?"
> **Not:** "Is this objectively correct?"

---

## Why You Should Not Manually Approve Everything

Manual approval of 100% of items sounds safe — but it creates three real problems:

### 1. You Don't Scale (Obvious, but real)

Zara alone = tens of thousands of SKUs.

You will:

- Slow ingestion
- Delay freshness
- Burn founder time
- Still miss errors

### 2. Humans Get Sloppy When Everything Is Manual

When reviewers see everything, they:

- Skim
- Rubber-stamp
- Miss edge cases
- Stop thinking critically

> **Counterintuitively:** Selective review produces higher quality than universal review.

### 3. You Lose Signal About the Model

If everything is reviewed:

- You never learn which tags are reliably safe
- You can't tighten thresholds intelligently
- You can't evolve taxonomy based on error patterns

> Confidence + thresholds let you **measure** reliability.

---

## The Correct Mental Model

> **ChatGPT confidence is a triage mechanism, not an authority.**

You are asking: *"Where should a human spend time?"*

Not: *"Is this correct?"*

---

## What Actually Deserves Mandatory Human Review

### Always review:

- Style identity conflicts (e.g. formal + streetwear)
- Low-confidence style identity
- New or rare tags
- New brands / new categories

> These are high-impact, high-risk.

### Safe to auto-approve (with thresholds):

- Color family
- Fit (most of the time)
- Materials when explicitly stated
- Common silhouettes
- Pairing / versatility tags

> If these are wrong occasionally, they don't break retrieval, don't confuse users, and get corrected downstream by scoring.

---

## Why ChatGPT Confidence Is Still Useful

> **You don't care if the confidence is "accurate" — you care if it is directionally consistent.**

Across thousands of items, the model:

- Is more confident on obvious cases
- Is less confident on ambiguous ones

That's enough to:

- Surface edge cases
- Reduce human load
- Keep quality high

> You are exploiting **relative uncertainty**, not absolute truth.

---

## The Safety Net You've Already Designed

Even if a tag slips through:

- It's still constrained by:
  - Size filters
  - Color filters
  - Brand filters
  - Formality scoring
- It's just one signal among many
- Bad tags show up as:
  - Weird outfits
  - Increased passes
  - Low save rates

Which feeds back into:

- Curator correction
- Taxonomy refinement
- Threshold tuning

> **This is why your system is robust.**

---

## The Real Trust Model

**You are not trusting ChatGPT.**

You are trusting:

1. Your taxonomy (small, controlled)
2. Your thresholds (conservative)
3. Your human review on high-risk cases
4. Your generator's redundancy
5. Your willingness to correct mistakes

> ChatGPT is just a fast junior assistant.

---

## A Better Framing (Internally)

| Layer | Role |
|-------|------|
| "AI tags" | Suggestions |
| "Policy-approved tags" | Assumptions |
| "Curated tags" | Ground truth |

Over time:

- The suggestion layer gets better
- The policy gets stricter
- The curator workload shrinks

---

## Final Recommendation

> ⚠️ **Do NOT manually approve everything.**
>
> You'll slow down, burn out, and ironically reduce quality.

**Do this instead:**

- ✅ Mandatory review for high-risk categories
- ✅ Threshold-based auto-approval for low-risk tags
- ✅ Periodic audits of auto-approved items
- ✅ Tight taxonomy discipline

> This is how real recommendation systems survive contact with scale.

---

---

# Policy Implementation: Review Routing + Suppression

Clean, implementable pseudo-code for the review routing + suppression logic.

```python
# ============================================================
# ReFitd Tag Policy v2 — Review Routing + Suppression
# Matches "ReFitd — Item Tagging System (Canonical...)"
#
# Input: tags_ai_raw (sensor output with confidence)
# Output:
#   - tags_final (canonical, confidence-free, generator-ready)
#   - curation_status: "approved" | "needs_review" | "needs_fix"
#   - curation_reasons: [string]
#   - suppressed_tags: [{field, tag, confidence, reason}]
#   - defaults_applied: [{field, value, reason}]
#   - tag_policy_version
#
# Notes:
# - tags_ai_raw is stored IMMUTABLY in DB.
# - tags_final is the ONLY structure consumed by generator.
# - Confidence NEVER reaches generator.
# - Category/top-layer-role are structural, assigned at ingestion.
# ============================================================

POLICY_VERSION = "tag_policy_v2.0"

# ----------------------------
# Canonical thresholds (from spec)
# ----------------------------
THRESH = {
    # Style Identity (primary retrieval)
    "style_identity_auto": 0.85,
    "style_identity_flag": 0.70,

    # Fit (required)
    "fit_auto": 0.80,
    "fit_allow": 0.65,
    "fit_suppress": 0.65,

    # Silhouette (required)
    "silhouette_auto": 0.80,
    "silhouette_allow": 0.65,
    "silhouette_suppress": 0.65,

    # Formality (required)
    "formality_auto": 0.80,
    "formality_allow": 0.65,
    "formality_suppress": 0.65,

    # Context (optional)
    "context_allow": 0.75,

    # Materials (optional)
    "materials_auto": 0.85,
    "materials_allow": 0.70,

    # Construction / Details (optional, higher bar)
    "details_allow": 0.85,
    "details_flag": 0.70,
    "details_suppress": 0.70,

    # Pairing tags (scoring-only)
    "pairing_allow": 0.60,

    # Shoes
    "shoe_type_auto": 0.80,
    "shoe_profile_allow": 0.70,
    "shoe_closure_allow": 0.70
}

# ----------------------------
# Category-aware constraints (from spec)
# ----------------------------
# Categories are ingestion-level structural:
#   "top_base", "top_mid", "bottom", "outerwear", "shoes"

ALLOWED = {
    "style_identity": {
        "minimal", "classic", "preppy", "workwear", "streetwear",
        "rugged", "tailoring", "elevated-basics", "normcore", "sporty",
        "outdoorsy", "western", "vintage", "grunge", "punk", "utilitarian"
    },
    "fit": {"skinny", "slim", "regular", "relaxed", "oversized"},
    "silhouette_bottom": {"straight", "tapered", "wide"},
    "silhouette_upper": {"boxy", "structured", "relaxed", "longline", "tailored"},
    "formality": {"athletic", "casual", "smart-casual", "business-casual", "formal"},
    "context": {"everyday", "work-appropriate", "travel", "evening", "weekend"},
    "materials_apparel": {"denim", "cotton", "wool", "linen", "leather", "synthetic", "blend"},
    "details_bottom": {"pleated", "flat-front", "cargo", "drawstring", "elastic-waist"},
    "details_upper": {"structured-shoulder", "dropped-shoulder"},
    "color_family": {"black", "white", "grey", "navy", "brown", "beige", "olive", "blue", "green", "red", "multi"},
    "pattern": {"solid", "stripe", "check", "textured"},
    "pairing_tags": {"neutral-base", "statement-piece", "easy-dress-up", "easy-dress-down", "high-versatility"},

    # shoes:
    "shoe_type": {"sneakers", "boots", "loafers", "derbies", "oxfords", "sandals", "dress-shoes"},
    "shoe_profile": {"sleek", "standard", "chunky"},
    "shoe_closure": {"lace-up", "slip-on", "buckle"},
    "materials_shoes": {"leather", "suede", "canvas", "knit", "synthetic", "blend"}
}

# ----------------------------
# Helpers
# ----------------------------
def add_reason(reasons, r):
    if r not in reasons:
        reasons.append(r)

def suppress(suppressed, field, tag, conf, reason):
    suppressed.append({
        "field": field,
        "tag": tag,
        "confidence": conf,
        "reason": reason
    })

def default_value(defaults, field, value, reason):
    defaults.append({
        "field": field,
        "value": value,
        "reason": reason
    })

def pick_top_by_conf(tag_objs, min_conf):
    best = None
    for obj in tag_objs:
        if obj["confidence"] >= min_conf:
            if best is None or obj["confidence"] > best["confidence"]:
                best = obj
    return best

def pick_top_n(tag_objs, n, min_conf):
    eligible = [x for x in tag_objs if x["confidence"] >= min_conf]
    eligible.sort(key=lambda x: x["confidence"], reverse=True)
    return eligible[:n]

def is_bottom(cat):
    return cat == "bottom"

def is_top_or_outer(cat):
    return cat in ("top_base", "top_mid", "outerwear")

def is_shoes(cat):
    return cat == "shoes"

# ----------------------------
# Main Policy Function
# ----------------------------
def apply_tag_policy_v2(tags_ai_raw, item_category):
    reasons = []
    suppressed = []
    defaults = []
    tags_final = {}

    # 0) Basic schema sanity
    if item_category is None:
        add_reason(reasons, "missing_item_category")
        return {"error": "fatal_needs_fix"}

    # 1) STYLE IDENTITY (1–2 max, REQUIRED)
    style_raw = tags_ai_raw.get("style_identity", [])
    style_legal = []

    for obj in style_raw:
        if obj["tag"] not in ALLOWED["style_identity"]:
            suppress(suppressed, "style_identity", obj["tag"], obj["confidence"], "illegal_tag")
            add_reason(reasons, "illegal_tag_returned")
            continue
        style_legal.append(obj)

    for obj in style_legal:
        if obj["confidence"] < THRESH["style_identity_flag"]:
            suppress(suppressed, "style_identity", obj["tag"], obj["confidence"], "below_flag_threshold")

    style_candidates = [x for x in style_legal if x["confidence"] >= THRESH["style_identity_flag"]]
    style_selected = pick_top_n(style_candidates, n=2, min_conf=THRESH["style_identity_flag"])
    tags_final["style_identity"] = [x["tag"] for x in style_selected]

    if len(tags_final["style_identity"]) == 0:
        add_reason(reasons, "missing_style_identity")
    else:
        if any(x["confidence"] < THRESH["style_identity_auto"] for x in style_selected):
            add_reason(reasons, "style_identity_needs_passive_review")

    # 2) FIT (EXACTLY ONE, REQUIRED, CATEGORY RULES)
    fit_obj = tags_ai_raw.get("fit")

    if fit_obj is None:
        add_reason(reasons, "missing_fit")
    elif fit_obj["tag"] not in ALLOWED["fit"]:
        suppress(suppressed, "fit", fit_obj["tag"], fit_obj["confidence"], "illegal_tag")
        add_reason(reasons, "missing_fit")
    else:
        if is_bottom(item_category) and fit_obj["tag"] == "oversized":
            suppress(suppressed, "fit", fit_obj["tag"], fit_obj["confidence"], "invalid_for_category")
            add_reason(reasons, "missing_fit")
        elif is_top_or_outer(item_category) and fit_obj["tag"] == "skinny":
            suppress(suppressed, "fit", fit_obj["tag"], fit_obj["confidence"], "invalid_for_category")
            add_reason(reasons, "missing_fit")
        elif fit_obj["confidence"] < THRESH["fit_allow"]:
            suppress(suppressed, "fit", fit_obj["tag"], fit_obj["confidence"], "below_allow_threshold")
            add_reason(reasons, "missing_fit")
        else:
            tags_final["fit"] = fit_obj["tag"]
            if fit_obj["confidence"] < THRESH["fit_auto"]:
                add_reason(reasons, "fit_low_confidence")

    # Fallback for missing fit
    if "fit" not in tags_final and not is_shoes(item_category):
        tags_final["fit"] = "regular"
        default_value(defaults, "fit", "regular", "required_missing_or_suppressed")

    # ... (remaining logic for silhouette, formality, color, etc.)

    # 12) Decide curation status
    status = "approved"

    if "missing_style_identity" in reasons:
        status = "needs_fix"

    if "missing_shoe_type" in reasons:
        status = "needs_fix"

    if status == "approved":
        review_triggers = [
            "style_identity_needs_passive_review",
            "category_inappropriate_detail",
            "illegal_tag_returned",
            "fit_low_confidence",
            "silhouette_low_confidence",
            "formality_low_confidence"
        ]
        if any(r in reasons for r in review_triggers):
            status = "needs_review"

    return {
        "tags_final": tags_final,
        "curation_status": status,
        "curation_reasons": reasons,
        "suppressed_tags": suppressed,
        "defaults_applied": defaults,
        "tag_policy_version": POLICY_VERSION
    }
```

### Implementation Tips

- Keep `tags_ai_raw` intact in the DB for auditing
- Store `tags_final` as the generator's only input
- Version the policy (`tag_policy_v2.0`) so you can reprocess older items consistently
- "Conflict pairs" is intentionally simple for v1; evolve based on real curator feedback

---

---

# ReFitd — Canonical Item Tagging Prompt

*Sensor Layer · GPT-5.2 · Vision + Text*

## SYSTEM / INSTRUCTION PROMPT

```
You are a fashion item tagging system for ReFitd.

Your task is to analyze real retail fashion products using:
• product images
• product title
• product category
• product description

and return structured, controlled tags that follow the ReFitd Item Tagging Specification exactly.

You are not generating opinions, recommendations, outfits, marketing copy, or explanations.
You are producing machine-readable tags for a deterministic outfit generation engine.

If something is uncertain, lower the confidence or omit the tag.
Never guess. Never invent tags. Never exceed limits.
```

---

## INPUTS YOU WILL RECEIVE

For each product:

| Input | Description |
|-------|-------------|
| Brand | Product brand name |
| Product title | Full product title |
| Product category | One of: `top_base`, `top_mid`, `bottom`, `outerwear`, `shoes` |
| Product description | Verbatim retail copy |
| Product images | One or more (at least one front-facing) |

> **Important:** Category and top-layer role are already determined upstream. Do not re-classify the product.

---

## GLOBAL TAGGING RULES (STRICT)

- Use only tags from the allowed lists
- Respect maximum tag counts per layer
- Every tag must include a confidence score (0.0–1.0)
- Prefer under-tagging to over-tagging
- Do not infer details not visible or stated
- Do not include confidence explanations
- Output valid JSON only
- Do not include any text outside the JSON

> **If a tag does not clearly apply, omit it.**

---

## REQUIRED vs OPTIONAL (CRITICAL)

### Apparel (`top_base`, `top_mid`, `bottom`, `outerwear`)

**Required (must be present):**

- Style Identity (1–2)
- Fit (exactly 1)
- Silhouette (exactly 1)
- Formality (exactly 1)
- Color Family (exactly 1)

**Optional:**

- Context (0–2)
- Materials (1–2)
- Construction / Details (0–2)
- Pattern (0–1)
- Pairing & Versatility (0–3)

### Shoes

**Required:**

- Shoe Type (exactly 1)
- Shoe Profile / Bulk (exactly 1)
- Formality (exactly 1)
- Color Family (exactly 1)

**Optional:**

- Style Identity (1–2)
- Materials (1–2)
- Closure (0–1)
- Pattern (0–1)
- Pairing & Versatility (0–3)

---

## EXPLICITLY FORBIDDEN

Do not output or reference:

- ❌ Era / decade tags (70s, 90s, Y2K, etc.)
- ❌ Garment archetypes (bomber, chore jacket, parka, etc.)
- ❌ Trend language or vibes
- ❌ Fit notes like "tight", "loose"
- ❌ Free-text descriptors
- ❌ Explanations outside JSON

---

## OUTPUT FORMAT (JSON ONLY)

Return only this structure:

```json
{
  "style_identity": [
    { "tag": "", "confidence": 0.0 }
  ],
  "fit": { "tag": "", "confidence": 0.0 },
  "silhouette": { "tag": "", "confidence": 0.0 },
  "formality": { "tag": "", "confidence": 0.0 },
  "context": [
    { "tag": "", "confidence": 0.0 }
  ],
  "materials": [
    { "tag": "", "confidence": 0.0 }
  ],
  "construction_details": [
    { "tag": "", "confidence": 0.0 }
  ],
  "color_family": { "tag": "", "confidence": 0.0 },
  "pattern": { "tag": "", "confidence": 0.0 },
  "pairing_tags": [
    { "tag": "", "confidence": 0.0 }
  ],

  /* shoes only */
  "shoe_type": { "tag": "", "confidence": 0.0 },
  "profile": { "tag": "", "confidence": 0.0 },
  "closure": { "tag": "", "confidence": 0.0 }
}
```

> Omit any optional fields entirely if not applicable.

---

## CONFIDENCE GUIDELINES

| Confidence | Meaning |
|------------|---------|
| 0.90–1.00 | Visually obvious or explicitly stated |
| 0.75–0.89 | Strong inference from images + text |
| 0.60–0.74 | Plausible but uncertain |
| < 0.60 | Usually omit |

> Confidence is a triage signal, not a guarantee.

---

## FINAL REMINDER

**You are the sensor, not the judge.**

- Propose conservatively
- Let policy decide
- Let humans review edge cases
- Preserve generator stability

> **Optimize for correctness and consistency — not creativity.**
