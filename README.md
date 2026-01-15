# Zara ETL Pipeline

A web scraping ETL (Extract, Transform, Load) pipeline for scraping men's clothing products from Zara.

## Features

- **Extract**: Scrapes product data using Playwright with stealth settings to handle JavaScript rendering
- **Transform**: Cleans and validates product data using Pydantic models
- **Load**: Saves products to organized directory structure with images and metadata
- **Database Storage**: Optional Supabase integration for cloud storage of products and images
- **Tracking**: SQLite-based tracking to avoid re-scraping the same products

## Directory Structure

```
zara_scraper/
├── config/
│   └── settings.py          # Configuration settings
├── src/
│   ├── extractors/
│   │   └── zara_extractor.py # Playwright-based extraction
│   ├── transformers/
│   │   └── product_transformer.py # Data cleaning & validation
│   ├── loaders/
│   │   └── file_loader.py    # Save to disk
│   └── pipeline.py           # Main ETL orchestration
├── data/                     # Output directory (created automatically)
│   └── zara/
│       └── mens/
│           ├── t-shirts/
│           │   └── {product_id}/
│           │       ├── metadata.json
│           │       └── image_01.jpg
│           ├── pants/
│           └── jackets/
├── logs/                     # Log files
├── requirements.txt
├── main.py                   # Entry point
└── README.md
```

## Installation

1. Create a virtual environment:
```bash
cd zara_scraper
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install chromium
```

## Usage

### Basic Usage (Default: 6 products)
```bash
python main.py
```

### With Options
```bash
# Scrape 5 products per category (15 total)
python main.py --products 5

# Run with visible browser (for debugging)
python main.py --headless false

# Only scrape specific categories
python main.py --categories tshirts jackets

# Skip downloading images (faster, metadata only)
python main.py --no-images

# Custom output directory
python main.py --output /path/to/output
```

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `-n, --products` | Products per category | 2 |
| `--headless` | Run browser in headless mode | true |
| `--categories` | Categories to scrape | tshirts pants jackets |
| `--output` | Output directory | ./data |
| `--no-images` | Skip image downloads | false |

## Output

### Product Metadata (metadata.json)
```json
{
  "product_id": "12345678",
  "name": "Relaxed Fit Jogger",
  "brand": "Zara",
  "category": "Bottoms",
  "subcategory": "Pants",
  "url": "https://www.zara.com/us/en/...",
  "price": {
    "current": 49.90,
    "original": 69.90,
    "currency": "USD",
    "discount_percentage": 28.6
  },
  "description": "Relaxed fit joggers with elastic...",
  "colors": ["Black", "Navy"],
  "sizes": ["S", "M", "L", "XL"],
  "materials": ["98% Cotton", "2% Elastane"],
  "images": ["image_01.jpg", "image_02.jpg"],
  "scraped_at": "2026-01-14T18:25:00Z"
}
```

### Summary File (summary.json)
Generated at `data/zara/mens/summary.json` with aggregated statistics.

## Configuration

Edit `config/settings.py` to customize:
- Rate limiting delays
- Browser settings
- Category URLs
- Image download limits
- User agent rotation

## Respectful Scraping

This pipeline is designed to be respectful:
- Follows Zara's robots.txt (avoids disallowed paths)
- Uses rate limiting (3-5 second delays between requests)
- Rotates user agents
- Limits concurrent requests

## Troubleshooting

### "No products extracted"
- Zara may have changed their HTML structure
- Try running with `--headless false` to see what's happening
- Check if the category URLs in settings.py are still valid

### "Browser timeout"
- Increase `timeout_ms` in settings.py
- Check your internet connection
- Zara's servers may be slow

### Images not downloading
- Check if Zara is blocking image requests
- Try with `--headless false` to debug
- Verify image URLs are being extracted correctly

## Future Enhancements

- [x] Add database storage (Supabase PostgreSQL)
- [x] Add product tracking to avoid re-scraping
- [ ] Add women's clothing support
- [ ] Add scheduling/cron support
- [ ] Add proxy rotation for scale
- [ ] Add more clothing retailers

---

## Database Storage (Supabase)

The pipeline supports optional cloud storage using [Supabase](https://supabase.com) (free tier available):

- **Product metadata** → PostgreSQL database
- **Product images** → Supabase Storage (S3-compatible)

### Setting Up Supabase

1. **Create a free Supabase account** at https://supabase.com

2. **Create a new project** and note your:
   - Project URL: `https://your-project-id.supabase.co`
   - API Key: Found in Project Settings → API → `anon public` key (starts with `eyJ...`)

3. **Create the database table** - Go to SQL Editor and run:

```sql
CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    url TEXT NOT NULL,
    price_current DECIMAL(10, 2),
    price_original DECIMAL(10, 2),
    currency TEXT DEFAULT 'USD',
    description TEXT,
    colors TEXT[] DEFAULT '{}',
    sizes TEXT[] DEFAULT '{}',
    materials TEXT[] DEFAULT '{}',
    fit TEXT,
    image_paths TEXT[] DEFAULT '{}',
    image_count INTEGER DEFAULT 0,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS with full access policy
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access" ON products FOR ALL USING (true) WITH CHECK (true);
```

4. **Create a storage bucket**:
   - Go to Storage → New bucket
   - Name: `product-images`
   - Check "Public bucket"
   - Add a policy: New policy → Allow all operations → Policy definition: `true`

5. **Configure environment variables**:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Using Supabase Storage

```bash
# Scrape and store in Supabase
python main.py --supabase

# Force re-scrape all products
python main.py --supabase --force

# Scrape specific categories
python main.py --supabase --categories tshirts pants -n 5
```

### Viewing Your Data Online

#### View Product Data (Database)
1. Go to your Supabase dashboard: https://supabase.com/dashboard
2. Select your project
3. Click **Table Editor** in the left sidebar
4. Click on the **products** table
5. You'll see all scraped products with their metadata

You can also run SQL queries directly:
- Go to **SQL Editor**
- Run queries like:
```sql
-- View all products
SELECT * FROM products;

-- View products by category
SELECT name, price_current, category FROM products WHERE category = 'Tops';

-- Get price statistics
SELECT
    category,
    COUNT(*) as count,
    AVG(price_current) as avg_price,
    MIN(price_current) as min_price,
    MAX(price_current) as max_price
FROM products
GROUP BY category;
```

#### View Product Images (Storage)
1. Go to your Supabase dashboard
2. Click **Storage** in the left sidebar
3. Click on the **product-images** bucket
4. Browse folders by category → product_id → images

Each image has a public URL you can access directly:
```
https://your-project-id.supabase.co/storage/v1/object/public/product-images/Tops/12345678/image_0.jpg
```

### Product Tracking

The pipeline uses a local SQLite database (`data/tracking.db`) to track which products have been scraped, avoiding duplicate work on subsequent runs.

```bash
# View tracking statistics
python main.py --stats

# Clear tracking database (to re-scrape everything)
python main.py --clear-tracking

# Force re-scrape ignoring tracking
python main.py --force
```

### CLI Options for Database

| Option | Description |
|--------|-------------|
| `--supabase` | Store data in Supabase |
| `--force, -f` | Force re-scrape, ignore tracking |
| `--clear-tracking` | Clear tracking database before running |
| `--stats` | Show tracking statistics and exit |
