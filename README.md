# Zara ETL Pipeline

A web scraping ETL (Extract, Transform, Load) pipeline for scraping men's clothing products from Zara.

## Features

- **Extract**: Scrapes product data using Playwright with stealth settings to handle JavaScript rendering
- **Transform**: Cleans and validates product data using Pydantic models
- **Load**: Saves products to organized directory structure with images and metadata

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

- [ ] Add database storage (SQLite/PostgreSQL)
- [ ] Add women's clothing support
- [ ] Add scheduling/cron support
- [ ] Add proxy rotation for scale
- [ ] Add more clothing retailers
