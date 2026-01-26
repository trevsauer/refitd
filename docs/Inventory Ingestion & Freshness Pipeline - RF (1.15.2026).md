# ReFitd — Inventory Ingestion & Freshness Pipeline

*Canonical Specification*

---

## Purpose

The Inventory Ingestion & Freshness Pipeline governs how ReFitd:

- Ingests retail products
- Captures size availability
- Manages staleness over time
- Refreshes inventory selectively
- Maintains trust without promising real-time accuracy

This system is designed to be:

- **Scalable**
- **Fast at generation time**
- **Honest about uncertainty**
- **Resilient to retail volatility**

> **ReFitd optimizes for likely correctness, not guarantees.**

---

## Core Principles

1. No real-time inventory checks during generation
2. Retailer pages are the final source of truth
3. Freshness is probabilistic, not binary
4. Selective refresh beats constant scraping
5. Never promise what cannot be enforced

---

## High-Level Architecture

The pipeline is composed of five stages:

```
┌─────────────────────────────────────────────────────────────┐
│  1. Ingestion (Initial Capture)                             │
│  2. Stored Availability Snapshot                            │
│  3. Freshness & Confidence Decay                            │
│  4. Refresh Queues (Selective)                              │
│  5. Click-Time Reality Check                                │
└─────────────────────────────────────────────────────────────┘
```

Each stage has a clearly defined responsibility.

---

## 1. Product Ingestion (Initial Capture)

### When Ingestion Happens

- When a product is first discovered via scraping
- When a new category or retailer is added
- When a curator manually forces ingestion

### Data Captured at Ingestion

Each product records a single availability snapshot:

| Field | Description |
|-------|-------------|
| Brand | Product brand name |
| Category | Product category |
| Product URL | Clean, canonical — no affiliate params |
| Price at ingestion | Snapshot price |
| All sizes offered | Complete size range supported by the item |
| Sizes available | Sizes available at time of scrape |
| Timestamp | Availability check timestamp |
| Product images | Full image gallery |
| Raw product metadata | Description, materials, etc. |

> **This snapshot establishes eligibility, not a promise.**

---

## 2. Size Availability Model (Non-Real-Time)

### Core Rule

> **ReFitd does not check live inventory at generation time.**
>
> **Generation is a database operation, not a network operation.**

### Eligibility Logic

A product is eligible for a user if and only if:

1. The product **offered** the user's size at ingestion, AND
2. The availability snapshot is not beyond freshness limits

### Important Implications

| Scenario | Behavior |
|----------|----------|
| Product never offered size L | Never shown to size L users |
| Product offered size M at ingestion | May be shown to size M users later |

> This avoids false inclusion.

---

## 3. Freshness & Confidence Decay

Size availability becomes less reliable over time.

ReFitd models this using **confidence decay**, not binary expiration.

### Decay Factors

Availability confidence decays based on:

- Time since last check
- Category volatility
- Brand behavior
- Size type (core vs edge)

### Core vs Edge Sizes

The system encodes real-world retail behavior:

#### Core Sizes

| Examples | Behavior |
|----------|----------|
| M, L, 32, 10 | Sell out more slowly |
| | Can tolerate older snapshots |

#### Edge Sizes

| Examples | Behavior |
|----------|----------|
| XS, XL, uncommon numerics | Sell out faster |
| | Require fresher data |

### Result

- Core-size users see **broader inventory** safely
- Edge-size users see **fresher, narrower** results

> This reduces false confidence.

---

## 4. Staleness Rules (Silent, Not User-Facing)

Each product has an internal availability confidence score derived from:

- `last_checked_at`
- Size volatility
- Category volatility

### Staleness Behavior

| Condition | Action |
|-----------|--------|
| Recently checked items | Prioritized |
| Older items | Gradually deprioritized |
| Very stale items | Excluded unless no alternatives exist |

### Users are never shown:

- ❌ Explicit freshness scores
- ❌ "Low confidence" warnings
- ❌ Availability guarantees

> **The system handles this quietly.**

---

## 5. Refresh Queues (Selective, Event-Driven)

> **ReFitd does not continuously re-scrape the entire catalog.**
>
> Instead, refreshes are **targeted and justified**.

### Products Eligible for Refresh

- Frequently generated items
- Saved items
- Clicked items
- Items in many users' size ranges
- Items in volatile categories

### Refresh Triggers

Refresh jobs are enqueued when:

| Trigger | Description |
|---------|-------------|
| Item clicked | User interaction signal |
| Item saved | Strong interest signal |
| Item appears in many generations | High-value item |
| Freshness threshold crossed | Time-based decay |

### Refreshes Update:

- ✅ Available sizes
- ✅ `last_checked_at` timestamp

> **They do not block the user experience.**

---

## 6. Generation-Time Behavior (Important)

At generation time:

- ❌ No scraping occurs
- ❌ No retailer calls occur
- ❌ No guarantees are made

### The Generator:

1. Filters by stored size eligibility
2. Applies freshness thresholds
3. Ranks by style, price, and confidence-weighted availability

This keeps generation:

- **Fast**
- **Deterministic**
- **Reliable at scale**

---

## 7. Click-Time Reality Check

> **The retailer's product page is always authoritative.**

If a user clicks through and:

- Their size is unavailable
- The product is sold out

This is:

- ✅ Expected occasionally
- ✅ Acceptable
- ✅ Unavoidable without real-time checks

> **The system never claims otherwise.**

---

## 8. What This System Explicitly Does Not Do

- ❌ No live inventory scraping at generation
- ❌ No constant catalog crawling
- ❌ No size guarantees
- ❌ No "in stock" promises
- ❌ No blocking user flows for freshness

> **These are intentional constraints.**

---

## 9. UX & Trust Contract

User-facing language must reflect reality.

### Allowed Phrasing

| ✅ Allowed |
|-----------|
| "Based on availability" |
| "Likely available in your size" |
| "Inventory can change" |

### Disallowed Phrasing

| ❌ Disallowed |
|--------------|
| "Guaranteed in stock" |
| "Live availability" |
| "Real-time inventory" |

> **Trust comes from honesty, not precision theater.**

---

## 10. Failure Modes & Mitigations

### Item Out of Stock at Click

| Aspect | Response |
|--------|----------|
| Status | Expected |
| User action | Can regenerate or swap item |
| System response | Data feeds back into refresh prioritization |

### Size Missing After Click

| Aspect | Response |
|--------|----------|
| Status | Treated as signal, not failure |
| System response | Increases urgency for refresh |

### Retailer Changes Page Structure

| Aspect | Response |
|--------|----------|
| Impact | Affects ingestion, not generation |
| User impact | Does not break user flows |

---

## Mental Model

```
┌─────────────────────────────────────────────────────────────┐
│  Ingestion   →  captures a moment                           │
│  Freshness   →  decays over time                            │
│  Refreshes   →  are selective                               │
│  Retailers   →  are always right                            │
└─────────────────────────────────────────────────────────────┘
```

> **ReFitd optimizes for speed, scale, and trust — not illusionary certainty.**
