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
    colors TEXT[] DEFAULT '{}',
    sizes TEXT[] DEFAULT '{}',
    materials TEXT[] DEFAULT '{}',
    fit TEXT,

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
