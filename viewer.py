#!/usr/bin/env python3
"""
Simple web viewer for browsing scraped product data.

Supports two data sources:
  - Local files (default): Reads from data/zara/mens directory
  - Supabase database: Reads from cloud database (use --supabase flag)

Usage:
    python viewer.py              # Load from local files
    python viewer.py --supabase   # Load from Supabase database

Then open http://localhost:5000 in your browser.
"""
import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template_string, send_from_directory

# Load environment variables
load_dotenv(Path(__file__).parent / ".env")

app = Flask(__name__)

# Data directory for local files
DATA_DIR = Path(__file__).parent / "data" / "zara" / "mens"

# Global flag for data source
USE_SUPABASE = False
supabase_client = None
BUCKET_NAME = "product-images"


def init_supabase():
    """Initialize Supabase client."""
    global supabase_client

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError(
            "Supabase credentials not found. "
            "Set SUPABASE_URL and SUPABASE_KEY in .env file."
        )

    from supabase import create_client

    supabase_client = create_client(supabase_url, supabase_key)
    return supabase_client


def get_products_from_supabase():
    """Fetch all products from Supabase database."""
    if not supabase_client:
        return []

    try:
        result = supabase_client.table("products").select("*").execute()
        products = result.data or []

        # Transform database format to match local file format for frontend compatibility
        transformed = []
        for p in products:
            # Build image URLs from storage paths
            image_paths = p.get("image_paths", [])
            supabase_url = os.getenv("SUPABASE_URL")

            transformed.append(
                {
                    "product_id": p.get("product_id"),
                    "name": p.get("name"),
                    "brand": "Zara",
                    "category": p.get("category"),
                    "subcategory": p.get("category"),  # Use category as subcategory
                    "url": p.get("url"),
                    "price": {
                        "current": (
                            float(p.get("price_current"))
                            if p.get("price_current")
                            else None
                        ),
                        "original": (
                            float(p.get("price_original"))
                            if p.get("price_original")
                            else None
                        ),
                        "currency": p.get("currency", "USD"),
                        "discount_percentage": None,
                    },
                    "description": p.get("description"),
                    "colors": p.get("colors", []),
                    "sizes": p.get("sizes", []),
                    "materials": p.get("materials", []),
                    "images": image_paths,  # Store full paths for Supabase
                    "image_urls": [
                        f"{supabase_url}/storage/v1/object/public/{BUCKET_NAME}/{path}"
                        for path in image_paths
                    ],
                    "fit": p.get("fit"),
                    "weight": None,
                    "style_tags": [],
                    "formality": None,
                    "scraped_at": p.get("scraped_at"),
                    "_source": "supabase",  # Mark source for frontend
                }
            )

        # Sort by product_id
        transformed.sort(key=lambda x: x.get("product_id", ""))
        return transformed

    except Exception as e:
        print(f"Error fetching from Supabase: {e}")
        return []


def get_products_from_local():
    """Scan data directory and load all product metadata from local files."""
    products = []

    if not DATA_DIR.exists():
        return products

    # Scan category directories
    for category_dir in DATA_DIR.iterdir():
        if category_dir.is_dir() and category_dir.name != "__pycache__":
            # Scan product directories within category
            for product_dir in category_dir.iterdir():
                if product_dir.is_dir():
                    metadata_file = product_dir / "metadata.json"
                    if metadata_file.exists():
                        try:
                            with open(metadata_file, "r") as f:
                                metadata = json.load(f)
                                # Add category folder name for image paths
                                metadata["category"] = category_dir.name
                                metadata["_source"] = "local"
                                products.append(metadata)
                        except json.JSONDecodeError:
                            print(f"Error reading {metadata_file}")

    # Sort by product_id for consistent ordering
    products.sort(key=lambda x: x.get("product_id", ""))
    return products


def get_all_products():
    """Get products from configured source (Supabase or local)."""
    if USE_SUPABASE:
        return get_products_from_supabase()
    else:
        return get_products_from_local()


# HTML Template with embedded CSS and JavaScript
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zara Scraper - Product Viewer</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f5f5f5;
            min-height: 100vh;
        }

        header {
            background: #000;
            color: #fff;
            padding: 20px;
            text-align: center;
        }

        header h1 {
            font-size: 24px;
            font-weight: 300;
            letter-spacing: 2px;
        }

        .data-source {
            font-size: 12px;
            margin-top: 5px;
            padding: 4px 12px;
            background: {{ '#4CAF50' if use_supabase else '#2196F3' }};
            display: inline-block;
            border-radius: 12px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        .navigation {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 20px;
            margin-bottom: 30px;
            background: #fff;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .nav-btn {
            background: #000;
            color: #fff;
            border: none;
            padding: 12px 30px;
            font-size: 14px;
            cursor: pointer;
            border-radius: 4px;
            transition: background 0.2s;
        }

        .nav-btn:hover {
            background: #333;
        }

        .nav-btn:disabled {
            background: #ccc;
            cursor: not-allowed;
        }

        .counter {
            font-size: 16px;
            color: #666;
        }

        .product-card {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 40px;
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
        }

        .image-section {
            padding: 30px;
            background: #fafafa;
        }

        .main-image {
            width: 100%;
            max-height: 500px;
            object-fit: contain;
            border-radius: 4px;
        }

        .thumbnail-row {
            display: flex;
            gap: 10px;
            margin-top: 15px;
            flex-wrap: wrap;
        }

        .thumbnail {
            width: 80px;
            height: 100px;
            object-fit: cover;
            border: 2px solid transparent;
            border-radius: 4px;
            cursor: pointer;
            transition: border-color 0.2s;
        }

        .thumbnail:hover,
        .thumbnail.active {
            border-color: #000;
        }

        .metadata-section {
            padding: 30px;
        }

        .category-badge {
            display: inline-block;
            background: #e0e0e0;
            color: #666;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }

        .product-name {
            font-size: 28px;
            font-weight: 400;
            margin-bottom: 10px;
            color: #000;
        }

        .product-id {
            color: #999;
            font-size: 12px;
            margin-bottom: 20px;
        }

        .price-section {
            margin-bottom: 25px;
        }

        .current-price {
            font-size: 24px;
            font-weight: 600;
            color: #000;
        }

        .original-price {
            font-size: 18px;
            color: #999;
            text-decoration: line-through;
            margin-left: 10px;
        }

        .discount-badge {
            display: inline-block;
            background: #c00;
            color: #fff;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            margin-left: 10px;
        }

        .section-title {
            font-size: 14px;
            font-weight: 600;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
            margin-top: 20px;
        }

        .description {
            color: #444;
            line-height: 1.6;
        }

        .tag-list {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }

        .tag {
            background: #f0f0f0;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 13px;
            color: #444;
        }

        .url-link {
            color: #0066cc;
            text-decoration: none;
            word-break: break-all;
            font-size: 13px;
        }

        .url-link:hover {
            text-decoration: underline;
        }

        .scraped-time {
            color: #999;
            font-size: 12px;
            margin-top: 30px;
        }

        .no-data {
            text-align: center;
            padding: 100px 20px;
            color: #666;
        }

        .no-data h2 {
            margin-bottom: 10px;
        }

        .validation-section {
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
        }

        .validation-btn {
            padding: 10px 20px;
            margin-right: 10px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }

        .btn-valid {
            background: #4CAF50;
            color: white;
        }

        .btn-invalid {
            background: #f44336;
            color: white;
        }

        .validation-status {
            margin-top: 10px;
            font-size: 14px;
        }

        @media (max-width: 900px) {
            .product-card {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <header>
        <h1>ZARA PRODUCT VIEWER</h1>
        <span class="data-source">{{ '🗄️ Supabase Database' if use_supabase else '📁 Local Files' }}</span>
    </header>

    <div class="container">
        <div class="navigation">
            <button class="nav-btn" id="prevBtn" onclick="navigate(-1)">← Previous</button>
            <span class="counter" id="counter">Loading...</span>
            <button class="nav-btn" id="nextBtn" onclick="navigate(1)">Next →</button>
        </div>

        <div id="productCard" class="product-card">
            <div class="no-data">
                <h2>Loading products...</h2>
            </div>
        </div>
    </div>

    <script>
        let products = [];
        let currentIndex = 0;
        let currentImageIndex = 0;
        const useSupabase = {{ 'true' if use_supabase else 'false' }};

        async function loadProducts() {
            try {
                const response = await fetch('/api/products');
                products = await response.json();

                if (products.length > 0) {
                    displayProduct(0);
                } else {
                    document.getElementById('productCard').innerHTML = `
                        <div class="no-data">
                            <h2>No products found</h2>
                            <p>${useSupabase ? 'No products in Supabase database. Run: <code>python main.py --supabase</code>' : 'Run the scraper first: <code>python main.py</code>'}</p>
                        </div>
                    `;
                    document.getElementById('counter').textContent = 'No products';
                }
            } catch (error) {
                console.error('Error loading products:', error);
                document.getElementById('productCard').innerHTML = `
                    <div class="no-data">
                        <h2>Error loading products</h2>
                        <p>${error.message}</p>
                    </div>
                `;
            }
        }

        function getImageUrl(product, index) {
            // For Supabase, use the full image URLs
            if (product._source === 'supabase' && product.image_urls && product.image_urls[index]) {
                return product.image_urls[index];
            }
            // For local files, construct the path
            const images = product.images || [];
            if (images[index]) {
                return `/images/${product.category}/${product.product_id}/${images[index]}`;
            }
            return 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="400" height="500" fill="%23ccc"><rect width="100%" height="100%"/><text x="50%" y="50%" text-anchor="middle" fill="%23999">No Image</text></svg>';
        }

        function displayProduct(index) {
            if (index < 0 || index >= products.length) return;

            currentIndex = index;
            currentImageIndex = 0;
            const product = products[index];

            // Update counter
            document.getElementById('counter').textContent = `Product ${index + 1} of ${products.length}`;

            // Update navigation buttons
            document.getElementById('prevBtn').disabled = index === 0;
            document.getElementById('nextBtn').disabled = index === products.length - 1;

            // Build image gallery
            const images = product.images || [];
            const imageCount = product._source === 'supabase' ? (product.image_urls || []).length : images.length;
            const mainImageSrc = getImageUrl(product, 0);

            let thumbnails = '';
            for (let i = 0; i < imageCount; i++) {
                const imgSrc = getImageUrl(product, i);
                thumbnails += `
                    <img src="${imgSrc}"
                         class="thumbnail ${i === 0 ? 'active' : ''}"
                         onclick="changeImage(${i})"
                         alt="Thumbnail ${i + 1}">
                `;
            }

            // Build price display
            let priceHtml = '';
            if (product.price) {
                const current = product.price.current;
                const original = product.price.original;
                const discount = product.price.discount_percentage;

                priceHtml = `<span class="current-price">$${current || 'N/A'}</span>`;
                if (original && original > current) {
                    priceHtml += `<span class="original-price">$${original}</span>`;
                }
                if (discount) {
                    priceHtml += `<span class="discount-badge">-${discount}%</span>`;
                }
            }

            // Build tags
            const colorTags = (product.colors || []).map(c => `<span class="tag">${c}</span>`).join('');
            const sizeTags = (product.sizes || []).filter(s => s && s.trim() && s !== 'Add').map(s => `<span class="tag">${s}</span>`).join('');
            const materialTags = (product.materials || []).map(m => `<span class="tag">${m}</span>`).join('');
            // Build style tags with reasoning (hover to see reasoning)
            const styleTags = (product.style_tags || []).map(s => {
                // Handle both old format (string) and new format (object with tag/reasoning)
                if (typeof s === 'string') {
                    return `<span class="tag" style="background:#e3f2fd;color:#1565c0;">${s}</span>`;
                }
                return `<span class="tag" style="background:#e3f2fd;color:#1565c0;cursor:help;" title="${s.reasoning || ''}">${s.tag}</span>`;
            }).join('');

            // Build fit badge
            const fitBadge = product.fit ? `<span class="tag" style="background:#fff3e0;color:#e65100;">${product.fit}</span>` : '';

            // Build weight badge with reasoning (handle both old string format and new object format)
            let weightBadge = '';
            let weightReasoning = '';
            if (product.weight) {
                if (typeof product.weight === 'string') {
                    // Old format: just a string
                    weightBadge = `<span class="tag" style="background:#f3e5f5;color:#7b1fa2;">${product.weight}</span>`;
                } else {
                    // New format: object with value and reasoning
                    weightBadge = `<span class="tag" style="background:#f3e5f5;color:#7b1fa2;">${product.weight.value}</span>`;
                    weightReasoning = (product.weight.reasoning || []).join(' • ');
                }
            }

            // Build formality display
            let formalityHtml = '';
            if (product.formality) {
                const score = product.formality.score;
                const label = product.formality.label;
                const reasoning = product.formality.reasoning || [];

                // Color based on formality level
                const formalityColors = {
                    1: '#ff6b6b',  // Very Casual - red
                    2: '#ffa94d',  // Casual - orange
                    3: '#ffd43b',  // Smart Casual - yellow
                    4: '#69db7c',  // Business Casual - green
                    5: '#339af0',  // Formal - blue
                };
                const barColor = formalityColors[score] || '#ccc';

                formalityHtml = `
                    <div style="margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                        <h3 class="section-title" style="margin-top: 0;">Formality</h3>
                        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 10px;">
                            <div style="font-size: 32px; font-weight: bold; color: ${barColor};">${score}/5</div>
                            <div>
                                <div style="font-size: 18px; font-weight: 500;">${label}</div>
                                <div style="display: flex; gap: 2px; margin-top: 5px;">
                                    ${[1,2,3,4,5].map(i => `<div style="width: 30px; height: 8px; border-radius: 4px; background: ${i <= score ? barColor : '#ddd'};"></div>`).join('')}
                                </div>
                            </div>
                        </div>
                        ${reasoning.length > 0 ? `
                            <div style="font-size: 12px; color: #666; margin-top: 10px;">
                                <strong>Reasoning:</strong> ${reasoning.join(' • ')}
                            </div>
                        ` : ''}
                    </div>
                `;
            }

            // Render card
            document.getElementById('productCard').innerHTML = `
                <div class="image-section">
                    <img id="mainImage" src="${mainImageSrc}" alt="${product.name}" class="main-image">
                    <div class="thumbnail-row">
                        ${thumbnails}
                    </div>
                </div>

                <div class="metadata-section">
                    <span class="category-badge">${product.subcategory || product.category}</span>
                    <h2 class="product-name">${product.name}</h2>
                    <p class="product-id">ID: ${product.product_id}</p>

                    <div class="price-section">
                        ${priceHtml}
                    </div>

                    ${formalityHtml}

                    ${fitBadge ? `
                        <h3 class="section-title">Fit</h3>
                        <div class="tag-list">${fitBadge}</div>
                    ` : ''}

                    ${weightBadge ? `
                        <h3 class="section-title">Weight</h3>
                        <div class="tag-list">${weightBadge}</div>
                        ${weightReasoning ? `<div style="font-size: 12px; color: #666; margin-top: 5px;"><em>${weightReasoning}</em></div>` : ''}
                    ` : ''}

                    ${styleTags ? `
                        <h3 class="section-title">Style Tags <span style="font-size:10px;color:#999;font-weight:normal;">(hover for reasoning)</span></h3>
                        <div class="tag-list">${styleTags}</div>
                    ` : ''}

                    ${product.description ? `
                        <h3 class="section-title">Description</h3>
                        <p class="description">${product.description}</p>
                    ` : ''}

                    ${colorTags ? `
                        <h3 class="section-title">Colors</h3>
                        <div class="tag-list">${colorTags}</div>
                    ` : ''}

                    ${sizeTags ? `
                        <h3 class="section-title">Sizes</h3>
                        <div class="tag-list">${sizeTags}</div>
                    ` : ''}

                    ${materialTags ? `
                        <h3 class="section-title">Materials</h3>
                        <div class="tag-list">${materialTags}</div>
                    ` : ''}

                    <h3 class="section-title">Source URL</h3>
                    <a href="${product.url}" target="_blank" class="url-link">${product.url}</a>

                    <div class="validation-section">
                        <h3 class="section-title">Manual Validation</h3>
                        <button class="validation-btn btn-valid" onclick="markValid(${index})">✓ Valid</button>
                        <button class="validation-btn btn-invalid" onclick="markInvalid(${index})">✗ Invalid</button>
                        <p class="validation-status" id="validationStatus"></p>
                    </div>

                    <p class="scraped-time">Scraped: ${new Date(product.scraped_at).toLocaleString()}</p>
                </div>
            `;
        }

        function changeImage(index) {
            currentImageIndex = index;
            const product = products[currentIndex];
            document.getElementById('mainImage').src = getImageUrl(product, index);

            // Update active thumbnail
            document.querySelectorAll('.thumbnail').forEach((thumb, i) => {
                thumb.classList.toggle('active', i === index);
            });
        }

        function navigate(direction) {
            const newIndex = currentIndex + direction;
            if (newIndex >= 0 && newIndex < products.length) {
                displayProduct(newIndex);
            }
        }

        function markValid(index) {
            document.getElementById('validationStatus').textContent = '✓ Marked as VALID';
            document.getElementById('validationStatus').style.color = '#4CAF50';
            console.log(`Product ${products[index].product_id} marked as valid`);
        }

        function markInvalid(index) {
            document.getElementById('validationStatus').textContent = '✗ Marked as INVALID';
            document.getElementById('validationStatus').style.color = '#f44336';
            console.log(`Product ${products[index].product_id} marked as invalid`);
        }

        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowLeft') navigate(-1);
            if (e.key === 'ArrowRight') navigate(1);
        });

        // Load products on page load
        loadProducts();
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    """Serve the main viewer page."""
    return render_template_string(HTML_TEMPLATE, use_supabase=USE_SUPABASE)


@app.route("/api/products")
def api_products():
    """API endpoint to get all products."""
    products = get_all_products()
    return jsonify(products)


@app.route("/images/<category>/<product_id>/<filename>")
def serve_image(category, product_id, filename):
    """Serve product images from local files."""
    image_dir = DATA_DIR / category / product_id
    return send_from_directory(image_dir, filename)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Zara Product Viewer - Browse scraped products"
    )
    parser.add_argument(
        "--supabase",
        action="store_true",
        help="Load products from Supabase database instead of local files",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to run the server on (default: 5000)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    USE_SUPABASE = args.supabase

    print("\n" + "=" * 50)
    print("  ZARA PRODUCT VIEWER")
    print("=" * 50)

    if USE_SUPABASE:
        print("\n📦 Data source: Supabase Database")
        try:
            init_supabase()
            print("✓ Connected to Supabase")
        except Exception as e:
            print(f"✗ Failed to connect to Supabase: {e}")
            print("\nFalling back to local files...")
            USE_SUPABASE = False

    if not USE_SUPABASE:
        print(f"\n📁 Data source: Local files")
        print(f"   Directory: {DATA_DIR}")

    products = get_all_products()
    print(f"\n📊 Products found: {len(products)}")

    if products:
        print("\nProducts loaded:")
        for p in products[:10]:  # Show first 10
            print(f"  • {p.get('name', 'Unknown')} ({p.get('product_id', 'N/A')})")
        if len(products) > 10:
            print(f"  ... and {len(products) - 10} more")

    print("\n" + "-" * 50)
    print(f"  Open http://localhost:{args.port} in your browser")
    print("-" * 50 + "\n")

    app.run(debug=True, port=args.port)
