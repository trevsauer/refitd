-- Supabase SQL Schema for Zara Product Scraper
-- Run this SQL in your Supabase SQL Editor to create the required table
-- https://supabase.com/dashboard/project/_/sql

-- Products table for storing scraped product metadata
CREATE TABLE IF NOT EXISTS products (
    -- Primary key
    product_id TEXT PRIMARY KEY,

    -- Basic product info
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    url TEXT NOT NULL,

    -- Pricing
    price_current DECIMAL(10, 2),
    price_original DECIMAL(10, 2),
    currency TEXT DEFAULT 'USD',

-- Product details
    description TEXT,
    colors TEXT[] DEFAULT '{}',       -- All available colors for the product
    color TEXT,                       -- Single color for this variant (if expanded)
    parent_product_id TEXT,           -- Original product ID if this is a color variant
    sizes TEXT[] DEFAULT '{}',
    materials TEXT[] DEFAULT '{}',
    fit TEXT,
    composition TEXT,  -- Fabric composition (e.g., "100% cotton", "49% polyamide, 29% polyester...")

    -- Inferred product attributes
    weight JSONB,           -- Weight info: {"value": "light/medium/heavy", "reasoning": [...]}
    style_tags JSONB,       -- Style tags: [{"tag": "minimal", "reasoning": "..."}, ...]
    formality JSONB,        -- Formality: {"score": 1-5, "label": "...", "reasoning": [...]}

    -- Image storage paths (in Supabase Storage)
    image_paths TEXT[] DEFAULT '{}',
    image_count INTEGER DEFAULT 0,

    -- Timestamps
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_scraped_at ON products(scraped_at);
CREATE INDEX IF NOT EXISTS idx_products_price ON products(price_current);

-- ============================================
-- MIGRATION: Add missing columns to existing table
-- Run this if you already have a products table
-- ============================================
ALTER TABLE products ADD COLUMN IF NOT EXISTS weight JSONB;
ALTER TABLE products ADD COLUMN IF NOT EXISTS style_tags JSONB;
ALTER TABLE products ADD COLUMN IF NOT EXISTS formality JSONB;
ALTER TABLE products ADD COLUMN IF NOT EXISTS composition TEXT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS color TEXT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS parent_product_id TEXT;

-- Index for efficient variant lookups
CREATE INDEX IF NOT EXISTS idx_products_parent_product_id ON products(parent_product_id);
CREATE INDEX IF NOT EXISTS idx_products_color ON products(color);

-- ============================================
-- MIGRATION: Update sizes column to JSONB for availability tracking
-- Run this to enable size availability tracking
-- ============================================
-- Note: This converts the existing TEXT[] to JSONB format
-- Old format: ['S', 'M', 'L']
-- New format: [{"size": "S", "available": true}, {"size": "M", "available": true}]

-- First, add a new JSONB column for sizes with availability
ALTER TABLE products ADD COLUMN IF NOT EXISTS sizes_availability JSONB DEFAULT '[]';

-- If you want to migrate existing TEXT[] sizes to JSONB format, run:
-- UPDATE products SET sizes_availability = (
--     SELECT jsonb_agg(jsonb_build_object('size', s, 'available', true))
--     FROM unnest(sizes) AS s
-- )
-- WHERE sizes IS NOT NULL AND array_length(sizes, 1) > 0;

-- Enable Row Level Security (RLS) - optional but recommended
ALTER TABLE products ENABLE ROW LEVEL SECURITY;

-- Policy to allow all operations (adjust based on your needs)
-- For a personal project, this allows full access
CREATE POLICY "Allow all access" ON products
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to call the function on updates
CREATE TRIGGER update_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Optional: Create a view for quick product stats
CREATE OR REPLACE VIEW product_stats AS
SELECT
    COUNT(*) as total_products,
    COUNT(DISTINCT category) as total_categories,
    MIN(price_current) as min_price,
    MAX(price_current) as max_price,
    AVG(price_current) as avg_price,
    SUM(image_count) as total_images
FROM products;

-- Optional: Category summary view
CREATE OR REPLACE VIEW category_summary AS
SELECT
    category,
    COUNT(*) as product_count,
    AVG(price_current) as avg_price,
    MIN(scraped_at) as first_scraped,
    MAX(scraped_at) as last_scraped
FROM products
GROUP BY category
ORDER BY product_count DESC;

-- ============================================
-- CURATED METADATA TABLE
-- ============================================
-- Stores user-curated additions to product metadata
-- Original metadata is never modified; curated data is stored separately

CREATE TABLE IF NOT EXISTS curated_metadata (
    id SERIAL PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    field_name TEXT NOT NULL,  -- 'style_tag', 'fit', 'weight'
    field_value TEXT NOT NULL,  -- The curated value
    curator TEXT NOT NULL,  -- 'Reed', 'Gigi', 'Kiki'
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Prevent duplicate entries for same product/field/value/curator
    UNIQUE(product_id, field_name, field_value, curator)
);

-- Index for fast lookups by product
CREATE INDEX IF NOT EXISTS idx_curated_product_id ON curated_metadata(product_id);
CREATE INDEX IF NOT EXISTS idx_curated_curator ON curated_metadata(curator);

-- Enable RLS with full access policy
ALTER TABLE curated_metadata ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access to curated_metadata" ON curated_metadata
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- ============================================
-- REJECTED INFERRED TAGS TABLE
-- ============================================
-- Stores inferred tags that curators have marked as incorrect.
-- This data is preserved for ML model training to learn from mistakes.
-- The original inferred tags remain in the products table but are
-- displayed with strikethrough styling in the UI.

CREATE TABLE IF NOT EXISTS rejected_inferred_tags (
    id SERIAL PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    field_name TEXT NOT NULL,  -- 'style_tag', 'fit', 'weight', 'formality'
    field_value TEXT NOT NULL,  -- The rejected tag value
    original_reasoning TEXT,  -- The ML model's original reasoning for inference
    curator TEXT NOT NULL,  -- Who marked it as incorrect
    rejection_reason TEXT,  -- Optional: why the curator thinks it's wrong
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Prevent duplicate rejections for same product/field/value
    UNIQUE(product_id, field_name, field_value)
);

-- Indexes for ML training queries
CREATE INDEX IF NOT EXISTS idx_rejected_product_id ON rejected_inferred_tags(product_id);
CREATE INDEX IF NOT EXISTS idx_rejected_field_name ON rejected_inferred_tags(field_name);
CREATE INDEX IF NOT EXISTS idx_rejected_created_at ON rejected_inferred_tags(created_at);

-- Enable RLS with full access policy
ALTER TABLE rejected_inferred_tags ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access to rejected_inferred_tags" ON rejected_inferred_tags
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- ============================================
-- VIEW: ML Training Data for Rejected Tags
-- ============================================
-- Useful view for extracting training data to improve ML model

CREATE OR REPLACE VIEW ml_rejected_tags_training AS
SELECT
    r.product_id,
    r.field_name,
    r.field_value,
    r.original_reasoning,
    r.curator,
    r.rejection_reason,
    r.created_at,
    p.name as product_name,
    p.category,
    p.description
FROM rejected_inferred_tags r
JOIN products p ON r.product_id = p.product_id
ORDER BY r.created_at DESC;

-- ============================================
-- CURATION STATUS TABLE
-- ============================================
-- Tracks which products have been fully curated (reviewed and marked complete)

CREATE TABLE IF NOT EXISTS curation_status (
    id SERIAL PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    curator TEXT NOT NULL,  -- Who marked it as complete
    status TEXT NOT NULL DEFAULT 'complete',  -- 'complete' = fully curated
    notes TEXT,  -- Optional notes about the curation
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- One status per product
    UNIQUE(product_id)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_curation_status_product ON curation_status(product_id);
CREATE INDEX IF NOT EXISTS idx_curation_status_curator ON curation_status(curator);
CREATE INDEX IF NOT EXISTS idx_curation_status_created ON curation_status(created_at);

-- Enable RLS with full access policy
ALTER TABLE curation_status ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access to curation_status" ON curation_status
    FOR ALL USING (true) WITH CHECK (true);

-- ============================================
-- VIEW: Curation Progress Summary
-- ============================================
-- Summary view for dashboard statistics

CREATE OR REPLACE VIEW curation_summary AS
SELECT
    COUNT(*) as total_products,
    COUNT(cs.product_id) as curated_products,
    COUNT(*) - COUNT(cs.product_id) as pending_products,
    ROUND(COUNT(cs.product_id)::numeric / NULLIF(COUNT(*)::numeric, 0) * 100, 1) as percent_complete
FROM products p
LEFT JOIN curation_status cs ON p.product_id = cs.product_id;

-- ============================================
-- VIEW: Category Summary with Curation Status
-- ============================================
CREATE OR REPLACE VIEW category_curation_summary AS
SELECT
    p.category,
    COUNT(*) as total_products,
    COUNT(cs.product_id) as curated_products,
    COUNT(*) - COUNT(cs.product_id) as pending_products,
    ROUND(COUNT(cs.product_id)::numeric / NULLIF(COUNT(*)::numeric, 0) * 100, 1) as percent_complete
FROM products p
LEFT JOIN curation_status cs ON p.product_id = cs.product_id
GROUP BY p.category
ORDER BY total_products DESC;

-- ============================================
-- AI GENERATED TAGS TABLE
-- ============================================
-- Stores tags generated by AI vision models (e.g., Moondream via Ollama).
-- These are separate from:
--   - Inferred tags (from scraping/text analysis, stored in products.style_tags)
--   - Human curated tags (stored in curated_metadata)
-- AI-generated tags are displayed with a distinct teal/cyan color in the UI.

CREATE TABLE IF NOT EXISTS ai_generated_tags (
    id SERIAL PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    field_name TEXT NOT NULL DEFAULT 'style_tag',  -- 'style_tag', 'fit', 'weight', etc.
    field_value TEXT NOT NULL,  -- The AI-generated tag value
    model_name TEXT DEFAULT 'moondream',  -- Which AI model generated this tag
    confidence DECIMAL(3, 2),  -- Optional confidence score (0.00-1.00)
    reasoning TEXT,  -- Optional reasoning from the AI
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Prevent duplicate entries for same product/field/value
    UNIQUE(product_id, field_name, field_value)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_ai_tags_product_id ON ai_generated_tags(product_id);
CREATE INDEX IF NOT EXISTS idx_ai_tags_field_name ON ai_generated_tags(field_name);
CREATE INDEX IF NOT EXISTS idx_ai_tags_model ON ai_generated_tags(model_name);
CREATE INDEX IF NOT EXISTS idx_ai_tags_created_at ON ai_generated_tags(created_at);

-- Enable RLS with full access policy
ALTER TABLE ai_generated_tags ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access to ai_generated_tags" ON ai_generated_tags
    FOR ALL USING (true) WITH CHECK (true);

-- ============================================
-- VIEW: AI Generated Tags Summary
-- ============================================
-- Summary of AI-generated tags for analytics

CREATE OR REPLACE VIEW ai_tags_summary AS
SELECT
    COUNT(DISTINCT product_id) as products_with_ai_tags,
    COUNT(*) as total_ai_tags,
    model_name,
    COUNT(DISTINCT field_value) as unique_tags
FROM ai_generated_tags
GROUP BY model_name;

-- ============================================
-- CUSTOM VOCABULARY TABLE
-- ============================================
-- Stores user-defined vocabulary terms that extend the default AI tag vocabulary.
-- These custom tags are merged with the built-in vocabulary when the AI generates tags.
-- This allows users to add new style terms or create entirely new categories
-- without modifying the source code.

CREATE TABLE IF NOT EXISTS custom_vocabulary (
    id SERIAL PRIMARY KEY,
    category TEXT NOT NULL,  -- Category name (e.g., 'aesthetic', 'vibe', 'mood')
    tag TEXT NOT NULL,  -- The vocabulary term
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Prevent duplicate tags in the same category
    UNIQUE(category, tag)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_custom_vocab_category ON custom_vocabulary(category);
CREATE INDEX IF NOT EXISTS idx_custom_vocab_tag ON custom_vocabulary(tag);

-- Enable RLS with full access policy
ALTER TABLE custom_vocabulary ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access to custom_vocabulary" ON custom_vocabulary
    FOR ALL USING (true) WITH CHECK (true);

-- ============================================
-- VIEW: Full Vocabulary (Built-in + Custom)
-- ============================================
-- Note: The built-in vocabulary is defined in Python code (src/ai/style_tagger.py).
-- This view shows only custom additions. The application merges these at runtime.

CREATE OR REPLACE VIEW custom_vocabulary_summary AS
SELECT
    category,
    COUNT(*) as tag_count,
    array_agg(tag ORDER BY tag) as tags
FROM custom_vocabulary
GROUP BY category
ORDER BY category;
