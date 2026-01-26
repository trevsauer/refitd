# ReFitd — Required Fields per Product Ingestion

This document defines the canonical product data captured at ingestion time.

**Ingestion establishes structural truth about a product.** Downstream systems (tagging, generation, monetization) may consume this data, but never reinterpret or override it.

Product ingestion is intentionally **conservative** and **deterministic**. No inferred attributes, AI judgments, or affiliate logic are allowed at this stage.

---

## 1. Product Identity (Required)

These fields uniquely identify a product and anchor it permanently in the catalog.

| Field | Description |
|-------|-------------|
| **Brand** | Product brand name |
| **Product title** | Full product title |
| **Canonical product URL** | Clean, stable retailer URL — no affiliate parameters, redirects, or tracking tokens |

---

## 2. Structural Classification (Required, Deterministic)

Structural classification defines how the product participates in outfit generation. These fields are assigned at ingestion and are **never inferred or modified** by the tagging model.

### Product Category (Required)

Exactly one of:

| Category | Includes |
|----------|----------|
| `top` | — |
| `bottom` | pants, shorts |
| `outerwear` | jackets, coats, blazers, vests |
| `shoes` | — |

### Top Layer Role (Required only if category = `top`)

Exactly one of:

| Role | Includes |
|------|----------|
| `base` | t-shirts, long-sleeve tees, shirts, polos |
| `mid` | sweaters, cardigans, hoodies, knit pullovers |

### Notes

- Category and top layer role are **structural**, not stylistic.
- These fields drive generator slot logic and are treated as authoritative.
- They are **not** refreshed, learned, or reclassified downstream.

---

## 3. Pricing (Snapshot at Ingestion)

Captured once at ingestion to provide baseline pricing context.

| Field | Description |
|-------|-------------|
| **Price** | Price at time of ingestion |
| **Currency** | Currency code |

> ⚠️ Pricing may drift over time; this snapshot is not a guarantee.

---

## 4. Size & Availability (Snapshot)

Ingestion captures a single availability snapshot, not real-time inventory.

| Field | Description |
|-------|-------------|
| **All sizes offered** | Complete size range supported by the item |
| **Sizes available** | Sizes available at time of scrape |
| **last_checked_at** | Availability check timestamp |

> This snapshot establishes eligibility, not availability guarantees.

---

## 5. Images (All Required)

The full product image gallery must be captured.

All images available on the product page, including:

- Model-worn images
- Model-less (flat / ghost / product-only) images
- Detail and close-up shots

> Images are stored verbatim and are **not** curated or filtered at ingestion.

---

## 6. Raw Product Metadata (Uninterpreted)

Raw retailer-provided text is stored without interpretation or normalization.

| Field | Description |
|-------|-------------|
| **Full product description** | Verbatim text |
| **Raw materials text** | Verbatim, if present |
| **Raw color name(s)** | Retailer-provided |

> These fields are inputs to the tagging system but are not directly consumed by the generator.

---

## 7. Ingestion Metadata (Required)

Operational metadata for auditing, debugging, and refresh logic.

| Field | Description |
|-------|-------------|
| **Retailer name** | Source retailer |
| **Ingestion timestamp** | When the product was ingested |
| **Source page identifier** | URL hash or internal source ID |

---

## 8. Refresh Scrape (Mutable Fields Only)

Subsequent refresh jobs are **strictly limited in scope**.

Only the following fields may update after ingestion:

- `sizes_available`
- `last_checked_at`

> ⚠️ **No other fields are refreshed automatically.**

---

## 9. Explicitly Not Captured at Ingestion

The ingestion pipeline **must not** capture or generate:

- ❌ Fit notes (unless part of the raw description text)
- ❌ Construction details (unless part of the raw description text)
- ❌ Any inferred or normalized attributes
- ❌ Any AI-generated tags or confidence scores
- ❌ Affiliate or tracking data
- ❌ Real-time inventory status or guarantees

---

## 10. Canonical Ingestion Rule (Non-Negotiable)

**Product category** and **top layer role** are structural classifications assigned deterministically at ingestion.

They are:

- ✅ **Not** inferred by the tagging model
- ✅ **Not** confidence-based
- ✅ **Not** subject to refresh
- ✅ **Not** overridable downstream

> This separation preserves determinism, debuggability, and long-term system trust.

---

## Mental Model

```
┌─────────────────────────────────────────────────────────────┐
│  Ingestion    →  defines structure                          │
│  Tagging      →  describes attributes                       │
│  Policy       →  decides what is safe                       │
│  Generator    →  executes deterministically                 │
└─────────────────────────────────────────────────────────────┘
```

**If ingestion is clean, everything downstream stays sane.**
