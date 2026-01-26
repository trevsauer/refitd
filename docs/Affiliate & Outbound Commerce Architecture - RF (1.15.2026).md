# ReFitd — Affiliate & Outbound Commerce Architecture

*Canonical Specification*

---

## Purpose

This document defines how ReFitd handles:

- Outbound product links
- Affiliate monetization
- Multi-retailer purchase flows
- Future checkout orchestration

Without coupling monetization logic to product data.

The system is designed to be:

- **Network-agnostic**
- **Low-maintenance**
- **Resilient to affiliate program changes**
- **Honest to users**
- **Compatible with future concierge and automation layers**

> **Affiliate logic is a transport concern, not a content concern.**

---

## Core Principles

1. Product data is always clean
2. Affiliate tracking happens at click time
3. No affiliate parameters are stored in the database
4. Outbound links are centralized
5. Failure never breaks the user experience
6. Future checkout automation must layer cleanly

---

## High-Level Architecture

Outbound commerce consists of four components:

```
┌─────────────────────────────────────────────────────────────┐
│  1. Clean Product URLs (Database Layer)                     │
│  2. Outbound Redirect Endpoint                              │
│  3. Affiliate Link Rewriting (Client Layer)                 │
│  4. Buy Outfit Orchestration                                │
└─────────────────────────────────────────────────────────────┘
```

Each layer has a single responsibility.

---

## 1. Clean Product URLs (Database Layer)

### Rule (Non-Negotiable)

> **The database stores only clean, canonical retailer URLs.**

**Example:**

```
https://www.zara.com/us/en/relaxed-fit-jacket-p01234567.html
```

### Never Store:

- ❌ Affiliate IDs
- ❌ Tracking parameters
- ❌ Redirects
- ❌ Shortened links

### Why This Matters

This keeps the system:

- **Scalable**
- **Maintainable**
- **Auditable**
- **Immune to affiliate network changes**

It also allows:

- Multiple affiliate networks
- Direct brand partnerships later
- Concierge checkout without refactoring

---

## 2. Outbound Redirect Endpoint

All outbound product clicks route through a single endpoint:

```
/out?u=<encoded_product_url>
```

### Responsibilities

- Receive encoded clean URL
- Issue a 302 redirect
- Allow affiliate scripts to rewrite the destination
- Provide a hook for:
  - Analytics
  - Attribution
  - Future checkout orchestration

### For MVP:

- This endpoint is a pass-through redirect
- No business logic is required here yet

---

## 3. Affiliate Monetization Strategy

### Primary Network: Sovrn (VigLink)

- Sovrn JavaScript snippet is loaded globally
- On outbound click:
  1. Sovrn detects supported merchants
  2. Rewrites the URL in real time
  3. Applies affiliate tracking
  4. Redirects the user

**This requires:**

- ✅ No per-product configuration
- ✅ No manual link generation

### Fallback Network: Skimlinks

To prevent lost monetization:

- Skimlinks is loaded as a fallback
- It rewrites outbound links not supported by Sovrn
- Only activates if Sovrn does not claim the link

### Script Load Order (Critical)

| Order | Network |
|-------|---------|
| 1 | Sovrn loads first |
| 2 | Skimlinks loads second |

**This prevents:**

- Double tracking
- Redirect conflicts
- Broken attribution

---

## 4. Click Behavior (Single Item)

When a user clicks an item name or image:

```
1. Link routes through /out
2. Affiliate scripts apply tracking (if supported)
3. User lands on retailer product page
4. Checkout happens entirely on the retailer site
```

**If no affiliate program exists:**

- ✅ User still lands correctly
- ✅ No monetization, no breakage

---

## 5. Buy Outfit Behavior (MVP)

### Current Behavior

- "Buy Outfit" opens each item in a separate tab
- Each tab routes independently through `/out`
- Affiliate tracking applies per item
- No cart merging or checkout automation

**This is:**

- ✅ Standard
- ✅ Acceptable
- ✅ Low risk
- ✅ Easy to reason about

### What Buy Outfit Is Not (Yet)

- ❌ Not a unified cart
- ❌ Not a single checkout
- ❌ Not guaranteed affiliate attribution on every item
- ❌ Not optimized for conversion initially

> Those are future layers.

---

## 6. Failure & Edge Case Handling

### Unsupported Retailer

| Step | Action |
|------|--------|
| 1 | Sovrn fails |
| 2 | Skimlinks attempts |
| 3 | If both fail: Clean URL redirect |

**Result:**

- No monetization
- No UX degradation

### Affiliate Program Changes

- ✅ No database updates required
- ✅ Only network configuration changes
- ✅ Product URLs remain valid

### Network Downtime

- ✅ Outbound links still function
- ✅ Worst case: no tracking
- ✅ Never block navigation

---

## 7. Relationship to Concierge Checkout

This architecture intentionally supports Concierge Checkout:

- Clean URLs allow ops to purchase directly
- No affiliate coupling in product data
- `/out` endpoint becomes:
  - Analytics hook
  - Orchestration trigger
  - Automation entry point later

### During Wizard-of-Oz Concierge:

- Affiliate attribution may be partially lost
- This is acceptable for validation
- No refactor required later

---

## 8. What This System Explicitly Avoids

- ❌ Manual affiliate link generation
- ❌ Per-product affiliate storage
- ❌ Network lock-in
- ❌ Scraping affiliate parameters
- ❌ Tight coupling between inventory and monetization

> **These choices preserve flexibility.**

---

## 9. Future-Proofing (Post-MVP)

This architecture supports future expansion without redesign:

| Future Capability | Status |
|-------------------|--------|
| Direct brand partnerships | Supported |
| Network overrides for higher commission rates | Supported |
| Click-level analytics and attribution | Supported |
| Unified checkout automation | Supported |
| Multi-retailer cart orchestration | Supported |
| Concierge-to-automation transition | Supported |

> All layer cleanly on top of `/out`.

---

## Mental Model

```
┌─────────────────────────────────────────────────────────────┐
│  Database    →  stores truth                                │
│  Outbound    →  handles monetization                        │
│  Retailers   →  handle checkout                             │
│  ReFitd      →  orchestrates, never impersonates            │
└─────────────────────────────────────────────────────────────┘
```

This keeps ReFitd:

- **Trustworthy**
- **Debuggable**
- **Scalable**
- **Monetization-flexible**

---

## Audience & Ownership

### Audience

- Backend engineering
- Web engineering
- Finance / monetization
- Partnerships

### Ownership

- Outbound routing service
- Affiliate configuration
- Commerce analytics

---

## One-Line Summary

> **Affiliate tracking is applied at click time, not stored in data, and never allowed to distort product selection or trust.**
