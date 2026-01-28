# 🛍️ ReFitD - Fashion Product Data Pipeline & Viewer

<div align="center">

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-Web%20App-green.svg)
![Supabase](https://img.shields.io/badge/Supabase-Database-orange.svg)
![AI](https://img.shields.io/badge/AI-Ollama%20%2B%20Moondream-purple.svg)

**A complete ETL pipeline for scraping, storing, viewing, and curating men's fashion products with AI-powered style tagging.**

[Features](#-features) • [Quick Start](#-quick-start) • [Product Viewer](#-product-viewer) • [AI Features](#-ai-features) • [Documentation](#-documentation)

</div>

---

## ✨ Features

### 🔄 ETL Pipeline
- **Extract** - Scrapes product data from Zara using Playwright with stealth settings
- **Transform** - Cleans and validates data using Pydantic models
- **Load** - Saves to local files or Supabase cloud database

### 🖼️ Product Viewer
- **Beautiful Web Interface** - Browse all scraped products with images
- **Organized Category Sidebar** - Hierarchical categories (Base Layer, Mid Layer, Bottoms, Outerwear, Shoes) with subcategories and counts
- **Image Gallery** - View all product images with thumbnails
- **Product Details** - Name, price, description, materials, composition, sizes, colors

### 🏷️ ReFitd Canonical Tagging System
The ReFitd tagging system uses a structured AI → Policy → Canonical flow:

| Component | Purpose | Output |
|-----------|---------|--------|
| 🔵 **AI Sensor** | GPT-4o vision analyzes product images | Tags with confidence scores |
| ⚙️ **Tag Policy** | Applies thresholds and business rules | Filtered, validated tags |
| 🏷️ **Canonical Tags** | Final machine-readable tags | Clean tags for outfit generation |

**Canonical Tag Categories:**
- **Style Identity** (1-2): minimal, classic, preppy, workwear, streetwear, rugged, etc.
- **Silhouette**: straight, tapered, wide (bottoms) / boxy, structured, relaxed, tailored (tops)
- **Formality**: athletic → casual → smart-casual → business-casual → formal
- **Context** (0-2): everyday, work-appropriate, travel, evening, weekend
- **Pattern** (0-1): solid, stripe, check, textured
- **Construction Details** (0-2): pleated, flat-front, cargo, structured-shoulder, etc.
- **Top Layer Role** (tops only): base (t-shirts, shirts, polos) or mid (sweaters, hoodies)
- **Shoe-Specific**: type, profile, closure

### 🤖 AI-Powered Features
- **GPT-4o Vision Tagging** - Analyzes product images to generate structured canonical tags with confidence scores
- **AI Formality Rating** - AI-generated formality level (1-5 scale) for comparison with rule-based approach
- **Semantic Search** - Find products using natural language queries
- **AI Chat Assistant** - Get styling advice and product recommendations

### 👥 Multi-Curator Support
- Multiple curators can add and manage tags
- Each curator has a unique color
- Track who curated what

### 📊 Dashboard
- View curation statistics
- Track progress across products
- See category breakdowns

---

## 🚀 Quick Start

### Prerequisites

- Python 3.9 or higher
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/trevsauer/refitd.git
cd refitd

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### Run the Product Viewer

```bash
# Start the viewer (connects to cloud database automatically)
python viewer.py --supabase
```

Open your browser to **http://localhost:5001**

> 💡 **New to coding?** See our [Complete Beginner's Setup Guide](docs/SETUP_GUIDE_FOR_BEGINNERS.md)

---

## 🖥️ Product Viewer

The product viewer is a web application for browsing and curating products.

### Starting the Viewer

```bash
# Start the viewer (with AI tagging features)
python viewer.py --supabase
```

### Viewer Features

#### 📂 Category Sidebar
- Shows all product categories
- Displays item count per category
- Click to filter products
- "All Products" option to see everything

#### 🏷️ Tag Management
- View inferred tags (blue) from scraping
- Add curated tags (purple) manually
- Generate AI tags (teal) with one click
- Delete or reject incorrect tags

#### 🔄 Curation Mode
1. Click **"🖊️ Curate"** button
2. Select your curator name
3. Click any tag to add it to your curated collection
4. Tags you add appear in purple with your name

#### ⬅️ ➡️ Navigation
- **Previous/Next** buttons to browse products
- Counter shows current position: "Product 5 of 127"
- Filter by category to narrow browsing

---

## 🤖 AI Features

The viewer includes powerful AI capabilities powered by GPT-4o and local models.

### Requirements for AI Features

```bash
# Option 1: OpenAI GPT-4o (for ReFitd Canonical Tagging)
# Set your OpenAI API key in .env file
OPENAI_API_KEY=your-key-here

# Option 2: Ollama (for legacy style tagging)
# Mac:
brew install ollama

# Start Ollama server
ollama serve

# Install the vision model (in a new terminal)
ollama pull moondream
```

### ReFitd Canonical Tagging (GPT-4o)

The primary tagging system uses GPT-4o vision for structured, machine-readable tags:

1. Open a product in the viewer
2. Click the **"🏷️ Generate ReFitd Tags"** button
3. GPT-4o analyzes the product image and generates canonical tags
4. Tags are processed through the policy layer (confidence thresholds, business rules)
5. Final canonical tags appear in the ReFitd Canonical Tags section

**What it generates:**
- Style Identity (1-2): minimal, classic, preppy, workwear, streetwear, etc.
- Silhouette: boxy, structured, relaxed, tailored, straight, tapered, wide
- **AI Formality**: athletic (1) → casual (2) → smart-casual (3) → business-casual (4) → formal (5)
- Context: everyday, work-appropriate, travel, evening, weekend
- Pattern: solid, stripe, check, textured
- Construction details: pleated, flat-front, cargo, structured-shoulder, etc.
- Top layer role (for tops): base or mid layer
- Shoe-specific fields: type, profile, closure

**AI vs Scraped Formality:**
The system now shows both AI-generated formality and rule-based formality side by side so you can compare approaches.

### Legacy AI Style Tag Generation (Moondream)

For legacy style tagging using local models:

1. Click the **"🤖 AI Generate"** button (teal)
2. Moondream analyzes the product image
3. New tags appear in teal color
4. Duplicates are automatically filtered out

> 📖 See [AI Tag Generation Documentation](docs/AI_TAG_GENERATION.md) for technical details

### Semantic Search

1. Go to the **"🤖 AI Assistant"** tab
2. Type a natural language query like:
   - "minimal white t-shirt"
   - "formal dark blazer"
   - "casual summer outfit"
3. AI finds matching products based on meaning, not just keywords

### AI Chat Assistant

- Ask for styling advice
- Get outfit recommendations
- Discuss product features

---

## 📦 Scraping Products

### Basic Usage

```bash
# Scrape 2 products per category (default)
python main.py --supabase

# Scrape 10 products per category
python main.py --supabase -n 10

# Scrape ALL products from specific categories
python main.py --supabase --all --categories tshirts jackets

# Scrape ALL products from ALL categories
python main.py --supabase --all
```

### Scrape by Subcategory

To scrape one product from every category (useful for testing):

```bash
# Quick way: Use --sample-all to get 1 product from each Zara category
python main.py --sample-all

# This is equivalent to:
# python main.py -n 1

# For specific categories only:
python main.py -n 1 -c tshirts shirts trousers shorts jackets blazers shoes
```

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `-n, --products` | Products per category | 2 |
| `-a, --all` | Scrape ALL products (no limit) | false |
| `--supabase` | Store in cloud database | false |
| `--headless` | Run browser invisibly | true |
| `--categories` | Specific categories to scrape | all |
| `--no-images` | Skip image downloads | false |
| `-f, --force` | Force re-scrape | false |

### Available Categories

```
tshirts, shirts, trousers, jeans, shorts, jackets,
blazers, suits, shoes, new-in
```

### Category → Subcategory Mapping

| Zara Category | ReFitd Subcategories |
|---------------|----------------------|
| `tshirts` | T-Shirts, Long Sleeve, Tanks & Henleys |
| `shirts` | Shirts, Polos |
| `trousers` | Pants |
| `shorts` | Shorts |
| `jackets` | Jackets, Coats |
| `blazers` | Blazers, Vests |
| `shoes` | Shoes |

---

## 🗄️ Database

### Supabase (Cloud Database)

The project uses Supabase for cloud storage:
- **PostgreSQL** - Product metadata
- **Storage** - Product images

> 🔑 Credentials are hardcoded for easy setup - just clone and run!

### Database Tables

| Table | Purpose |
|-------|---------|
| `products` | Product metadata (name, price, description, etc.) |
| `curated_metadata` | Human-curated tags |
| `ai_generated_tags` | AI-generated style tags |
| `rejected_tags` | Tags marked as incorrect |
| `curation_status` | Track which products are curated |

---

## 📁 Project Structure

```
refitd/
├── 📄 main.py                 # Scraper entry point
├── 📄 viewer.py               # Product viewer with AI features
├── 📄 requirements.txt        # Python dependencies
├── 📄 supabase_schema.sql     # Database schema
│
├── 📁 src/
│   ├── 📁 extractors/         # Web scraping logic
│   ├── 📁 transformers/       # Data cleaning
│   ├── 📁 loaders/            # Database & file storage
│   ├── 📁 tracking/           # Scraping tracker
│   └── 📁 ai/                 # AI features
│       ├── ollama_client.py   # Ollama API client
│       ├── style_tagger.py    # AI tag generation
│       ├── embeddings.py      # Semantic search
│       └── chat.py            # AI chat assistant
│
├── 📁 config/
│   └── settings.py            # Configuration
│
├── 📁 docs/
│   ├── SETUP_GUIDE_FOR_BEGINNERS.md
│   ├── AI_TAG_GENERATION.md
│   └── SIZE_EXTRACTION.md
│
└── 📁 data/                   # Local data storage
```

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [Setup Guide for Beginners](docs/SETUP_GUIDE_FOR_BEGINNERS.md) | Step-by-step setup for complete beginners |
| [AI Tag Generation](docs/AI_TAG_GENERATION.md) | How AI style tagging works |
| [Supabase Setup](SUPABASE_SETUP.md) | Database configuration guide |

---

## 🔧 Troubleshooting

### Viewer won't start

```bash
# Make sure dependencies are installed
pip install -r requirements.txt

# Try a different port if 5001 is busy
python viewer.py --supabase --port 5002
```

### AI features not working

```bash
# Make sure Ollama is running
ollama serve

# Install the vision model
ollama pull moondream

# Check if Ollama is accessible
curl http://localhost:11434/api/tags
```

### "No products found"

```bash
# Run the scraper first
python main.py --supabase -n 5
```

### Images not loading

- Check your internet connection
- Verify Supabase storage bucket is public
- Try refreshing the page

---

## 🛣️ Roadmap

- [x] ETL pipeline for Zara products
- [x] Cloud database storage (Supabase)
- [x] Product viewer web app
- [x] Multi-curator tagging system
- [x] AI-powered style tagging
- [x] Semantic product search
- [x] Category filtering sidebar
- [x] Duplicate tag prevention
- [ ] Women's clothing support
- [ ] Additional retailers
- [ ] Outfit recommendation engine
- [ ] Mobile-responsive design

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## 📄 License

This project is for educational purposes.

---

<div align="center">

**Made with ❤️ for fashion data enthusiasts**

</div>
