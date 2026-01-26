# ReFitd — Product Definition (Revised & Consolidated)

## Product Overview

ReFitd is a personal outfit-generation and shopping system that helps men assemble coherent outfits from real, in-stock retail products — tailored to their size, location, budget preferences, and evolving style contexts.

Instead of browsing catalogs or chasing inspiration, users interact with a Style Profile–driven generator that lets them:

- Define explicit shopping constraints
- Express intent in natural language
- Iteratively refine item stacks
- Purchase individual items or full outfits via affiliate links

The system learns within distinct style contexts (e.g. "Moroccan Summer," "Business Casual NYC"), allowing users to maintain multiple independent Style Profiles that evolve separately over time.

> **Long-term vision:** Make buying a coherent outfit across brands as simple — and confidence-inducing — as buying a single product.

---

## Core Product Principles

- Built around **decision-making**, not inspiration
- Uses **real retail inventory**, not generated images
- No avatars, no try-on, no compositing
- No social feed or influencer content
- No hidden algorithmic behavior
- Value comes from **what works together — and why**
- AI interprets intent; rules enforce reality

---

## 1. Account Creation & Onboarding

### Account Creation (Minimal)

When creating an account, users provide only:

| Field | Required |
|-------|----------|
| Location / shipping region | ✅ |
| Address | ✅ |
| Age | ✅ |

> No sizes, budgets, or style preferences are required at this stage.

### Onboarding (Explanatory, Not Configurational)

After account creation, onboarding explains:

- How the generator works
- The difference between:
  - **AI intent** (soft, directional biases)
  - **Filters & controls** (explicit hard rules)
- How price sliders and total price behave
- How to iterate using Generate, Lock, and Pass

> All actual configuration happens inside Style Profiles.

---

## 2. Style Profiles (Core Object)

Users can create multiple named Style Profiles, each representing a specific context or use case.

### Examples:

- Business Casual
- Moroccan Summer
- New York Winter

Each Style Profile is:

- ✅ Independent
- ✅ Persistent
- ✅ Fully editable
- ✅ Re-openable with all state preserved

> **Everything below is saved per Style Profile.**

---

## 3. Control Layer — Explicit Rules (Hard Constraints)

The Control Layer defines the literal rules the system must obey.

### Filters (Hard Rules)

Users can include or exclude:

- Colors
- Brands
- Retailers
- Sizes

These rules are:

- **Explicit**
- **Always enforced**
- **Never overridden by AI**

### Sizes (Optional)

Sizes can be set per category:

| Category | Examples |
|----------|----------|
| Top | S, M, L, XL |
| Bottom | 30, 32, 34 |
| Shoes | 9, 10, 11 |
| Outerwear | M, L, XL |

- If no sizes are selected → generator does not filter by size
- If sizes are selected → only compatible products are eligible

> This keeps early exploration friction-free while allowing precision later.

---

## 4. Intent Layer — AI Chat (Soft Biases, Fully Visible)

The AI chat interface translates natural-language intent into directional preferences, not rules.

### Example prompts:

- "I'm going to Morocco for the summer."
- "This should feel more relaxed."
- "I hate skinny pants."
- "This profile is for work, not weekends."

### AI-Derived Biases May Include:

| Bias Type | Example |
|-----------|---------|
| Fit preferences | Avoid slim bottoms |
| Silhouette tendencies | Relaxed, oversized |
| Fabric and material direction | Linen, breathable |
| Formality range | Casual to smart-casual |
| Color direction | Light vs dark, muted vs bold |
| Climate and context assumptions | Summer, tropical |

### Critical Design Choices

All AI outputs:

- ✅ Appear in a visible bias log
- ✅ Can be individually reverted
- ✅ Never override explicit filters or sizes

The AI does **not**:

- ❌ Select specific products
- ❌ Break constraints
- ❌ Apply irreversible changes

### Hard Filter Escalation (Important)

When user language is explicit and absolute (e.g. "no skinny pants"), the AI may:

1. Apply a strong bias immediately, and
2. Offer to convert that bias into a hard filter, **only after explicit user confirmation**

> **Mental model:**
> AI suggests direction → User confirms rules → Generator executes deterministically

---

## 5. Outfit Generation Engine (Unified)

The generation engine is the core interactive surface of ReFitd.

Users generate, refine, and converge on item stacks through a single continuous flow.

### Default Starting Stack

The generator initializes with four active slots:

1. Outerwear
2. Top (Base)
3. Bottom
4. Shoes

> This is a starting configuration, not a requirement.

### Stack & Category Controls (UPDATED)

- All slots are optional
- Users may turn any slot on or off
- **The only invariant:**
  - At least **two items** must be active at all times
  - No more than **four items** may be active

### Top Layer Slots

The Top category is split into two independent, optional slots:

| Slot | Includes |
|------|----------|
| **Top (Base)** | T-shirts, long-sleeve tees, shirts, polos |
| **Top (Mid)** | Sweaters, cardigans, hoodies, knit pullovers |

**Rules:**

- At most one Base Top slot
- At most one Mid Top slot
- Either or both may be enabled

### Outerwear Slot

- Outerwear is a distinct slot
- Includes jackets, coats, blazers, and vests
- May be enabled or disabled independently

### Valid Stack Examples (Non-Exhaustive)

| Stack Configuration |
|---------------------|
| Base Top + Mid Top |
| Base Top + Outerwear |
| Mid Top + Outerwear |
| Bottom + Shoes |
| Base Top + Bottom + Shoes |
| Outerwear + Mid Top + Bottom + Shoes |

> As long as 2–4 items are active, the stack is valid.

### Generation & Iteration

#### Generate

- Re-runs the full pipeline
- Respects all active constraints and biases
- Preserves locked items

#### Lock Item

- Item remains fixed across generations
- Acts as an anchor for the rest of the stack

#### Pass / Swap

- Only the passed item regenerates
- All other items remain unchanged

> **Mental model:**
> - Generate → explore
> - Lock → keep
> - Pass → fix one thing
> - Turn off → remove a slot
>
> No modes. No hidden state.

---

## 6. Price System (Always On, No Modes)

### Per-Item Budget Sliders

- Every item has its own min / max price slider
- Sliders move freely
- Total stack price updates automatically

> There is no enforced budget mode.

### Optional Total Budget Input

- If a total budget is entered first:
  - The system distributes realistic starting weights
- Users may override freely

> This is a convenience, not a constraint.

---

## 7. Saving & Reuse

### Save Stack → My Fits

- Saves a full snapshot
- Items remain linked to live product pages

### Save Item → Saved Items

- Individual products can be saved
- Saved items are reusable assets

### Build Around Saved Items

Any saved item can be:

- Inserted into an active Style Profile
- Locked into place
- Used as an anchor for new generation

---

## 8. Visual & Interaction Design (UPDATED)

### Stack View (Hard Rule)

- The generator stack displays **model-less product images only** (flat / ghost / product-only)
- Model-worn images are **never** shown in the stack

### Gallery View

- Clicking an item opens the full ingested product gallery
- Gallery includes all product images from the retailer page, including model-worn and detail shots

### Navigation

- Clicking an item name routes via affiliate link
- Opens the retailer's product page

---

## 9. Purchase Flow (Affiliate-First MVP)

- Each item links out individually
- **Buy Stack** opens all product pages in separate tabs
- Affiliate tracking is applied at click time
- Checkout occurs entirely on retailer sites

---

## 10. Community Style Profiles (Planned — V2)

> ⚠️ **Future feature, not shipped in MVP.**

- Public, locked Style Profiles
- Stable reference points
- Savable as private, editable copies
- No learning or mutation on the community version

---

## One-Line Summary

> **ReFitd helps men confidently assemble and shop item stacks from real retail inventory by combining explicit rules, visible AI intent, and a deterministic generator that prioritizes what actually works — not what just looks good.**

---

---

# ReFitd Monetization: Plus & Concierge Checkout

## Monetization Philosophy

**ReFitd monetizes confidence and convenience, not access to taste.**

- The core generator remains fully usable for free
- No monetization logic biases outfit generation
- Paid features unlock compounding value and execution, not better recommendations

> This preserves trust, learning quality, and long-term defensibility.

---

## Free Plan (Default)

Free users can fully explore and use the generator.

### Included

- ✅ Unlimited outfit generations
- ✅ Full access to:
  - AI intent chat
  - Hard filters (colors, brands, retailers, sizes)
  - Generate / Lock / Pass / Turn Off categories
- ✅ Affiliate purchase links
- ✅ Up to **3 Style Profiles**
- ✅ Up to **5 saved outfits**

### Limitations

- ❌ Saved items and outfits cannot be reused as anchors in the generator

> Free is for exploration, not accumulation.
>
> **Free users learn what they like. They just can't compound it deeply.**

---

## ReFitd Plus — $15 / month

**Plus unlocks accumulation, reuse, and control.**

It does not promise better outfits — only deeper ownership of taste.

### Plus Features

#### 1. Unlimited Profiles & Saves

- Unlimited Style Profiles
- Unlimited saved outfits
- Unlimited saved items

> Supports users with many contexts and long-term use.

#### 2. Build Around Saved Items (Core Plus Feature)

Plus users can:

- Pull an item from:
  - Saved Items, or
  - Saved Outfits
- Insert it directly into an active generator
- Lock it in place
- Generate outfits around that specific item

This enables workflows like:

- "I already own this jacket — build outfits around it"
- "Reuse these shoes across profiles"
- "Start here, not from scratch"

> ⚠️ **This feature is Plus-only.**

### Mental Model

| Tier | Purpose |
|------|---------|
| **Free** | Discover taste |
| **Plus** | Compound taste |

---

## Concierge Checkout — $25 per Outfit (Experimental)

Concierge Checkout is an optional, paid execution layer for users who want zero friction at purchase time.

> ⚠️ **Explicitly a Wizard-of-Oz experiment to validate demand before automation.**

### How Concierge Checkout Works (Clean MVP Flow)

#### 1. Eligibility

- Concierge Checkout is available to **Plus subscribers only**
- This ensures:
  - Serious intent
  - Lower abuse
  - Higher trust on both sides

#### 2. User Initiates Concierge Checkout

When a user clicks "Concierge Checkout", they see a clear breakdown:

| Line Item | Amount |
|-----------|--------|
| Outfit subtotal | $X |
| Estimated tax & shipping | $Y (estimated) |
| Concierge fee | $25 |
| **Total charged now** | **$X + $Y + $25** |

**Clear disclosure copy (critical):**

> "We'll place the order for you within a few hours. Final totals may vary slightly based on retailer shipping and tax. Any difference is automatically refunded."

No second charges. No surprises.

#### 3. Single Upfront Charge (With Small Buffer)

- The full amount is charged once, immediately
- Estimated tax & shipping includes a small buffer (e.g. 5–8%)
- This avoids:
  - Re-charging later
  - Card failures mid-checkout
  - Trust anxiety

**If the final total is lower:**
- The difference is automatically refunded

> Users tolerate refunds far better than unexpected charges.

#### 4. Internal Execution Window (Speed Without Rushing)

- Ops is notified immediately
- Orders are placed within 1–5 hours during business hours

**User-facing language:**

> "Orders are placed within a few hours during business hours."

This frames the wait as intentional, not slow.

#### 5. Manual Checkout (Wizard-of-Oz)

An ops team member:

1. Opens each product page
2. Selects correct size and color
3. Completes checkout at each retailer
4. Ships items directly to the customer

**ReFitd does not:**

- Modify products without approval
- Guarantee availability beyond best effort

**If an item is unavailable:**

- Closest substitute is proposed, or
- That item is refunded

#### 6. Confirmation & Refunds

After checkout:

- User is notified that the order has been placed
- Any unused buffer is refunded automatically
- Concierge fee becomes non-refundable once ordering begins

**Order status only needs 3 states:**

| Status |
|--------|
| Received |
| Placed |
| Shipped |

> No noisy tracking required.

### Shipping & Taxes (Explicit Contract)

- ReFitd does **not** cover shipping
- Shipping and taxes are whatever the retailer charges
- These costs are included in the final amount charged
- Retailer policies apply for delivery and returns

> This is clearly communicated before purchase.

### Affiliate Reality (Early-Stage Honesty)

During Concierge Checkout:

- Affiliate attribution may be partially or fully lost

This is acceptable during the experiment.

**The goal is to validate:**

- Will users pay for "don't make me think" checkout?
- At what price?
- How often?

**If validated, future options include:**

- Automated multi-retailer checkout
- Brand partnerships
- Hybrid affiliate + concierge flows

---

## Mental Model (End-to-End)

```
┌─────────────────────────────────────────────────────────────┐
│  Free       →  explore outfits                              │
│  Plus ($15) →  accumulate, reuse, and refine taste          │
│  Concierge  →  outsource execution entirely                 │
└─────────────────────────────────────────────────────────────┘
```

Each layer monetizes a different user need:

| Need | Tier |
|------|------|
| Curiosity | Free |
| Confidence | Plus |
| Convenience | Concierge |

> **None compromise the generator.**

---

## Why This Works

- ✅ No double charging
- ✅ No hidden uncertainty
- ✅ No false promises
- ✅ Minimal ops complexity
- ✅ High perceived value
- ✅ Clean learning signal preserved

> **This is the safest possible way to test concierge without breaking trust or your sanity.**
