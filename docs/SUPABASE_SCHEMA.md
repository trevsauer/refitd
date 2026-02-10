# ReFitd — Supabase Database Schema

> **Auto-generated reference** — Last updated 2026-02-10
>
> Database: **Supabase PostgreSQL** (project `uochfddhtkzrvcmfwksm`)
>
> Source of truth: [`docs/supabase_schema.sql`](./supabase_schema.sql) + [`docs/migrations/`](./migrations/)

---

## Table of Contents

1. [Entity-Relationship Overview](#entity-relationship-overview)
2. [Tables](#tables)
   - [`products`](#products) — Core product catalog
   - [`curated_metadata`](#curated_metadata) — Human-curated tag additions
   - [`rejected_inferred_tags`](#rejected_inferred_tags) — Rejected AI/inferred tags (ML training data)
   - [`curation_status`](#curation_status) — Per-product curation completion tracking
   - [`ai_generated_tags`](#ai_generated_tags) — AI vision-model generated tags
   - [`custom_vocabulary`](#custom_vocabulary) — User-defined vocabulary extensions
   - [`access_logs`](#access_logs) — API/data access audit log
3. [Views](#views)
4. [Functions & Triggers](#functions--triggers)
5. [Row-Level Security (RLS)](#row-level-security-rls)
6. [Supabase Storage](#supabase-storage)
7. [Local SQLite (Tracking DB)](#local-sqlite-tracking-db)

---

## Entity-Relationship Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          RELATIONSHIP DIAGRAM                               │
│                                                                              │
│  ┌─────────────────────┐                                                     │
│  │      products        │◄─── Central table, all others reference this       │
│  │  (PK: product_id)   │                                                     │
│  └──────┬──┬──┬──┬─────┘                                                     │
│         │  │  │  │                                                            │
│         │  │  │  │  ┌─────────────────────────┐                              │
│         │  │  │  └──┤   curated_metadata       │  Human-curated tags          │
│         │  │  │     │  FK: product_id ──►       │  (style_tag, fit, weight)   │
│         │  │  │     │  ON DELETE CASCADE        │                              │
│         │  │  │     └─────────────────────────┘                              │
│         │  │  │                                                               │
│         │  │  │     ┌─────────────────────────┐                              │
│         │  │  └─────┤  rejected_inferred_tags  │  Rejected AI tags            │
│         │  │        │  FK: product_id ──►       │  (ML training feedback)     │
│         │  │        │  ON DELETE CASCADE        │                              │
│         │  │        └─────────────────────────┘                              │
│         │  │                                                                  │
│         │  │        ┌─────────────────────────┐                              │
│         │  └────────┤    curation_status       │  Curation completion          │
│         │           │  FK: product_id ──►       │  (one status per product)   │
│         │           │  ON DELETE CASCADE        │                              │
│         │           └─────────────────────────┘                              │
│         │                                                                     │
│         │           ┌─────────────────────────┐                              │
│         └───────────┤   ai_generated_tags      │  AI vision-model tags        │
│                     │  FK: product_id ──►       │  (moondream, etc.)          │
│                     │  ON DELETE CASCADE        │                              │
│                     └─────────────────────────┘                              │
│                                                                              │
│  ┌─────────────────────┐        ┌─────────────────────────┐                 │
│  │  custom_vocabulary   │        │     access_logs          │                 │
│  │  (standalone)        │        │  (standalone audit log)  │                 │
│  └─────────────────────┘        └─────────────────────────┘                 │
│                                                                              │
│  Self-referencing within products:                                            │
│  products.parent_product_id ──► products.product_id  (color variants)        │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Relationship Summary

| Parent Table | Child Table | FK Column | Relationship | On Delete |
|---|---|---|---|---|
| `products` | `curated_metadata` | `product_id` | One-to-Many | CASCADE |
| `products` | `rejected_inferred_tags` | `product_id` | One-to-Many | CASCADE |
| `products` | `curation_status` | `product_id` | One-to-One | CASCADE |
| `products` | `ai_generated_tags` | `product_id` | One-to-Many | CASCADE |
| `products` | `products` *(self)* | `parent_product_id` | One-to-Many *(variants)* | — |

The **`custom_vocabulary`** and **`access_logs`** tables are standalone and do not reference `products`.

---

## Tables

### `products`

> **Central product catalog.** Stores all scraped product metadata, images, pricing, inferred attributes, and canonical ReFitd tags.

| Column | Type | Default | Nullable | Description |
|---|---|---|---|---|
| `product_id` | `TEXT` | — | **PK, NOT NULL** | Unique product identifier (e.g., `"zara-12345678"`) |
| `name` | `TEXT` | — | NOT NULL | Product display name |
| `category` | `TEXT` | — | NOT NULL | Product category (e.g., `"tshirts"`, `"jackets"`) |
| `url` | `TEXT` | — | NOT NULL | Source product page URL |
| `price_current` | `DECIMAL(10,2)` | — | Yes | Current selling price |
| `price_original` | `DECIMAL(10,2)` | — | Yes | Original price before discount |
| `currency` | `TEXT` | `'USD'` | Yes | ISO currency code |
| `description` | `TEXT` | — | Yes | Product description text |
| `colors` | `TEXT[]` | `'{}'` | Yes | All available color options for the product |
| `color` | `TEXT` | — | Yes | Single color for this variant (if expanded by color) |
| `parent_product_id` | `TEXT` | — | Yes | Original product ID if this row is a color variant (self-referencing) |
| `sizes` | `TEXT[]` | `'{}'` | Yes | Simple list of size labels (`['S', 'M', 'L']`) |
| `sizes_availability` | `JSONB` | `'[]'` | Yes | Size objects with availability: `[{"size": "M", "available": true}]` |
| `sizes_checked_at` | `TIMESTAMPTZ` | — | Yes | Timestamp when size availability was last checked |
| `materials` | `TEXT[]` | `'{}'` | Yes | Material/fabric list |
| `fit` | `TEXT` | — | Yes | Fit type (`slim`, `regular`, `oversized`, etc.) |
| `composition` | `TEXT` | — | Yes | Fabric composition string (e.g., `"100% cotton"`) — legacy format |
| `composition_structured` | `JSONB` | — | Yes | Hierarchical composition data: `{"parts": [...]}` with areas/components |
| `weight` | `JSONB` | — | Yes | Inferred weight: `{"value": "light\|medium\|heavy", "reasoning": [...]}` |
| `style_tags` | `JSONB` | — | Yes | Inferred style tags: `[{"tag": "minimal", "reasoning": "..."}]` |
| `formality` | `JSONB` | — | Yes | Inferred formality: `{"score": 1-5, "label": "...", "reasoning": [...]}` |
| `image_paths` | `TEXT[]` | `'{}'` | Yes | Storage paths in Supabase Storage bucket |
| `image_count` | `INTEGER` | `0` | Yes | Number of stored images |
| `tags_ai_raw` | `JSONB` | — | Yes | **Immutable** AI sensor output with confidence scores (ReFitd tagging layer 1) |
| `tags_final` | `JSONB` | — | Yes | Canonical tags for the generator — no confidence scores (ReFitd tagging layer 3) |
| `curation_status_refitd` | `TEXT` | `'pending'` | Yes | ReFitd curation status: `'approved'`, `'needs_review'`, `'needs_fix'`, `'pending'` |
| `tag_policy_version` | `TEXT` | — | Yes | Policy version used to produce `tags_final` (e.g., `'tag_policy_v2.0'`) |
| `curation_notes_refitd` | `TEXT` | — | Yes | Free-text curator comments on the product |
| `scraped_at` | `TIMESTAMPTZ` | `NOW()` | Yes | When the product was scraped |
| `created_at` | `TIMESTAMPTZ` | `NOW()` | Yes | Row creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOW()` | Yes | Auto-updated on every `UPDATE` via trigger |

#### Indexes

| Index Name | Column(s) | Type |
|---|---|---|
| `idx_products_category` | `category` | B-tree |
| `idx_products_scraped_at` | `scraped_at` | B-tree |
| `idx_products_price` | `price_current` | B-tree |
| `idx_products_parent_product_id` | `parent_product_id` | B-tree |
| `idx_products_color` | `color` | B-tree |
| `idx_products_curation_status` | `curation_status_refitd` | B-tree |
| `idx_products_tag_policy_version` | `tag_policy_version` | B-tree |
| `idx_products_tags_final` | `tags_final` | **GIN** (JSONB) |

#### JSONB Column Schemas

<details>
<summary><strong><code>weight</code></strong> — Inferred weight assessment</summary>

```json
{
  "value": "light",        // "light" | "medium" | "heavy"
  "reasoning": [
    "Linen is a lightweight, breathable natural fiber"
  ]
}
```
</details>

<details>
<summary><strong><code>style_tags</code></strong> — Inferred style tags</summary>

```json
[
  {"tag": "minimal",  "reasoning": "Name contains 'basic'"},
  {"tag": "casual",   "reasoning": "Category 'tshirts' is typically this style"}
]
```
</details>

<details>
<summary><strong><code>formality</code></strong> — Formality assessment</summary>

```json
{
  "score": 3,                   // 1 (Very Casual) → 5 (Formal)
  "label": "Smart Casual",
  "reasoning": [
    "Base: sweater (3/5)",
    "Material: casual (-0.3)",
    "Color: darker/formal (+0.3)"
  ]
}
```
</details>

<details>
<summary><strong><code>sizes_availability</code></strong> — Sizes with stock status</summary>

```json
[
  {"size": "S",  "available": true},
  {"size": "M",  "available": true},
  {"size": "L",  "available": false},
  {"size": "XL", "available": true}
]
```
</details>

<details>
<summary><strong><code>composition_structured</code></strong> — Hierarchical fabric composition</summary>

```json
{
  "parts": [
    {
      "part_name": "OUTER SHELL",
      "areas": [
        {
          "area_name": "main",
          "components": [
            {"material": "polyamide", "percentage": 49},
            {"material": "polyester", "percentage": 29},
            {"material": "elastane",  "percentage": 22}
          ]
        }
      ]
    }
  ]
}
```
</details>

<details>
<summary><strong><code>tags_ai_raw</code></strong> — Raw AI sensor output (immutable)</summary>

```json
{
  "style_identity": [
    {"tag": "minimalist", "confidence": 0.92},
    {"tag": "modern",     "confidence": 0.78}
  ],
  "formality": {"value": "smart-casual", "confidence": 0.85},
  "weight":    {"value": "medium",       "confidence": 0.70},
  "model": "moondream",
  "generated_at": "2026-01-15T12:00:00Z"
}
```
</details>

<details>
<summary><strong><code>tags_final</code></strong> — Canonical tags for generator (no confidence)</summary>

```json
{
  "style_identity": ["minimalist", "modern"],
  "formality": "smart-casual",
  "weight": "medium",
  "fit": "regular",
  "occasion": ["everyday", "office"]
}
```
</details>

---

### `curated_metadata`

> **Human-curated additions** to product metadata. Original scraped/inferred metadata is never modified; curated data is stored in this separate table and merged at read time.

| Column | Type | Default | Nullable | Constraints | Description |
|---|---|---|---|---|---|
| `id` | `SERIAL` | auto-increment | **PK** | — | Row ID |
| `product_id` | `TEXT` | — | NOT NULL | **FK → `products.product_id`** ON DELETE CASCADE | Product being curated |
| `field_name` | `TEXT` | — | NOT NULL | — | Which attribute: `'style_tag'`, `'fit'`, `'weight'` |
| `field_value` | `TEXT` | — | NOT NULL | — | The curated value |
| `curator` | `TEXT` | — | NOT NULL | — | Who added it (e.g., `'Reed'`, `'Gigi'`, `'Kiki'`) |
| `created_at` | `TIMESTAMPTZ` | `NOW()` | Yes | — | When curated |

**Unique constraint:** `(product_id, field_name, field_value, curator)` — prevents duplicate entries.

#### Indexes

| Index Name | Column(s) |
|---|---|
| `idx_curated_product_id` | `product_id` |
| `idx_curated_curator` | `curator` |

---

### `rejected_inferred_tags`

> **Rejected AI/inferred tags** that curators marked as incorrect. Preserved for **ML model training** — the original inferred tag stays in `products` but is displayed with strikethrough styling in the UI.

| Column | Type | Default | Nullable | Constraints | Description |
|---|---|---|---|---|---|
| `id` | `SERIAL` | auto-increment | **PK** | — | Row ID |
| `product_id` | `TEXT` | — | NOT NULL | **FK → `products.product_id`** ON DELETE CASCADE | Product with the bad tag |
| `field_name` | `TEXT` | — | NOT NULL | — | Tag type: `'style_tag'`, `'fit'`, `'weight'`, `'formality'` |
| `field_value` | `TEXT` | — | NOT NULL | — | The rejected tag value |
| `original_reasoning` | `TEXT` | — | Yes | — | ML model's original reasoning for inference |
| `curator` | `TEXT` | — | NOT NULL | — | Who rejected it |
| `rejection_reason` | `TEXT` | — | Yes | — | Why the curator thinks it's wrong |
| `created_at` | `TIMESTAMPTZ` | `NOW()` | Yes | — | When rejected |

**Unique constraint:** `(product_id, field_name, field_value)` — one rejection per tag per product.

#### Indexes

| Index Name | Column(s) |
|---|---|
| `idx_rejected_product_id` | `product_id` |
| `idx_rejected_field_name` | `field_name` |
| `idx_rejected_created_at` | `created_at` |

---

### `curation_status`

> **Per-product curation completion tracking.** Records when a product has been fully reviewed and approved by a curator.

| Column | Type | Default | Nullable | Constraints | Description |
|---|---|---|---|---|---|
| `id` | `SERIAL` | auto-increment | **PK** | — | Row ID |
| `product_id` | `TEXT` | — | NOT NULL | **FK → `products.product_id`** ON DELETE CASCADE | Product that was curated |
| `curator` | `TEXT` | — | NOT NULL | — | Who marked it complete |
| `status` | `TEXT` | `'complete'` | NOT NULL | — | Status value (currently always `'complete'`) |
| `notes` | `TEXT` | — | Yes | — | Optional curation notes |
| `created_at` | `TIMESTAMPTZ` | `NOW()` | Yes | — | When marked complete |
| `updated_at` | `TIMESTAMPTZ` | `NOW()` | Yes | — | Last update |

**Unique constraint:** `(product_id)` — at most one status per product.

#### Indexes

| Index Name | Column(s) |
|---|---|
| `idx_curation_status_product` | `product_id` |
| `idx_curation_status_curator` | `curator` |
| `idx_curation_status_created` | `created_at` |

---

### `ai_generated_tags`

> **Tags generated by AI vision models** (e.g., Moondream via Ollama). Separate from inferred tags (text analysis, in `products.style_tags`) and human-curated tags (in `curated_metadata`). Displayed with a distinct **teal/cyan** color in the UI.

| Column | Type | Default | Nullable | Constraints | Description |
|---|---|---|---|---|---|
| `id` | `SERIAL` | auto-increment | **PK** | — | Row ID |
| `product_id` | `TEXT` | — | NOT NULL | **FK → `products.product_id`** ON DELETE CASCADE | Product that was tagged |
| `field_name` | `TEXT` | `'style_tag'` | NOT NULL | — | Tag type: `'style_tag'`, `'fit'`, `'weight'`, etc. |
| `field_value` | `TEXT` | — | NOT NULL | — | The AI-generated tag value |
| `model_name` | `TEXT` | `'moondream'` | Yes | — | Which AI model generated this |
| `confidence` | `DECIMAL(3,2)` | — | Yes | — | Confidence score `0.00 – 1.00` |
| `reasoning` | `TEXT` | — | Yes | — | Optional reasoning from the AI |
| `created_at` | `TIMESTAMPTZ` | `NOW()` | Yes | — | When generated |

**Unique constraint:** `(product_id, field_name, field_value)` — no duplicate tags per product.

#### Indexes

| Index Name | Column(s) |
|---|---|
| `idx_ai_tags_product_id` | `product_id` |
| `idx_ai_tags_field_name` | `field_name` |
| `idx_ai_tags_model` | `model_name` |
| `idx_ai_tags_created_at` | `created_at` |

---

### `custom_vocabulary`

> **User-defined vocabulary terms** that extend the default AI tag vocabulary. Merged with built-in vocabulary (defined in `src/ai/style_tagger.py`) at runtime when the AI generates tags.

| Column | Type | Default | Nullable | Constraints | Description |
|---|---|---|---|---|---|
| `id` | `SERIAL` | auto-increment | **PK** | — | Row ID |
| `category` | `TEXT` | — | NOT NULL | — | Vocabulary category (e.g., `'aesthetic'`, `'vibe'`, `'mood'`) |
| `tag` | `TEXT` | — | NOT NULL | — | The vocabulary term |
| `created_at` | `TIMESTAMPTZ` | `NOW()` | Yes | — | When added |

**Unique constraint:** `(category, tag)` — prevents duplicate tags in the same category.

#### Indexes

| Index Name | Column(s) |
|---|---|
| `idx_custom_vocab_category` | `category` |
| `idx_custom_vocab_tag` | `tag` |

---

### `access_logs`

> **API/data access audit log.** Tracks all reads and writes for security auditing and usage pattern analysis. Added in [Migration 001](./migrations/001_rls_public_read_and_access_logs.sql).

| Column | Type | Default | Nullable | Constraints | Description |
|---|---|---|---|---|---|
| `id` | `BIGSERIAL` | auto-increment | **PK** | — | Row ID |
| `accessed_at` | `TIMESTAMPTZ` | `NOW()` | Yes | — | When access occurred |
| `table_name` | `TEXT` | — | NOT NULL | — | Table accessed: `'products'`, `'curated_metadata'`, etc. |
| `operation` | `TEXT` | — | NOT NULL | — | SQL operation: `'SELECT'`, `'INSERT'`, `'UPDATE'`, `'DELETE'` |
| `query_description` | `TEXT` | — | Yes | — | Human-readable description of the request |
| `access_role` | `TEXT` | — | Yes | — | Supabase role: `'anon'`, `'service_role'`, `'authenticated'` |
| `client_source` | `TEXT` | — | Yes | — | Calling module: `'viewer.py'`, `'supabase_loader.py'`, `'external'` |
| `client_ip` | `TEXT` | — | Yes | — | Client IP address if available |
| `row_count` | `INTEGER` | — | Yes | — | Number of rows returned/affected |
| `product_ids` | `TEXT[]` | — | Yes | — | Specific product IDs if applicable |
| `category_filter` | `TEXT` | — | Yes | — | Category filter if used |
| `endpoint` | `TEXT` | — | Yes | — | API endpoint (e.g., `'/api/products'`, `'get_products()'`) |
| `request_metadata` | `JSONB` | `'{}'` | Yes | — | Additional context |

#### Indexes

| Index Name | Column(s) |
|---|---|
| `idx_access_logs_accessed_at` | `accessed_at` |
| `idx_access_logs_table_name` | `table_name` |
| `idx_access_logs_operation` | `operation` |
| `idx_access_logs_client_source` | `client_source` |
| `idx_access_logs_access_role` | `access_role` |

---

## Views

### Data Views

| View | Source Table(s) | Purpose |
|---|---|---|
| `product_stats` | `products` | Aggregate stats: total products, categories, min/max/avg price, total images |
| `category_summary` | `products` | Product count and avg price grouped by category |
| `curation_summary` | `products` ⟕ `curation_status` | Curation progress: total, curated, pending counts and % complete |
| `category_curation_summary` | `products` ⟕ `curation_status` | Curation progress broken down by category |
| `ml_rejected_tags_training` | `rejected_inferred_tags` ⟗ `products` | Training dataset export: rejected tags joined with product name, category, description |
| `ai_tags_summary` | `ai_generated_tags` | AI tag counts by model with unique tag counts |
| `custom_vocabulary_summary` | `custom_vocabulary` | Tag counts and arrays grouped by vocabulary category |

### ReFitd Tagging Views

| View | Source Table(s) | Purpose |
|---|---|---|
| `refitd_tagging_summary` | `products` | Tagging pipeline progress: tagged/untagged counts, approval status breakdown, % tagged/approved |
| `refitd_style_distribution` | `products` (JSONB unnest) | Distribution of style identity tags across products |
| `refitd_formality_distribution` | `products` (JSONB extract) | Distribution of formality levels (athletic → formal) |

### Access Log Views

| View | Source Table(s) | Purpose |
|---|---|---|
| `access_log_recent` | `access_logs` | Last 24 hours: request counts grouped by table/operation/source/role |
| `access_log_hourly` | `access_logs` | Hourly request counts for the last 7 days |
| `access_log_endpoints` | `access_logs` | Top accessed endpoints with avg rows returned |

---

## Functions & Triggers

### `update_updated_at_column()` — Trigger Function

Automatically sets `updated_at = NOW()` on every row `UPDATE` in the `products` table.

```sql
CREATE TRIGGER update_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

### `log_access(...)` — Stored Procedure

Helper function callable from Python to insert access log entries. Uses `SECURITY DEFINER` to ensure it always succeeds regardless of the calling role.

```sql
log_access(
    p_table_name TEXT,
    p_operation TEXT,
    p_client_source TEXT DEFAULT NULL,
    p_query_description TEXT DEFAULT NULL,
    p_row_count INTEGER DEFAULT NULL,
    p_product_ids TEXT[] DEFAULT NULL,
    p_category_filter TEXT DEFAULT NULL,
    p_endpoint TEXT DEFAULT NULL,
    p_request_metadata JSONB DEFAULT '{}'
) RETURNS VOID
```

---

## Row-Level Security (RLS)

All tables have **RLS enabled**. After [Migration 001](./migrations/001_rls_public_read_and_access_logs.sql), the original "Allow all access" policies were replaced with granular role-based policies:

### Policy Matrix

| Table | `anon` (public key) | `authenticated` | `service_role` |
|---|---|---|---|
| `products` | **SELECT** only | ALL | ALL |
| `curated_metadata` | **SELECT** only | ALL | ALL |
| `rejected_inferred_tags` | **SELECT** only | ALL | ALL |
| `curation_status` | **SELECT** only | ALL | ALL |
| `ai_generated_tags` | **SELECT** only | ALL | ALL |
| `custom_vocabulary` | **SELECT** only | ALL | ALL |
| `access_logs` | **SELECT + INSERT** | ALL | ALL |

**Key notes:**
- The **anon** key (public) can only **read** data from all product-related tables.
- The **anon** key can also **insert** into `access_logs` (so the public client can record its own access).
- The **service_role** key (used by the scraper/admin) has full CRUD access everywhere.
- The **authenticated** role (for future Supabase Auth integration) has full CRUD access.

---

## Supabase Storage

### Bucket: `product-images`

| Setting | Value |
|---|---|
| Bucket name | `product-images` |
| Public access | **Yes** |
| Path format | `{category}/{product_id}/image_{index}.{ext}` |
| Supported formats | `.jpg`, `.png`, `.webp`, `.gif` |

**Public URL pattern:**
```
https://uochfddhtkzrvcmfwksm.supabase.co/storage/v1/object/public/product-images/{category}/{product_id}/image_0.jpg
```

The `products.image_paths` array stores the relative paths within the bucket.

---

## Local SQLite (Tracking DB)

> **Separate from Supabase.** A lightweight local SQLite database (`data/tracking.db`) used to avoid re-scraping products. This is NOT stored in Supabase.

### Table: `scraped_products`

| Column | Type | Nullable | Description |
|---|---|---|---|
| `product_id` | `TEXT` | **PK, NOT NULL** | Unique product identifier |
| `url` | `TEXT` | NOT NULL | Product page URL |
| `category` | `TEXT` | NOT NULL | Product category |
| `name` | `TEXT` | NOT NULL | Product name |
| `price` | `REAL` | Yes | Current price |
| `scraped_at` | `TEXT` | NOT NULL | ISO 8601 timestamp of first scrape |
| `updated_at` | `TEXT` | NOT NULL | ISO 8601 timestamp of last update |

**Indexes:** `idx_category` on `category`, `idx_scraped_at` on `scraped_at`.

---

## Tag Architecture — Three-Layer System

The ReFitd tagging system uses three distinct layers of tags, each stored in different locations:

```
Layer 1 — Inferred Tags (text analysis)
  └─► products.style_tags, products.weight, products.formality, products.fit
  └─► Generated by: src/transformers/product_transformer.py
  └─► Can be rejected → rejected_inferred_tags table

Layer 2 — AI Vision Tags (image analysis)
  └─► ai_generated_tags table
  └─► Generated by: AI vision models (Moondream via Ollama)
  └─► Displayed in teal/cyan in the UI

Layer 3 — Human Curated Tags
  └─► curated_metadata table
  └─► Added manually by curators (Reed, Gigi, Kiki)
  └─► Displayed in gold in the UI

ReFitd Canonical Pipeline:
  products.tags_ai_raw  →  Policy Layer (Python)  →  products.tags_final
  (immutable sensor)       (thresholds/rules)        (canonical for generator)
```

---

## Color Variant Model

Products can be expanded into color variants. When this happens:

- A **parent product** has `color = NULL` and `colors = ['Black', 'White', 'Navy']`
- Each **variant** has:
  - Its own `product_id` (e.g., `"zara-12345678-black"`)
  - `parent_product_id` pointing to the original
  - `color = 'Black'` (single color for this variant)
  - Its own images in Supabase Storage

This is a **soft self-reference** — `parent_product_id` is not enforced by a formal FK constraint in the SQL, but is used conventionally by the application layer.
