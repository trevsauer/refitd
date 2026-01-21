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
import subprocess
import threading
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template_string, request, send_from_directory

# Load environment variables (optional - credentials are hardcoded as fallback)
load_dotenv(Path(__file__).parent / ".env")

app = Flask(__name__)

# Data directory for local files
DATA_DIR = Path(__file__).parent / "data" / "zara" / "mens"

# ============================================
# SUPABASE CREDENTIALS (Hardcoded for easy sharing)
# ============================================
# These credentials allow anyone who clones the repo to connect immediately
DEFAULT_SUPABASE_URL = "https://uochfddhtkzrvcmfwksm.supabase.co"
DEFAULT_SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVvY2hmZGRodGt6cnZjbWZ3a3NtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg1MDA1NDEsImV4cCI6MjA4NDA3NjU0MX0.mzBTf1GV8_Vk-nIMvf26PxI_MAqZfStzRTEZBEvHyLU"

# Global flag for data source
USE_SUPABASE = False
supabase_client = None
BUCKET_NAME = "product-images"

# ============================================
# SCRAPER STATUS TRACKING
# ============================================
scraper_status = {
    "running": False,
    "progress": 0,
    "total": 0,
    "current_category": "",
    "current_product": "",
    "products_scraped": 0,
    "products_skipped": 0,
    "error": None,
    "completed": False,
    "start_time": None,
    "end_time": None,
    "logs": [],  # Store log lines for display
    "refresh_handled": False,  # Prevent multiple refreshes
}


def init_supabase():
    """Initialize Supabase client."""
    global supabase_client

    # Use environment variables if available, otherwise use hardcoded defaults
    supabase_url = os.getenv("SUPABASE_URL") or DEFAULT_SUPABASE_URL
    supabase_key = os.getenv("SUPABASE_KEY") or DEFAULT_SUPABASE_KEY

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
            supabase_url = os.getenv("SUPABASE_URL") or DEFAULT_SUPABASE_URL

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
                    "sizes_availability": p.get(
                        "sizes_availability", []
                    ),  # New field with availability
                    "materials": p.get("materials", []),
                    "images": image_paths,  # Store full paths for Supabase
                    "image_urls": [
                        f"{supabase_url}/storage/v1/object/public/{BUCKET_NAME}/{path}"
                        for path in image_paths
                    ],
                    "fit": p.get("fit"),
                    "weight": p.get("weight"),  # Now loaded from DB as JSONB
                    "style_tags": p.get(
                        "style_tags", []
                    ),  # Now loaded from DB as JSONB
                    "formality": p.get("formality"),  # Now loaded from DB as JSONB
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
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
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

        /* Curate Mode Styles */
        .curate-btn {
            background: #ff9800;
            color: #fff;
            border: none;
            padding: 8px 20px;
            font-size: 14px;
            cursor: pointer;
            border-radius: 4px;
            margin-left: 15px;
            transition: background 0.2s;
        }

        .curate-btn:hover {
            background: #f57c00;
        }

        .curate-btn.active {
            background: #4CAF50;
        }

        .curator-selector {
            display: none;
            margin-left: 10px;
        }

        .curator-selector.visible {
            display: inline-block;
        }

        .curator-selector select {
            padding: 8px 15px;
            font-size: 14px;
            border-radius: 4px;
            border: none;
            cursor: pointer;
        }

        .curator-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            margin-left: 10px;
        }

        .curator-reed { background: #4CAF50; color: white; }
        .curator-gigi { background: #9C27B0; color: white; }
        .curator-kiki { background: #E91E63; color: white; }

        /* Curate Input Styles */
        .curate-input-wrapper {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 10px;
        }

        .curate-input {
            flex: 1;
            padding: 8px 12px;
            font-size: 14px;
            border: 2px solid #ddd;
            border-radius: 4px;
            outline: none;
            transition: border-color 0.2s;
        }

        .curate-input:focus {
            border-color: #ff9800;
        }

        .curate-input::placeholder {
            color: #999;
        }

        .curated-tag {
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 13px;
            color: white;
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }

        .curated-tag .curator-name {
            font-size: 10px;
            opacity: 0.8;
        }

        .tag-delete-btn {
            display: none;
            margin-left: 5px;
            background: rgba(255,0,0,0.2);
            border: none;
            color: #c00;
            font-size: 12px;
            cursor: pointer;
            padding: 2px 6px;
            border-radius: 3px;
            line-height: 1;
        }

        .tag-delete-btn:hover {
            background: rgba(255,0,0,0.4);
        }

        .curate-mode .tag-delete-btn {
            display: inline-block;
        }

        .tag-container {
            display: inline-flex;
            align-items: center;
            gap: 2px;
        }

        /* Rejected inferred tag styling */
        .rejected-tag {
            background: #ffebee !important;
            color: #c62828 !important;
            text-decoration: line-through;
            opacity: 0.7;
        }

        .rejected-tag .tag-delete-btn {
            background: rgba(76, 175, 80, 0.2);
            color: #2e7d32;
        }

        .rejected-tag .tag-delete-btn:hover {
            background: rgba(76, 175, 80, 0.4);
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

        /* Tab Navigation Styles */
        .tab-nav {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 20px;
        }

        .tab-btn {
            padding: 12px 30px;
            font-size: 14px;
            font-weight: 500;
            border: 2px solid #000;
            background: #fff;
            color: #000;
            cursor: pointer;
            border-radius: 4px;
            transition: all 0.2s;
        }

        .tab-btn:hover {
            background: #f5f5f5;
        }

        .tab-btn.active {
            background: #000;
            color: #fff;
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }

        /* Dashboard Styles */
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: #fff;
            border-radius: 8px;
            padding: 25px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            text-align: center;
        }

        .stat-card .stat-value {
            font-size: 42px;
            font-weight: 700;
            color: #000;
        }

        .stat-card .stat-label {
            font-size: 14px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-top: 5px;
        }

        .stat-card.success .stat-value { color: #4CAF50; }
        .stat-card.warning .stat-value { color: #ff9800; }
        .stat-card.info .stat-value { color: #2196F3; }

        .chart-container {
            background: #fff;
            border-radius: 8px;
            padding: 25px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }

        .chart-title {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 15px;
            color: #333;
        }

        .activity-list {
            background: #fff;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .activity-item {
            padding: 12px 0;
            border-bottom: 1px solid #eee;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .activity-item:last-child {
            border-bottom: none;
        }

        .activity-product {
            font-weight: 500;
        }

        .activity-curator {
            font-size: 12px;
            padding: 4px 8px;
            border-radius: 12px;
            color: #fff;
        }

        .activity-time {
            font-size: 12px;
            color: #999;
        }

        /* Mark Complete Button */
        .complete-btn {
            background: #4CAF50;
            color: #fff;
            border: none;
            padding: 12px 25px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            border-radius: 4px;
            transition: background 0.2s;
            margin-right: 10px;
        }

        .complete-btn:hover {
            background: #388E3C;
        }

        .complete-btn.completed {
            background: #81C784;
        }

        .complete-btn.undo {
            background: #ff9800;
        }

        .complete-btn.undo:hover {
            background: #f57c00;
        }

        .curation-status-badge {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
            margin-left: 10px;
        }

        .curation-status-badge.complete {
            background: #e8f5e9;
            color: #2e7d32;
        }

        .curation-status-badge.pending {
            background: #fff3e0;
            color: #e65100;
        }

        /* Scraper Section Styles */
        .scraper-section {
            background: #fff;
            border-radius: 8px;
            padding: 25px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            text-align: center;
        }

        .scraper-section h3 {
            font-size: 20px;
            margin-bottom: 15px;
            color: #333;
        }

        .scraper-controls {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }

        .scraper-controls label {
            font-size: 14px;
            color: #666;
        }

        .scraper-controls select,
        .scraper-controls input {
            padding: 8px 12px;
            font-size: 14px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }

        .go-btn {
            background: linear-gradient(135deg, #4CAF50, #45a049);
            color: #fff;
            border: none;
            padding: 15px 50px;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
            border-radius: 8px;
            transition: all 0.3s;
            box-shadow: 0 4px 15px rgba(76, 175, 80, 0.3);
        }

        .go-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(76, 175, 80, 0.4);
        }

        .go-btn:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }

        .progress-container {
            margin-top: 20px;
            display: none;
        }

        .progress-container.visible {
            display: block;
        }

        .progress-bar-wrapper {
            background: #e0e0e0;
            border-radius: 10px;
            height: 20px;
            overflow: hidden;
            margin-bottom: 10px;
        }

        .progress-bar {
            height: 100%;
            background: linear-gradient(90deg, #4CAF50, #8BC34A);
            border-radius: 10px;
            transition: width 0.5s ease;
            width: 0%;
        }

        .progress-text {
            font-size: 14px;
            color: #666;
        }

        .progress-status {
            font-size: 16px;
            font-weight: 500;
            color: #333;
            margin-bottom: 10px;
        }

        .progress-details {
            font-size: 13px;
            color: #888;
        }

        /* Log Viewer Styles */
        .log-viewer {
            background: #1e1e1e;
            border-radius: 8px;
            padding: 15px;
            margin-top: 15px;
            max-height: 300px;
            overflow-y: auto;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 12px;
            line-height: 1.5;
            text-align: left;
            display: none;
        }

        .log-viewer.visible {
            display: block;
        }

        .log-viewer .log-line {
            color: #d4d4d4;
            margin: 0;
            padding: 2px 0;
            white-space: pre-wrap;
            word-break: break-all;
        }

        .log-viewer .log-line.error {
            color: #f44336;
        }

        .log-viewer .log-line.success {
            color: #4CAF50;
        }

        .log-viewer .log-line.warning {
            color: #ff9800;
        }

        .log-viewer .log-line.info {
            color: #2196F3;
        }

        .log-viewer .log-line.command {
            color: #9cdcfe;
        }

        .log-toggle {
            background: #333;
            color: #fff;
            border: none;
            padding: 8px 16px;
            font-size: 12px;
            cursor: pointer;
            border-radius: 4px;
            margin-top: 10px;
        }

        .log-toggle:hover {
            background: #444;
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

            /* AI Section Styles */
            .ai-section {
                background: #fff;
                border-radius: 8px;
                padding: 25px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                margin-bottom: 30px;
            }

            .ai-section h3 {
                font-size: 20px;
                margin-bottom: 15px;
                color: #333;
                display: flex;
                align-items: center;
                gap: 10px;
            }

            .ai-status {
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 500;
            }

            .ai-status.online {
                background: #e8f5e9;
                color: #2e7d32;
            }

            .ai-status.offline {
                background: #ffebee;
                color: #c62828;
            }

            .ai-status .dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
            }

            .ai-status.online .dot {
                background: #4CAF50;
                animation: pulse 2s infinite;
            }

            .ai-status.offline .dot {
                background: #f44336;
            }

            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }

            /* AI Search */
            .ai-search-container {
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
            }

            .ai-search-input {
                flex: 1;
                padding: 15px 20px;
                font-size: 16px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                outline: none;
                transition: border-color 0.2s, box-shadow 0.2s;
            }

            .ai-search-input:focus {
                border-color: #9c27b0;
                box-shadow: 0 0 0 3px rgba(156, 39, 176, 0.1);
            }

            .ai-search-input::placeholder {
                color: #999;
            }

            .ai-search-btn {
                padding: 15px 30px;
                background: linear-gradient(135deg, #9c27b0, #7b1fa2);
                color: #fff;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s;
            }

            .ai-search-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 15px rgba(156, 39, 176, 0.3);
            }

            .ai-search-btn:disabled {
                background: #ccc;
                cursor: not-allowed;
                transform: none;
                box-shadow: none;
            }

            /* AI Results */
            .ai-results {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                gap: 20px;
                margin-top: 20px;
            }

            .ai-result-card {
                background: #fafafa;
                border-radius: 8px;
                overflow: hidden;
                transition: transform 0.2s, box-shadow 0.2s;
                cursor: pointer;
            }

            .ai-result-card:hover {
                transform: translateY(-4px);
                box-shadow: 0 8px 25px rgba(0,0,0,0.15);
            }

            .ai-result-card img {
                width: 100%;
                height: 200px;
                object-fit: cover;
            }

            .ai-result-card .card-content {
                padding: 15px;
            }

            .ai-result-card .card-title {
                font-size: 14px;
                font-weight: 500;
                margin-bottom: 5px;
                color: #333;
            }

            .ai-result-card .card-price {
                font-size: 16px;
                font-weight: 600;
                color: #000;
            }

            .ai-result-card .card-similarity {
                font-size: 11px;
                color: #9c27b0;
                margin-top: 5px;
            }

            /* Generate Tags Section */
            .generate-tags-section {
                display: flex;
                gap: 15px;
                align-items: center;
                flex-wrap: wrap;
            }

            .generate-tags-btn {
                padding: 12px 25px;
                background: linear-gradient(135deg, #ff9800, #f57c00);
                color: #fff;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s;
            }

            .generate-tags-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 15px rgba(255, 152, 0, 0.3);
            }

            .generate-tags-btn:disabled {
                background: #ccc;
                cursor: not-allowed;
                transform: none;
            }

            /* AI Generate Tags Button for Product Page */
            .ai-generate-btn {
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 8px 16px;
                background: linear-gradient(135deg, #9c27b0, #7b1fa2);
                color: #fff;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s;
                margin-left: 10px;
            }

            .ai-generate-btn:hover {
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(156, 39, 176, 0.4);
            }

            .ai-generate-btn:disabled {
                background: #ccc;
                cursor: not-allowed;
                transform: none;
                box-shadow: none;
            }

            .ai-generate-btn.loading {
                pointer-events: none;
            }

            .ai-generate-btn .spinner {
                width: 14px;
                height: 14px;
                border: 2px solid rgba(255,255,255,0.3);
                border-top-color: #fff;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                display: none;
            }

            .ai-generate-btn.loading .spinner {
                display: inline-block;
            }

            .ai-generate-btn.loading .btn-text {
                display: none;
            }

            /* AI Generated Tag Styling - Teal/Cyan color */
            .ai-generated-tag {
                background: linear-gradient(135deg, #00bcd4, #0097a7) !important;
                color: #fff !important;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 13px;
                display: inline-flex;
                align-items: center;
                gap: 5px;
            }

            .ai-generated-tag .ai-badge {
                font-size: 10px;
                opacity: 0.9;
                background: rgba(255,255,255,0.2);
                padding: 1px 4px;
                border-radius: 3px;
            }

            .ai-generated-tag .tag-delete-btn {
                display: none;
                margin-left: 5px;
                background: rgba(255,255,255,0.2);
                border: none;
                color: #fff;
                font-size: 12px;
                cursor: pointer;
                padding: 2px 6px;
                border-radius: 3px;
                line-height: 1;
            }

            .ai-generated-tag .tag-delete-btn:hover {
                background: rgba(255,0,0,0.3);
            }

            .curate-mode .ai-generated-tag .tag-delete-btn {
                display: inline-block;
            }

            .ai-progress {
                display: none;
                align-items: center;
                gap: 10px;
                color: #666;
            }

            .ai-progress.visible {
                display: flex;
            }

            .ai-spinner {
                width: 20px;
                height: 20px;
                border: 3px solid #e0e0e0;
                border-top-color: #9c27b0;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }

            @keyframes spin {
                to { transform: rotate(360deg); }
            }

            /* AI Chat Widget */
            .ai-chat-container {
                background: #f8f9fa;
                border-radius: 8px;
                padding: 20px;
                margin-top: 20px;
            }

            .ai-chat-messages {
                max-height: 400px;
                overflow-y: auto;
                margin-bottom: 15px;
                padding: 10px;
                background: #fff;
                border-radius: 8px;
                min-height: 200px;
            }

            .ai-chat-message {
                margin-bottom: 15px;
                padding: 12px 15px;
                border-radius: 12px;
                max-width: 85%;
            }

            .ai-chat-message.user {
                background: #e3f2fd;
                margin-left: auto;
                border-bottom-right-radius: 4px;
            }

            .ai-chat-message.assistant {
                background: #f3e5f5;
                margin-right: auto;
                border-bottom-left-radius: 4px;
            }

            .ai-chat-message .role {
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                margin-bottom: 5px;
                color: #666;
            }

            .ai-chat-input-container {
                display: flex;
                gap: 10px;
            }

            .ai-chat-input {
                flex: 1;
                padding: 12px 15px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                font-size: 14px;
                outline: none;
            }

            .ai-chat-input:focus {
                border-color: #9c27b0;
            }

            .ai-chat-send {
                padding: 12px 25px;
                background: #9c27b0;
                color: #fff;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-weight: 500;
            }

            .ai-chat-send:hover {
                background: #7b1fa2;
            }

            .no-results {
                text-align: center;
                padding: 40px;
                color: #666;
            }
    </style>
</head>
<body>
    <header>
        <h1>ZARA PRODUCT VIEWER</h1>
        <div style="margin-top: 10px;">
            <span class="data-source">{{ '🗄️ Supabase Database' if use_supabase else '📁 Local Files' }}</span>
            <button class="curate-btn" id="curateBtn" onclick="toggleCurateMode()">✏️ Curate</button>
            <span class="curator-selector" id="curatorSelector">
                <select id="curatorSelect" onchange="selectCurator(this.value)">
                    <option value="">Select curator...</option>
                    <option value="Reed">Reed</option>
                    <option value="Gigi">Gigi</option>
                    <option value="Kiki">Kiki</option>
                </select>
            </span>
            <span class="curator-badge" id="curatorBadge" style="display: none;"></span>
        </div>
    </header>

    <div class="container">
        <!-- Tab Navigation -->
        <div class="tab-nav">
            <button class="tab-btn active" id="tabProducts" onclick="switchTab('products')">📦 Products</button>
            <button class="tab-btn" id="tabAI" onclick="switchTab('ai')">🤖 AI Assistant</button>
            <button class="tab-btn" id="tabDashboard" onclick="switchTab('dashboard')">📊 Dashboard</button>
        </div>

        <!-- Products Tab Content -->
        <div id="productsTab" class="tab-content active">
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

        <!-- AI Tab Content -->
        <div id="aiTab" class="tab-content">
            <div class="ai-section">
                <h3>
                    🔍 Semantic Search
                    <span class="ai-status" id="aiStatus">
                        <span class="dot"></span>
                        <span id="aiStatusText">Checking...</span>
                    </span>
                </h3>
                <p style="color: #666; margin-bottom: 15px;">Search products using natural language. Describe what you're looking for and AI will find matching items.</p>

                <div class="ai-search-container">
                    <input type="text"
                           class="ai-search-input"
                           id="aiSearchInput"
                           placeholder="e.g., 'minimal white t-shirt', 'casual summer outfit', 'formal dark blazer'..."
                           onkeypress="handleAISearchKeypress(event)">
                    <button class="ai-search-btn" id="aiSearchBtn" onclick="performAISearch()">🔍 Search</button>
                </div>

                <div class="ai-progress" id="searchProgress">
                    <div class="ai-spinner"></div>
                    <span>Searching...</span>
                </div>

                <div id="aiSearchResults"></div>
            </div>

            <div class="ai-section">
                <h3>🏷️ Generate Style Tags</h3>
                <p style="color: #666; margin-bottom: 15px;">Use AI vision to analyze product images and generate style tags automatically.</p>

                <div class="generate-tags-section">
                    <button class="generate-tags-btn" id="generateAllTagsBtn" onclick="generateAllTags()">
                        🤖 Generate Tags for All Products
                    </button>
                    <button class="generate-tags-btn" style="background: linear-gradient(135deg, #2196F3, #1976D2);" onclick="generateTagsForCurrent()">
                        🏷️ Generate Tags for Current Product
                    </button>
                    <div class="ai-progress" id="tagProgress">
                        <div class="ai-spinner"></div>
                        <span id="tagProgressText">Generating...</span>
                    </div>
                </div>

                <div id="tagResults" style="margin-top: 15px;"></div>
            </div>

            <div class="ai-section">
                <h3>💬 Fashion Assistant</h3>
                <p style="color: #666; margin-bottom: 15px;">Chat with the AI about styling advice, outfit recommendations, and product questions.</p>

                <div class="ai-chat-container">
                    <div class="ai-chat-messages" id="chatMessages">
                        <div class="ai-chat-message assistant">
                            <div class="role">Assistant</div>
                            <div>Hello! I'm your fashion assistant. Ask me about styling advice, outfit combinations, or help finding the perfect items from our catalog.</div>
                        </div>
                    </div>
                    <div class="ai-chat-input-container">
                        <input type="text"
                               class="ai-chat-input"
                               id="chatInput"
                               placeholder="Ask about styling, outfits, or products..."
                               onkeypress="handleChatKeypress(event)">
                        <button class="ai-chat-send" onclick="sendChatMessage()">Send</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Dashboard Tab Content -->
        <div id="dashboardTab" class="tab-content">
            <div id="dashboardContent">
                <div class="no-data">
                    <h2>Loading dashboard...</h2>
                </div>
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

        async function displayProduct(index) {
            if (index < 0 || index >= products.length) return;

            currentIndex = index;
            currentImageIndex = 0;
            const product = products[index];

            // Update counter
            document.getElementById('counter').textContent = `Product ${index + 1} of ${products.length}`;

            // Update navigation buttons
            document.getElementById('prevBtn').disabled = index === 0;
            document.getElementById('nextBtn').disabled = index === products.length - 1;

            // Fetch curated metadata for this product (if using Supabase)
            let curatedTags = [];
            let curatedFit = [];
            let curatedWeight = [];
            let rejectedTags = [];
            let aiGeneratedTags = [];
            let curationStatus = null;
            if (useSupabase) {
                // Fetch curated data
                try {
                    const curatedResponse = await fetch(`/api/curated/${product.product_id}`);
                    const curatedData = await curatedResponse.json();
                    if (Array.isArray(curatedData)) {
                        curatedTags = curatedData.filter(c => c.field_name === 'style_tag');
                        curatedFit = curatedData.filter(c => c.field_name === 'fit');
                        curatedWeight = curatedData.filter(c => c.field_name === 'weight');
                    }
                } catch (error) {
                    console.error('Error fetching curated data:', error);
                }

                // Fetch rejected tags (may fail if table doesn't exist yet)
                try {
                    const rejectedResponse = await fetch(`/api/rejected_tags/${product.product_id}`);
                    const rejectedData = await rejectedResponse.json();
                    if (Array.isArray(rejectedData)) {
                        rejectedTags = rejectedData;
                    }
                } catch (error) {
                    console.warn('Could not fetch rejected tags (table may not exist yet):', error);
                }

                // Fetch AI-generated tags (may fail if table doesn't exist yet)
                try {
                    const aiTagsResponse = await fetch(`/api/ai_tags/${product.product_id}`);
                    const aiTagsData = await aiTagsResponse.json();
                    if (Array.isArray(aiTagsData)) {
                        aiGeneratedTags = aiTagsData.filter(t => t.field_name === 'style_tag');
                    }
                } catch (error) {
                    console.warn('Could not fetch AI-generated tags (table may not exist yet):', error);
                }

                // Fetch curation status
                try {
                    const statusResponse = await fetch(`/api/curation_status/${product.product_id}`);
                    curationStatus = await statusResponse.json();
                } catch (error) {
                    console.warn('Could not fetch curation status:', error);
                }
            }

            // Store for global access
            window.currentCurationStatus = curationStatus;

            // Store rejected tags globally for easy lookup
            window.currentRejectedTags = rejectedTags;

            // Store AI-generated tags globally
            window.currentAIGeneratedTags = aiGeneratedTags;

            // Helper function to check if an inferred tag is rejected
            function isTagRejected(fieldName, fieldValue) {
                return rejectedTags.some(r => r.field_name === fieldName && r.field_value === fieldValue);
            }

            // Helper function to get rejection info for a tag
            function getRejectionInfo(fieldName, fieldValue) {
                return rejectedTags.find(r => r.field_name === fieldName && r.field_value === fieldValue);
            }

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

            // Build size tags with availability styling
            // Try to use sizes_availability first (new format with availability), fallback to sizes (old format)
            const sizesAvailability = product.sizes_availability || [];
            const sizesOld = (product.sizes || []).filter(s => s && s.trim() && s !== 'Add');

            let sizeTags = '';
            if (sizesAvailability.length > 0) {
                // New format: [{"size": "M", "available": true}, ...]
                sizeTags = sizesAvailability.map(s => {
                    const sizeLabel = typeof s === 'object' ? s.size : s;
                    const isAvailable = typeof s === 'object' ? s.available : true;

                    if (isAvailable) {
                        return `<span class="tag">${sizeLabel}</span>`;
                    } else {
                        return `<span class="tag" style="background: #ffebee; color: #c62828; text-decoration: line-through; opacity: 0.7;" title="Out of stock">${sizeLabel}</span>`;
                    }
                }).join('');
            } else if (sizesOld.length > 0) {
                // Old format: ["S", "M", "L"]
                sizeTags = sizesOld.map(s => `<span class="tag">${s}</span>`).join('');
            }

            const materialTags = (product.materials || []).map(m => `<span class="tag">${m}</span>`).join('');
            // Build style tags with reasoning (hover to see reasoning)
            const styleTags = (product.style_tags || []).map(s => {
                // Handle both old format (string) and new format (object with tag/reasoning)
                const tagValue = typeof s === 'string' ? s : s.tag;
                const reasoning = typeof s === 'string' ? '' : (s.reasoning || '');
                const isRejected = isTagRejected('style_tag', tagValue);
                const rejectedClass = isRejected ? 'rejected-tag' : '';
                const deleteTitle = isRejected ? 'Undo rejection (restore tag)' : 'Mark as incorrect';
                const deleteSymbol = isRejected ? '↩' : '×';

                return `<span class="tag-container">
                    <span class="tag ${rejectedClass}" style="background:#e3f2fd;color:#1565c0;cursor:help;" title="${reasoning}" data-field="style_tag" data-value="${tagValue}" data-reasoning="${reasoning}" data-type="inferred">${tagValue}</span>
                    <button class="tag-delete-btn" data-field="style_tag" data-value="${tagValue}" data-rejected="${isRejected}" onclick="handleTagDeleteClick(this)" title="${deleteTitle}">${deleteSymbol}</button>
                </span>`;
            }).join('');

            // Build fit badge (teal/cyan - distinct from curator colors)
            let fitBadge = '';
            if (product.fit) {
                const fitValue = product.fit;
                const isFitRejected = isTagRejected('fit', fitValue);
                const fitRejectedClass = isFitRejected ? 'rejected-tag' : '';
                const fitDeleteTitle = isFitRejected ? 'Undo rejection (restore tag)' : 'Mark as incorrect';
                const fitDeleteSymbol = isFitRejected ? '↩' : '×';

                fitBadge = `<span class="tag-container">
                    <span class="tag ${fitRejectedClass}" style="background:#e0f7fa;color:#00838f;" data-field="fit" data-value="${fitValue}" data-type="inferred">${fitValue}</span>
                    <button class="tag-delete-btn" data-field="fit" data-value="${fitValue}" data-rejected="${isFitRejected}" data-reasoning="" onclick="handleTagDeleteClick(this)" title="${fitDeleteTitle}">${fitDeleteSymbol}</button>
                </span>`;
            }

            // Build weight badge with reasoning (amber/gold - distinct from curator colors)
            let weightBadge = '';
            let weightReasoning = '';
            if (product.weight) {
                let weightValue = '';
                let weightReasoningText = '';

                if (typeof product.weight === 'string') {
                    weightValue = product.weight;
                } else {
                    weightValue = product.weight.value;
                    weightReasoningText = (product.weight.reasoning || []).join(' • ');
                    weightReasoning = weightReasoningText;
                }

                const isWeightRejected = isTagRejected('weight', weightValue);
                const weightRejectedClass = isWeightRejected ? 'rejected-tag' : '';
                const weightDeleteTitle = isWeightRejected ? 'Undo rejection (restore tag)' : 'Mark as incorrect';
                const weightDeleteSymbol = isWeightRejected ? '↩' : '×';

                weightBadge = `<span class="tag-container">
                    <span class="tag ${weightRejectedClass}" style="background:#fff8e1;color:#ff8f00;" data-field="weight" data-value="${weightValue}" data-type="inferred">${weightValue}</span>
                    <button class="tag-delete-btn" data-field="weight" data-value="${weightValue}" data-rejected="${isWeightRejected}" data-reasoning="${weightReasoningText}" onclick="handleTagDeleteClick(this)" title="${weightDeleteTitle}">${weightDeleteSymbol}</button>
                </span>`;
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

                    ${fitBadge || curatedFit.length > 0 ? `
                        <h3 class="section-title">Fit</h3>
                        <div class="tag-list" id="fitTagsList">${fitBadge}${renderCuratedTagsInline(curatedFit)}</div>
                    ` : `
                        <h3 class="section-title">Fit</h3>
                        <div class="tag-list" id="fitTagsList"><span style="color:#999;font-size:13px;">Not specified</span></div>
                    `}
                    <div id="curateFitInput"></div>

                    ${weightBadge || curatedWeight.length > 0 ? `
                        <h3 class="section-title">Weight</h3>
                        <div class="tag-list" id="weightTagsList">${weightBadge}${renderCuratedTagsInline(curatedWeight)}</div>
                        ${weightReasoning ? `<div style="font-size: 12px; color: #666; margin-top: 5px;"><em>${weightReasoning}</em></div>` : ''}
                    ` : `
                        <h3 class="section-title">Weight</h3>
                        <div class="tag-list" id="weightTagsList"><span style="color:#999;font-size:13px;">Not specified</span></div>
                    `}
                    <div id="curateWeightInput"></div>

                    ${styleTags || curatedTags.length > 0 ? `
                        <h3 class="section-title">
                            Style Tags <span style="font-size:10px;color:#999;font-weight:normal;">(hover for reasoning)</span>
                            <button class="ai-generate-btn" onclick="generateAITagsForProduct('${product.product_id}')" id="aiGenTagsBtn">
                                <span class="spinner"></span>
                            <span class="btn-text">🤖 AI Generate</span>
                            </button>
                        </h3>
                        <div class="tag-list" id="styleTagsList">${styleTags}${renderCuratedTagsInline(curatedTags)}${renderAIGeneratedTagsInline(aiGeneratedTags)}</div>
                    ` : `
                        <h3 class="section-title">
                            Style Tags
                            <button class="ai-generate-btn" onclick="generateAITagsForProduct('${product.product_id}')" id="aiGenTagsBtn">
                                <span class="spinner"></span>
                                <span class="btn-text">🤖 AI Generate</span>
                            </button>
                        </h3>
                        <div class="tag-list" id="styleTagsList">${renderAIGeneratedTagsInline(aiGeneratedTags) || '<span style="color:#999;font-size:13px;">No style tags</span>'}</div>
                    `}
                    <div id="aiTagsStatus" style="margin-top: 8px; font-size: 12px;"></div>
                    <div id="curateStyleTagInput"></div>

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
                        <h3 class="section-title">Curation Status</h3>
                        <div id="curationStatusArea">
                            ${curationStatus && curationStatus.status === 'complete' ? `
                                <span class="curation-status-badge complete">✓ Curated by ${curationStatus.curator}</span>
                                ${curationStatus.notes ? `<p style="font-size:12px;color:#666;margin-top:5px;">Notes: ${curationStatus.notes}</p>` : ''}
                            ` : `
                                <span class="curation-status-badge pending">⏳ Pending Curation</span>
                            `}
                        </div>
                        <div id="curationButtonArea" style="margin-top: 15px;"></div>
                    </div>

                    <div class="danger-zone" style="margin-top: 30px; padding: 15px; border: 1px solid #ffcdd2; border-radius: 8px; background: #fff5f5;">
                        <h3 class="section-title" style="color: #c62828; margin-top: 0;">⚠️ Danger Zone</h3>
                        <p style="font-size: 12px; color: #666; margin-bottom: 10px;">Permanently delete this product from the database.</p>
                        <button onclick="deleteProduct('${product.product_id}')"
                                style="background: #f44336; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 13px;"
                                onmouseover="this.style.background='#d32f2f'"
                                onmouseout="this.style.background='#f44336'">
                            🗑️ Delete Product
                        </button>
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

        async function deleteProduct(productId) {
            // Show confirmation dialog
            const productName = products[currentIndex]?.name || productId;
            const confirmed = confirm(`Are you sure you want to delete this product?\n\n"${productName}"\n(ID: ${productId})\n\nThis action cannot be undone.`);

            if (!confirmed) return;

            try {
                const response = await fetch(`/api/products/${productId}`, {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' }
                });

                const result = await response.json();

                if (response.ok && result.success) {
                    // Remove from local products array
                    const deletedIndex = products.findIndex(p => p.product_id === productId);
                    if (deletedIndex !== -1) {
                        products.splice(deletedIndex, 1);
                    }

                    // Show success message
                    alert(`✓ Product deleted successfully!\n\nImages deleted: ${result.images_deleted || 0}`);

                    // Navigate to next product or reload
                    if (products.length === 0) {
                        document.getElementById('productCard').innerHTML = `
                            <div class="no-data">
                                <h2>No products remaining</h2>
                                <p>All products have been deleted. Run the scraper to add more.</p>
                            </div>
                        `;
                        document.getElementById('counter').textContent = 'No products';
                    } else {
                        // Adjust current index if needed
                        if (currentIndex >= products.length) {
                            currentIndex = products.length - 1;
                        }
                        displayProduct(currentIndex);
                    }
                } else {
                    alert(`❌ Failed to delete product:\n${result.error || 'Unknown error'}`);
                }
            } catch (error) {
                console.error('Error deleting product:', error);
                alert(`❌ Error deleting product:\n${error.message}`);
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

        // ============================================
        // CURATE MODE FUNCTIONALITY
        // ============================================
        let curateMode = false;
        let currentCurator = null;

        const curatorColors = {
            'Reed': { bg: '#4CAF50', class: 'curator-reed' },
            'Gigi': { bg: '#9C27B0', class: 'curator-gigi' },
            'Kiki': { bg: '#E91E63', class: 'curator-kiki' }
        };

        function renderCuratedTagsInline(curatedTags) {
            if (!curatedTags || curatedTags.length === 0) {
                return '';
            }

            return curatedTags.map(tag => {
                const colorInfo = curatorColors[tag.curator] || { bg: '#999' };
                return `<span class="tag-container">
                    <span class="curated-tag" style="background: ${colorInfo.bg};" data-type="curated" data-field="${tag.field_name}" data-value="${tag.field_value}" data-curator="${tag.curator}">
                        ${tag.field_value} <span class="curator-name">(${tag.curator})</span>
                    </span>
                    <button class="tag-delete-btn" onclick="handleCuratedTagDelete('${tag.field_name}', '${tag.field_value}', '${tag.curator}')" title="Delete curated tag">×</button>
                </span>`;
            }).join('');
        }

        // Render AI-generated tags with teal/cyan color
        function renderAIGeneratedTagsInline(aiTags) {
            if (!aiTags || aiTags.length === 0) {
                return '';
            }

            return aiTags.map(tag => {
                return `<span class="tag-container">
                    <span class="ai-generated-tag" data-type="ai-generated" data-field="${tag.field_name}" data-value="${tag.field_value}">
                        ${tag.field_value} <span class="ai-badge">🤖 AI</span>
                    </span>
                    <button class="tag-delete-btn" onclick="handleAITagDelete('${tag.field_name}', '${tag.field_value}')" title="Delete AI-generated tag">×</button>
                </span>`;
            }).join('');
        }

        function renderCuratedTags(curatedTags) {
            if (!curatedTags || curatedTags.length === 0) {
                return '';
            }

            const tagsHtml = curatedTags.map(tag => {
                const colorInfo = curatorColors[tag.curator] || { bg: '#999' };
                return `<span class="curated-tag" style="background: ${colorInfo.bg};">
                    ${tag.field_value} <span class="curator-name">(${tag.curator})</span>
                </span>`;
            }).join('');

            return `
                <h3 class="section-title" style="margin-top: 15px;">Curated Tags</h3>
                <div class="tag-list">${tagsHtml}</div>
            `;
        }

        function toggleCurateMode() {
            const btn = document.getElementById('curateBtn');
            const selector = document.getElementById('curatorSelector');

            if (!curateMode) {
                // Entering curate mode - show curator selector
                selector.classList.add('visible');
                btn.textContent = '❌ Exit Curate';
                btn.classList.add('active');
                document.body.classList.add('curate-mode');
                curateMode = true;
            } else {
                // Exiting curate mode
                exitCurateMode();
            }
        }

        function exitCurateMode() {
            const btn = document.getElementById('curateBtn');
            const selector = document.getElementById('curatorSelector');
            const badge = document.getElementById('curatorBadge');

            selector.classList.remove('visible');
            badge.style.display = 'none';
            btn.textContent = '✏️ Curate';
            btn.classList.remove('active');
            document.getElementById('curatorSelect').value = '';
            document.body.classList.remove('curate-mode');

            curateMode = false;
            currentCurator = null;

            // Re-render the product to hide curate inputs
            if (products.length > 0) {
                displayProduct(currentIndex);
            }
        }

        async function selectCurator(curator) {
            if (!curator) {
                currentCurator = null;
                document.getElementById('curatorBadge').style.display = 'none';
                return;
            }

            currentCurator = curator;
            const badge = document.getElementById('curatorBadge');
            const colorInfo = curatorColors[curator];

            badge.textContent = `Curating as: ${curator}`;
            badge.className = `curator-badge ${colorInfo.class}`;
            badge.style.display = 'inline-block';

            // Re-render the product to show curate inputs (await since displayProduct is async)
            await displayProduct(currentIndex);

            // Show the curate input after render
            showCurateInputs();
        }

        function showCurateInputs() {
            if (!currentCurator) return;

            const colorInfo = curatorColors[currentCurator];

            // Style Tags input
            const styleInputContainer = document.getElementById('curateStyleTagInput');
            if (styleInputContainer) {
                styleInputContainer.innerHTML = `
                    <div class="curate-input-wrapper">
                        <input type="text"
                               class="curate-input"
                               id="newStyleTagInput"
                               placeholder="Add new style tag... (press Enter)"
                               onkeypress="handleCurateKeypress(event, 'style_tag', 'styleTagsList')"
                               style="border-color: ${colorInfo.bg};">
                    </div>
                `;
            }

            // Fit input
            const fitInputContainer = document.getElementById('curateFitInput');
            if (fitInputContainer) {
                fitInputContainer.innerHTML = `
                    <div class="curate-input-wrapper">
                        <input type="text"
                               class="curate-input"
                               id="newFitInput"
                               placeholder="Add fit value... (e.g., slim, relaxed, oversized)"
                               onkeypress="handleCurateKeypress(event, 'fit', 'fitTagsList')"
                               style="border-color: ${colorInfo.bg};">
                    </div>
                `;
            }

            // Weight input
            const weightInputContainer = document.getElementById('curateWeightInput');
            if (weightInputContainer) {
                weightInputContainer.innerHTML = `
                    <div class="curate-input-wrapper">
                        <input type="text"
                               class="curate-input"
                               id="newWeightInput"
                               placeholder="Add weight value... (e.g., light, medium, heavy)"
                               onkeypress="handleCurateKeypress(event, 'weight', 'weightTagsList')"
                               style="border-color: ${colorInfo.bg};">
                    </div>
                `;
            }

            // Mark as Complete button
            const curationButtonArea = document.getElementById('curationButtonArea');
            if (curationButtonArea) {
                const curationStatus = window.currentCurationStatus;
                if (curationStatus && curationStatus.status === 'complete') {
                    curationButtonArea.innerHTML = `
                        <button class="complete-btn undo" onclick="unmarkProductComplete()">↩ Undo Completion</button>
                    `;
                } else {
                    curationButtonArea.innerHTML = `
                        <button class="complete-btn" onclick="markProductComplete()">✓ Mark as Complete (Good as is)</button>
                    `;
                }
            }
        }

        function handleCurateKeypress(event, fieldName, tagsListId) {
            if (event.key === 'Enter') {
                const input = event.target;
                const tagValue = input.value.trim();

                if (tagValue && currentCurator) {
                    addCuratedField(tagValue, fieldName, tagsListId);
                    input.value = '';
                }
            }
        }

        async function addCuratedField(tagValue, fieldName, tagsListId) {
            const product = products[currentIndex];
            const colorInfo = curatorColors[currentCurator];

            // Add the tag to the display immediately
            const tagsList = document.getElementById(tagsListId);

            // Remove "Not specified" placeholder if present
            const placeholder = tagsList.querySelector('span[style*="color:#999"]');
            if (placeholder) {
                placeholder.remove();
            }

            // Create the new curated tag element
            const newTag = document.createElement('span');
            newTag.className = 'curated-tag';
            newTag.style.background = colorInfo.bg;
            newTag.innerHTML = `${tagValue} <span class="curator-name">(${currentCurator})</span>`;
            tagsList.appendChild(newTag);

            // Save to database
            try {
                const response = await fetch('/api/curated', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        product_id: product.product_id,
                        field_name: fieldName,
                        field_value: tagValue,
                        curator: currentCurator
                    })
                });
                const result = await response.json();
                if (result.success) {
                    console.log(`✓ Saved curated ${fieldName}: "${tagValue}" by ${currentCurator}`);
                } else {
                    console.error('Failed to save:', result.error);
                }
            } catch (error) {
                console.error('Error saving curated field:', error);
            }
        }

        // ============================================
        // TAG DELETION FUNCTIONALITY
        // ============================================

        function handleTagDeleteClick(button) {
            const fieldName = button.dataset.field;
            const fieldValue = button.dataset.value;
            const isRejected = button.dataset.rejected === 'true';
            const reasoning = button.dataset.reasoning || '';

            handleInferredTagDelete(fieldName, fieldValue, reasoning, isRejected);
        }

        async function handleCuratedTagDelete(fieldName, fieldValue, curator) {
            if (!curateMode || !currentCurator) {
                alert('Please enter curate mode first to delete tags.');
                return;
            }

            const product = products[currentIndex];

            if (!confirm(`Delete curated tag "${fieldValue}" added by ${curator}?`)) {
                return;
            }

            try {
                const response = await fetch('/api/curated', {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        product_id: product.product_id,
                        field_name: fieldName,
                        field_value: fieldValue,
                        curator: curator
                    })
                });

                const result = await response.json();
                if (result.success || result.error === undefined) {
                    console.log(`✓ Deleted curated tag: "${fieldValue}" by ${curator}`);
                    // Refresh the display
                    await displayProduct(currentIndex);
                    showCurateInputs();
                } else {
                    console.error('Failed to delete:', result.error);
                    alert('Failed to delete tag: ' + result.error);
                }
            } catch (error) {
                console.error('Error deleting curated tag:', error);
                alert('Error deleting tag');
            }
        }

        // Handle deletion of AI-generated tags
        async function handleAITagDelete(fieldName, fieldValue) {
            if (!curateMode || !currentCurator) {
                alert('Please enter curate mode first to delete tags.');
                return;
            }

            const product = products[currentIndex];

            if (!confirm(`Delete AI-generated tag "${fieldValue}"?`)) {
                return;
            }

            try {
                const response = await fetch('/api/ai_tags', {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        product_id: product.product_id,
                        field_name: fieldName,
                        field_value: fieldValue
                    })
                });

                const result = await response.json();
                if (result.success || result.error === undefined) {
                    console.log(`✓ Deleted AI-generated tag: "${fieldValue}"`);
                    // Refresh the display
                    await displayProduct(currentIndex);
                    showCurateInputs();
                } else {
                    console.error('Failed to delete:', result.error);
                    alert('Failed to delete AI tag: ' + result.error);
                }
            } catch (error) {
                console.error('Error deleting AI-generated tag:', error);
                alert('Error deleting AI tag');
            }
        }

        async function handleInferredTagDelete(fieldName, fieldValue, reasoning, isCurrentlyRejected) {
            if (!curateMode || !currentCurator) {
                alert('Please enter curate mode first to manage tags.');
                return;
            }

            const product = products[currentIndex];

            if (isCurrentlyRejected) {
                // Undo rejection - restore the tag
                if (!confirm(`Restore tag "${fieldValue}"? This will undo the rejection.`)) {
                    return;
                }

                try {
                    const response = await fetch('/api/rejected_tags', {
                        method: 'DELETE',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            product_id: product.product_id,
                            field_name: fieldName,
                            field_value: fieldValue
                        })
                    });

                    const result = await response.json();
                    if (result.success || result.error === undefined) {
                        console.log(`✓ Restored inferred tag: "${fieldValue}"`);
                        // Refresh the display
                        await displayProduct(currentIndex);
                        showCurateInputs();
                    } else {
                        console.error('Failed to restore:', result.error);
                        alert('Failed to restore tag: ' + result.error);
                    }
                } catch (error) {
                    console.error('Error restoring tag:', error);
                    alert('Error restoring tag');
                }
            } else {
                // Mark as rejected
                const rejectionReason = prompt(`Mark "${fieldValue}" as incorrect?\n\nOptionally, enter why this tag is wrong (for ML training):`, '');

                if (rejectionReason === null) {
                    return; // User cancelled
                }

                try {
                    const response = await fetch('/api/rejected_tags', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            product_id: product.product_id,
                            field_name: fieldName,
                            field_value: fieldValue,
                            original_reasoning: reasoning,
                            curator: currentCurator,
                            rejection_reason: rejectionReason || null
                        })
                    });

                    const result = await response.json();
                    if (result.success) {
                        console.log(`✓ Marked inferred tag as rejected: "${fieldValue}" (reason: ${rejectionReason || 'not provided'})`);
                        // Refresh the display
                        await displayProduct(currentIndex);
                        showCurateInputs();
                    } else {
                        console.error('Failed to reject:', result.error);
                        alert('Failed to mark as incorrect: ' + result.error);
                    }
                } catch (error) {
                    console.error('Error rejecting tag:', error);
                    alert('Error marking tag as incorrect');
                }
            }
        }

        // Load products on page load
        loadProducts();

        // ============================================
        // TAB NAVIGATION
        // ============================================

        function switchTab(tab) {
            // Update tab buttons
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            if (tab === 'products') {
                document.getElementById('tabProducts').classList.add('active');
            } else if (tab === 'ai') {
                document.getElementById('tabAI').classList.add('active');
            } else {
                document.getElementById('tabDashboard').classList.add('active');
            }

            // Update tab content
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
            if (tab === 'products') {
                document.getElementById('productsTab').classList.add('active');
            } else if (tab === 'ai') {
                document.getElementById('aiTab').classList.add('active');
                checkAIStatus();
            } else {
                document.getElementById('dashboardTab').classList.add('active');
                loadDashboard();
            }
        }

        // ============================================
        // AI FUNCTIONALITY
        // ============================================

        let chatHistory = [];

        async function checkAIStatus() {
            const statusEl = document.getElementById('aiStatus');
            const statusText = document.getElementById('aiStatusText');

            try {
                const response = await fetch('/api/ai/status');
                const data = await response.json();

                if (data.available) {
                    statusEl.classList.remove('offline');
                    statusEl.classList.add('online');
                    statusText.textContent = 'Online';
                } else {
                    statusEl.classList.remove('online');
                    statusEl.classList.add('offline');
                    statusText.textContent = 'Offline';
                }
            } catch (error) {
                statusEl.classList.remove('online');
                statusEl.classList.add('offline');
                statusText.textContent = 'Error';
            }
        }

        function handleAISearchKeypress(event) {
            if (event.key === 'Enter') {
                performAISearch();
            }
        }

        async function performAISearch() {
            const input = document.getElementById('aiSearchInput');
            const query = input.value.trim();

            if (!query) {
                alert('Please enter a search query');
                return;
            }

            const searchBtn = document.getElementById('aiSearchBtn');
            const progress = document.getElementById('searchProgress');
            const results = document.getElementById('aiSearchResults');

            searchBtn.disabled = true;
            progress.classList.add('visible');
            results.innerHTML = '';

            try {
                const response = await fetch('/api/ai/search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: query, limit: 12 })
                });

                const data = await response.json();

                if (data.error) {
                    results.innerHTML = `<div class="no-results"><p>❌ ${data.error}</p></div>`;
                } else if (data.results && data.results.length > 0) {
                    renderSearchResults(data.results);
                } else {
                    results.innerHTML = `<div class="no-results"><p>No matching products found. Try a different description.</p></div>`;
                }
            } catch (error) {
                results.innerHTML = `<div class="no-results"><p>❌ Error: ${error.message}</p></div>`;
            } finally {
                searchBtn.disabled = false;
                progress.classList.remove('visible');
            }
        }

        function renderSearchResults(results) {
            const container = document.getElementById('aiSearchResults');
            const supabaseUrl = '{{ supabase_url }}';

            const html = `
                <p style="color: #666; margin-bottom: 15px;">Found ${results.length} matching products:</p>
                <div class="ai-results">
                    ${results.map(product => {
                        let imageUrl = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="250" height="200" fill="%23ccc"><rect width="100%" height="100%"/><text x="50%" y="50%" text-anchor="middle" fill="%23999">No Image</text></svg>';

                        if (product.image_urls && product.image_urls[0]) {
                            imageUrl = product.image_urls[0];
                        } else if (product.primary_image) {
                            imageUrl = product.primary_image;
                        }

                        const similarity = product.similarity ? Math.round(product.similarity * 100) : '';

                        return `
                            <div class="ai-result-card" onclick="goToProduct('${product.product_id}')">
                                <img src="${imageUrl}" alt="${product.name}" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22250%22 height=%22200%22 fill=%22%23ccc%22><rect width=%22100%25%22 height=%22100%25%22/><text x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 fill=%22%23999%22>No Image</text></svg>'">
                                <div class="card-content">
                                    <div class="card-title">${product.name || 'Unknown'}</div>
                                    <div class="card-price">${product.price || ''}</div>
                                    ${similarity ? `<div class="card-similarity">${similarity}% match</div>` : ''}
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            `;

            container.innerHTML = html;
        }

        function goToProduct(productId) {
            const index = products.findIndex(p => p.product_id === productId);
            if (index !== -1) {
                switchTab('products');
                displayProduct(index);
            } else {
                alert('Product not found in current view. Try refreshing the page.');
            }
        }

        async function generateAllTags() {
            const btn = document.getElementById('generateAllTagsBtn');
            const progress = document.getElementById('tagProgress');
            const progressText = document.getElementById('tagProgressText');
            const results = document.getElementById('tagResults');

            if (!confirm('This will generate AI style tags for all products without tags. This may take several minutes. Continue?')) {
                return;
            }

            btn.disabled = true;
            progress.classList.add('visible');
            progressText.textContent = 'Starting...';
            results.innerHTML = '';

            try {
                const response = await fetch('/api/ai/generate-tags', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ all: true })
                });

                const data = await response.json();

                if (data.error) {
                    results.innerHTML = `<p style="color: #c62828;">❌ ${data.error}</p>`;
                } else {
                    results.innerHTML = `<p style="color: #2e7d32;">✅ Generated tags for ${data.count || 0} products!</p>`;
                    // Reload products to show new tags
                    await loadProducts();
                }
            } catch (error) {
                results.innerHTML = `<p style="color: #c62828;">❌ Error: ${error.message}</p>`;
            } finally {
                btn.disabled = false;
                progress.classList.remove('visible');
            }
        }

        async function generateTagsForCurrent() {
            if (products.length === 0 || currentIndex < 0) {
                alert('No product selected');
                return;
            }

            const product = products[currentIndex];
            const progress = document.getElementById('tagProgress');
            const progressText = document.getElementById('tagProgressText');
            const results = document.getElementById('tagResults');

            progress.classList.add('visible');
            progressText.textContent = `Analyzing ${product.name}...`;
            results.innerHTML = '';

            try {
                const response = await fetch('/api/ai/generate-tags', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ product_id: product.product_id })
                });

                const data = await response.json();

                if (data.error) {
                    results.innerHTML = `<p style="color: #c62828;">❌ ${data.error}</p>`;
                } else if (data.tags) {
                    results.innerHTML = `
                        <p style="color: #2e7d32;">✅ Generated tags for ${product.name}:</p>
                        <div class="tag-list" style="margin-top: 10px;">
                            ${data.tags.map(tag => `<span class="tag" style="background:#e3f2fd;color:#1565c0;">${tag}</span>`).join('')}
                        </div>
                    `;
                    // Reload the current product to show new tags
                    await loadProducts();
                    displayProduct(currentIndex);
                }
            } catch (error) {
                results.innerHTML = `<p style="color: #c62828;">❌ Error: ${error.message}</p>`;
            } finally {
                progress.classList.remove('visible');
            }
        }

        // Generate AI tags for a specific product (called from product page button)
        async function generateAITagsForProduct(productId) {
            const btn = document.getElementById('aiGenTagsBtn');
            const statusDiv = document.getElementById('aiTagsStatus');

            if (!btn || !statusDiv) return;

            // Set loading state
            btn.classList.add('loading');
            btn.disabled = true;
            statusDiv.innerHTML = '<span style="color: #9c27b0;">🔄 Analyzing product images with AI...</span>';

            try {
                const response = await fetch('/api/ai/generate-tags', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ product_id: productId })
                });

                const data = await response.json();

                if (data.error) {
                    statusDiv.innerHTML = `<span style="color: #c62828;">❌ ${data.error}</span>`;
                } else if (data.tags && data.tags.length > 0) {
                    statusDiv.innerHTML = `<span style="color: #2e7d32;">✅ Generated ${data.tags.length} tags successfully!</span>`;

                    // Reload products and refresh display to show new tags
                    await loadProducts();

                    // Find the current product index again (might have changed)
                    const newIndex = products.findIndex(p => p.product_id === productId);
                    if (newIndex >= 0) {
                        await displayProduct(newIndex);
                    } else {
                        await displayProduct(currentIndex);
                    }
                } else {
                    statusDiv.innerHTML = `<span style="color: #ff9800;">⚠️ No tags generated</span>`;
                }
            } catch (error) {
                console.error('Error generating AI tags:', error);
                statusDiv.innerHTML = `<span style="color: #c62828;">❌ Error: ${error.message}</span>`;
            } finally {
                // Reset button state
                btn.classList.remove('loading');
                btn.disabled = false;
            }
        }

        function handleChatKeypress(event) {
            if (event.key === 'Enter') {
                sendChatMessage();
            }
        }

        async function sendChatMessage() {
            const input = document.getElementById('chatInput');
            const message = input.value.trim();

            if (!message) return;

            input.value = '';

            const messagesContainer = document.getElementById('chatMessages');

            // Add user message to UI
            messagesContainer.innerHTML += `
                <div class="ai-chat-message user">
                    <div class="role">You</div>
                    <div>${escapeHtml(message)}</div>
                </div>
            `;

            // Add to history
            chatHistory.push({ role: 'user', content: message });

            // Add loading indicator
            messagesContainer.innerHTML += `
                <div class="ai-chat-message assistant" id="chatLoading">
                    <div class="role">Assistant</div>
                    <div><em>Thinking...</em></div>
                </div>
            `;

            messagesContainer.scrollTop = messagesContainer.scrollHeight;

            try {
                const response = await fetch('/api/ai/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ messages: chatHistory })
                });

                const data = await response.json();

                // Remove loading indicator
                document.getElementById('chatLoading')?.remove();

                if (data.error) {
                    messagesContainer.innerHTML += `
                        <div class="ai-chat-message assistant">
                            <div class="role">Assistant</div>
                            <div style="color: #c62828;">Error: ${data.error}</div>
                        </div>
                    `;
                } else {
                    const assistantMessage = data.response || 'No response';
                    chatHistory.push({ role: 'assistant', content: assistantMessage });

                    messagesContainer.innerHTML += `
                        <div class="ai-chat-message assistant">
                            <div class="role">Assistant</div>
                            <div>${formatChatResponse(assistantMessage)}</div>
                        </div>
                    `;
                }
            } catch (error) {
                document.getElementById('chatLoading')?.remove();
                messagesContainer.innerHTML += `
                    <div class="ai-chat-message assistant">
                        <div class="role">Assistant</div>
                        <div style="color: #c62828;">Error: ${error.message}</div>
                    </div>
                `;
            }

            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function formatChatResponse(text) {
            // Basic markdown-like formatting
            return text
                .replace(/\\n/g, '<br>')
                .replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>')
                .replace(/\\*(.+?)\\*/g, '<em>$1</em>');
        }

        // ============================================
        // DASHBOARD FUNCTIONALITY
        // ============================================

        async function loadDashboard() {
            const dashboardContent = document.getElementById('dashboardContent');

            if (!useSupabase) {
                dashboardContent.innerHTML = `
                    <div class="no-data">
                        <h2>Dashboard requires Supabase</h2>
                        <p>Run the viewer with <code>--supabase</code> flag to enable dashboard features.</p>
                    </div>
                `;
                return;
            }

            dashboardContent.innerHTML = '<div class="no-data"><h2>Loading dashboard...</h2></div>';

            try {
                const response = await fetch('/api/dashboard/stats');
                const stats = await response.json();

                if (stats.error) {
                    dashboardContent.innerHTML = `
                        <div class="no-data">
                            <h2>Error loading dashboard</h2>
                            <p>${stats.error}</p>
                        </div>
                    `;
                    return;
                }

                renderDashboard(stats);
            } catch (error) {
                console.error('Error loading dashboard:', error);
                dashboardContent.innerHTML = `
                    <div class="no-data">
                        <h2>Error loading dashboard</h2>
                        <p>${error.message}</p>
                    </div>
                `;
            }
        }

        function renderDashboard(stats) {
            const overview = stats.overview;
            const byCategory = stats.by_category;
            const byCurator = stats.by_curator;
            const recentActivity = stats.recent_activity;

            // Build scraper section
            const scraperHtml = `
                <div class="scraper-section">
                    <h3>🔍 Want to Scrape?</h3>
                    <p style="color: #666; margin-bottom: 15px;">Scrape new products from Zara. Already-scraped products will be skipped automatically.</p>

                    <div class="scraper-controls">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <label style="margin: 0;">Categories:</label>
                            <div style="display: flex; gap: 8px;">
                                <button type="button" onclick="selectAllCategories()" style="padding: 4px 8px; font-size: 11px; cursor: pointer; background: #4CAF50; color: white; border: none; border-radius: 4px;">Select All</button>
                                <button type="button" onclick="deselectAllCategories()" style="padding: 4px 8px; font-size: 11px; cursor: pointer; background: #f44336; color: white; border: none; border-radius: 4px;">Deselect All</button>
                            </div>
                        </div>
                        <select id="scraperCategories" multiple style="height: 150px;">
                            <optgroup label="Clothing">
                                <option value="tshirts" selected>T-Shirts</option>
                                <option value="shirts" selected>Shirts</option>
                                <option value="trousers" selected>Trousers</option>
                                <option value="jeans" selected>Jeans</option>
                                <option value="shorts" selected>Shorts</option>
                                <option value="jackets" selected>Jackets</option>
                                <option value="blazers" selected>Blazers</option>
                                <option value="suits" selected>Suits</option>
                            </optgroup>
                            <optgroup label="Footwear & Accessories">
                                <option value="shoes" selected>Shoes</option>
                                <option value="bags" selected>Bags</option>
                                <option value="accessories" selected>Accessories</option>
                                <option value="underwear" selected>Underwear</option>
                            </optgroup>
                            <optgroup label="Discovery">
                                <option value="new-in" selected>New In</option>
                            </optgroup>
                        </select>

                        <div style="margin-top: 15px; padding: 12px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e0e0e0;">
                            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
                                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; margin: 0; font-weight: 500;">
                                    <input type="checkbox" id="scrapeAllProducts" onchange="toggleAllProducts()" style="width: 18px; height: 18px; cursor: pointer;">
                                    <span>Scrape ALL products per category</span>
                                </label>
                            </div>
                            <div id="productCountContainer" style="display: flex; align-items: center; gap: 10px;">
                                <label style="margin: 0; color: #666;">Products per category:</label>
                                <input type="number" id="scraperProductCount" value="2" min="1" max="100" style="width: 70px; padding: 6px; border: 1px solid #ccc; border-radius: 4px;">
                            </div>
                            <p id="allProductsNote" style="display: none; margin: 8px 0 0 0; font-size: 12px; color: #4CAF50;">
                                ✓ Will scrape all available products (this may take a while)
                            </p>
                        </div>
                    </div>

                    <button class="go-btn" id="scraperGoBtn" onclick="startScraper()">🚀 GO</button>

                    <div class="progress-container" id="scraperProgress">
                        <div class="progress-status" id="progressStatus">Starting scraper...</div>
                        <div class="progress-bar-wrapper">
                            <div class="progress-bar" id="progressBar"></div>
                        </div>
                        <div class="progress-text" id="progressText">0 products processed</div>
                        <div class="progress-details" id="progressDetails"></div>

                        <button class="log-toggle" id="logToggle" onclick="toggleLogViewer()">📋 Show Logs</button>
                        <div class="log-viewer" id="logViewer"></div>
                    </div>
                </div>
            `;

            // Build stat cards
            const statCardsHtml = `
                <div class="dashboard-grid">
                    <div class="stat-card">
                        <div class="stat-value">${overview.total_products}</div>
                        <div class="stat-label">Total Products</div>
                    </div>
                    <div class="stat-card success">
                        <div class="stat-value">${overview.curated_products}</div>
                        <div class="stat-label">Curated Complete</div>
                    </div>
                    <div class="stat-card warning">
                        <div class="stat-value">${overview.pending_products}</div>
                        <div class="stat-label">Pending Curation</div>
                    </div>
                    <div class="stat-card info">
                        <div class="stat-value">${overview.percent_complete}%</div>
                        <div class="stat-label">Progress</div>
                    </div>
                </div>

                <div class="dashboard-grid">
                    <div class="stat-card">
                        <div class="stat-value">${overview.total_curated_tags}</div>
                        <div class="stat-label">Tags Added by Curators</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${overview.total_rejected_tags}</div>
                        <div class="stat-label">Inferred Tags Rejected</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${Object.keys(byCategory).length}</div>
                        <div class="stat-label">Categories</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${Object.keys(byCurator).length}</div>
                        <div class="stat-label">Active Curators</div>
                    </div>
                </div>
            `;

            // Build recent activity
            let activityHtml = '';
            if (recentActivity.length > 0) {
                const activityItems = recentActivity.map(item => {
                    const colorInfo = curatorColors[item.curator] || { bg: '#999' };
                    const date = new Date(item.created_at).toLocaleDateString();
                    return `
                        <div class="activity-item">
                            <span class="activity-product">${item.product_id}</span>
                            <span class="activity-curator" style="background: ${colorInfo.bg};">${item.curator}</span>
                            <span class="activity-time">${date}</span>
                        </div>
                    `;
                }).join('');

                activityHtml = `
                    <div class="activity-list">
                        <h3 class="chart-title">Recent Curation Activity</h3>
                        ${activityItems}
                    </div>
                `;
            }

            // Render HTML
            document.getElementById('dashboardContent').innerHTML = `
                ${scraperHtml}

                ${statCardsHtml}

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                    <div class="chart-container">
                        <h3 class="chart-title">Curation Progress by Category</h3>
                        <div id="categoryChart"></div>
                    </div>
                    <div class="chart-container">
                        <h3 class="chart-title">Curator Activity</h3>
                        <div id="curatorChart"></div>
                    </div>
                </div>

                <div class="chart-container">
                    <h3 class="chart-title">Overall Progress</h3>
                    <div id="progressChart"></div>
                </div>

                ${activityHtml}
            `;

            // Render Plotly charts
            renderCategoryChart(byCategory);
            renderCuratorChart(byCurator);
            renderProgressChart(overview);

            // Check if scraper is already running
            checkScraperStatus();
        }

        // ============================================
        // SCRAPER FUNCTIONALITY
        // ============================================

        let scraperPollingInterval = null;

        // Select all categories
        function selectAllCategories() {
            const select = document.getElementById('scraperCategories');
            for (let option of select.options) {
                option.selected = true;
            }
        }

        // Deselect all categories
        function deselectAllCategories() {
            const select = document.getElementById('scraperCategories');
            for (let option of select.options) {
                option.selected = false;
            }
        }

        // Toggle "all products" mode
        function toggleAllProducts() {
            const checkbox = document.getElementById('scrapeAllProducts');
            const countContainer = document.getElementById('productCountContainer');
            const allNote = document.getElementById('allProductsNote');
            const countInput = document.getElementById('scraperProductCount');

            if (checkbox.checked) {
                countContainer.style.opacity = '0.5';
                countInput.disabled = true;
                allNote.style.display = 'block';
            } else {
                countContainer.style.opacity = '1';
                countInput.disabled = false;
                allNote.style.display = 'none';
            }
        }

        async function startScraper() {
            const categoriesSelect = document.getElementById('scraperCategories');
            const productCountInput = document.getElementById('scraperProductCount');
            const scrapeAllCheckbox = document.getElementById('scrapeAllProducts');
            const goBtn = document.getElementById('scraperGoBtn');

            // Get selected categories
            const selectedCategories = Array.from(categoriesSelect.selectedOptions).map(opt => opt.value);

            // If "scrape all" is checked, use a high number (9999), otherwise use the input value
            const productsPerCategory = scrapeAllCheckbox.checked ? 9999 : (parseInt(productCountInput.value) || 2);

            if (selectedCategories.length === 0) {
                alert('Please select at least one category');
                return;
            }

            // Disable button
            goBtn.disabled = true;
            goBtn.textContent = '⏳ Starting...';

            try {
                const response = await fetch('/api/scraper/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        categories: selectedCategories,
                        products_per_category: productsPerCategory
                    })
                });

                const result = await response.json();
                if (result.success) {
                    // Show progress container
                    document.getElementById('scraperProgress').classList.add('visible');
                    goBtn.textContent = '🔄 Scraping...';

                    // Start polling for status
                    startScraperPolling();
                } else {
                    alert('Failed to start scraper: ' + result.error);
                    goBtn.disabled = false;
                    goBtn.textContent = '🚀 GO';
                }
            } catch (error) {
                console.error('Error starting scraper:', error);
                alert('Error starting scraper');
                goBtn.disabled = false;
                goBtn.textContent = '🚀 GO';
            }
        }

        function startScraperPolling() {
            // Clear any existing interval
            if (scraperPollingInterval) {
                clearInterval(scraperPollingInterval);
            }

            // Poll every second
            scraperPollingInterval = setInterval(checkScraperStatus, 1000);
        }

        async function checkScraperStatus() {
            try {
                const response = await fetch('/api/scraper/status');
                const status = await response.json();

                const progressContainer = document.getElementById('scraperProgress');
                const progressBar = document.getElementById('progressBar');
                const progressStatus = document.getElementById('progressStatus');
                const progressText = document.getElementById('progressText');
                const progressDetails = document.getElementById('progressDetails');
                const goBtn = document.getElementById('scraperGoBtn');
                const logViewer = document.getElementById('logViewer');

                // Don't update if elements don't exist (not on dashboard tab)
                if (!progressContainer) return;

                // Update log viewer
                if (logViewer && status.logs && status.logs.length > 0) {
                    logViewer.innerHTML = status.logs.map(line => {
                        let lineClass = 'log-line';
                        if (line.startsWith('$')) lineClass += ' command';
                        else if (line.includes('❌') || line.includes('Error') || line.includes('error')) lineClass += ' error';
                        else if (line.includes('✅') || line.includes('✓')) lineClass += ' success';
                        else if (line.includes('⏭️') || line.includes('Skipping')) lineClass += ' warning';
                        else if (line.includes('Processing') || line.includes('Extracting')) lineClass += ' info';
                        return `<div class="${lineClass}">${line}</div>`;
                    }).join('');
                    // Auto-scroll to bottom
                    logViewer.scrollTop = logViewer.scrollHeight;
                }

                if (status.running) {
                    progressContainer.classList.add('visible');
                    goBtn.disabled = true;
                    goBtn.textContent = '🔄 Scraping...';

                    // Update progress bar
                    const total = status.total || 1;
                    const progress = status.progress || 0;
                    const percent = Math.min((progress / total) * 100, 100);
                    progressBar.style.width = percent + '%';

                    // Update status text
                    progressStatus.textContent = `Category: ${status.current_category || 'Starting...'}`;
                    progressText.textContent = `${status.products_scraped} scraped, ${status.products_skipped} skipped`;
                    if (status.current_product) {
                        progressDetails.textContent = `Current: ${status.current_product}`;
                    }
                } else if (status.completed && !status.refresh_handled) {
                    // Scraping completed - only refresh once
                    clearInterval(scraperPollingInterval);
                    scraperPollingInterval = null;

                    progressBar.style.width = '100%';
                    progressStatus.textContent = '✅ Scraping Complete!';
                    progressText.textContent = `${status.products_scraped} new products scraped, ${status.products_skipped} skipped`;
                    progressDetails.textContent = 'Refreshing dashboard...';

                    goBtn.disabled = false;
                    goBtn.textContent = '🚀 GO';

                    // Mark refresh as handled to prevent loops
                    fetch('/api/scraper/reset', { method: 'POST' });

                    // Auto-refresh after 2 seconds
                    setTimeout(() => {
                        // Reload products
                        loadProducts();
                        // Reload dashboard stats only (not full reload to avoid loop)
                        refreshDashboardStats();
                        progressDetails.textContent = 'Dashboard updated!';
                    }, 2000);
                } else if (status.completed && status.refresh_handled) {
                    // Already handled, just show completed state
                    progressContainer.classList.add('visible');
                    progressBar.style.width = '100%';
                    progressStatus.textContent = '✅ Scraping Complete!';
                    progressText.textContent = `${status.products_scraped} new products scraped, ${status.products_skipped} skipped`;
                    progressDetails.textContent = 'Dashboard updated!';
                    goBtn.disabled = false;
                    goBtn.textContent = '🚀 GO';
                } else if (status.error) {
                    // Error occurred
                    clearInterval(scraperPollingInterval);
                    scraperPollingInterval = null;

                    progressStatus.textContent = '❌ Error';
                    progressText.textContent = status.error;
                    progressDetails.textContent = 'Check logs for details';

                    // Auto-show logs on error
                    if (logViewer) {
                        logViewer.classList.add('visible');
                        const logToggle = document.getElementById('logToggle');
                        if (logToggle) logToggle.textContent = '📋 Hide Logs';
                    }

                    goBtn.disabled = false;
                    goBtn.textContent = '🚀 GO';
                } else {
                    // Not running, hide progress
                    progressContainer.classList.remove('visible');
                    goBtn.disabled = false;
                    goBtn.textContent = '🚀 GO';
                }
            } catch (error) {
                console.error('Error checking scraper status:', error);
            }
        }

        function toggleLogViewer() {
            const logViewer = document.getElementById('logViewer');
            const logToggle = document.getElementById('logToggle');

            if (logViewer.classList.contains('visible')) {
                logViewer.classList.remove('visible');
                logToggle.textContent = '📋 Show Logs';
            } else {
                logViewer.classList.add('visible');
                logToggle.textContent = '📋 Hide Logs';
            }
        }

        async function refreshDashboardStats() {
            // Refresh only the statistics without re-rendering the scraper section
            // This prevents the refresh loop issue
            try {
                const response = await fetch('/api/dashboard/stats');
                const stats = await response.json();

                if (stats.error) {
                    console.error('Error refreshing stats:', stats.error);
                    return;
                }

                // Just update the stat card values
                const overview = stats.overview;

                // Find and update stat cards by their labels
                const statCards = document.querySelectorAll('.stat-card');
                statCards.forEach(card => {
                    const label = card.querySelector('.stat-label');
                    const value = card.querySelector('.stat-value');
                    if (!label || !value) return;

                    const labelText = label.textContent.toLowerCase();
                    if (labelText.includes('total products')) {
                        value.textContent = overview.total_products;
                    } else if (labelText.includes('curated complete')) {
                        value.textContent = overview.curated_products;
                    } else if (labelText.includes('pending')) {
                        value.textContent = overview.pending_products;
                    } else if (labelText.includes('progress')) {
                        value.textContent = overview.percent_complete + '%';
                    } else if (labelText.includes('tags added')) {
                        value.textContent = overview.total_curated_tags;
                    } else if (labelText.includes('tags rejected')) {
                        value.textContent = overview.total_rejected_tags;
                    }
                });

                // Update charts
                renderCategoryChart(stats.by_category);
                renderCuratorChart(stats.by_curator);
                renderProgressChart(overview);

                console.log('Dashboard stats refreshed');
            } catch (error) {
                console.error('Error refreshing dashboard stats:', error);
            }
        }

        function renderCategoryChart(byCategory) {
            const categories = Object.keys(byCategory);

            // Build stacked bars by curator instead of generic "Curated"
            const allCurators = ['Reed', 'Gigi', 'Kiki'];
            const curatorTraces = [];

            // Create a trace for each curator
            allCurators.forEach(curator => {
                const colorInfo = curatorColors[curator];
                const values = categories.map(cat => {
                    const byCurator = byCategory[cat].by_curator || {};
                    return byCurator[curator] || 0;
                });

                // Only add trace if this curator has any data
                if (values.some(v => v > 0)) {
                    curatorTraces.push({
                        x: categories,
                        y: values,
                        name: curator,
                        type: 'bar',
                        marker: { color: colorInfo ? colorInfo.bg : '#999' }
                    });
                }
            });

            // Add pending trace
            const pending = categories.map(c => byCategory[c].pending);
            curatorTraces.push({
                x: categories,
                y: pending,
                name: 'Pending',
                type: 'bar',
                marker: { color: '#ff9800' }
            });

            const layout = {
                barmode: 'stack',
                margin: { t: 20, r: 20, b: 60, l: 40 },
                legend: { orientation: 'h', y: -0.2 },
                xaxis: { tickangle: -45 }
            };

            Plotly.newPlot('categoryChart', curatorTraces, layout, { responsive: true });
        }

        function renderCuratorChart(byCurator) {
            const curators = Object.keys(byCurator);

            if (curators.length === 0) {
                document.getElementById('curatorChart').innerHTML = '<p style="color:#999;text-align:center;padding:40px;">No curator activity yet</p>';
                return;
            }

            // Get curator colors to match the rest of the UI
            const curatorBarColors = curators.map(c => {
                const colorInfo = curatorColors[c];
                return colorInfo ? colorInfo.bg : '#999';
            });

            const data = [
                {
                    x: curators,
                    y: curators.map(c => byCurator[c].completed),
                    name: 'Products Completed',
                    type: 'bar',
                    marker: { color: curatorBarColors }
                },
                {
                    x: curators,
                    y: curators.map(c => byCurator[c].tags_added),
                    name: 'Tags Added',
                    type: 'bar',
                    marker: { color: curatorBarColors.map(c => c + '99') }  // Slightly transparent
                },
                {
                    x: curators,
                    y: curators.map(c => byCurator[c].tags_rejected),
                    name: 'Tags Rejected',
                    type: 'bar',
                    marker: { color: curatorBarColors.map(c => c + '66') }  // More transparent
                }
            ];

            const layout = {
                barmode: 'group',
                margin: { t: 20, r: 20, b: 40, l: 40 },
                legend: { orientation: 'h', y: -0.15 }
            };

            Plotly.newPlot('curatorChart', data, layout, { responsive: true });
        }

        function renderProgressChart(overview) {
            // Build values, labels, and colors arrays based on curated_by_curator
            const values = [];
            const labels = [];
            const colors = [];

            // Add curator-specific slices if curated_by_curator data is available
            if (overview.curated_by_curator) {
                const allCurators = ['Reed', 'Gigi', 'Kiki'];
                allCurators.forEach(curator => {
                    const count = overview.curated_by_curator[curator] || 0;
                    if (count > 0) {
                        values.push(count);
                        labels.push(`${curator} Curated`);
                        const colorInfo = curatorColors[curator];
                        colors.push(colorInfo ? colorInfo.bg : '#999');
                    }
                });
            } else if (overview.curated_products > 0) {
                // Fallback if no curator breakdown available
                values.push(overview.curated_products);
                labels.push('Curated');
                colors.push('#4CAF50');
            }

            // Add pending products
            if (overview.pending_products > 0) {
                values.push(overview.pending_products);
                labels.push('Pending');
                colors.push('#ff9800');
            }

            const data = [{
                values: values,
                labels: labels,
                type: 'pie',
                hole: 0.6,
                marker: {
                    colors: colors
                },
                textinfo: 'label+percent',
                textposition: 'outside'
            }];

            const layout = {
                margin: { t: 20, r: 20, b: 20, l: 20 },
                showlegend: false,
                annotations: [{
                    text: `${overview.percent_complete}%`,
                    showarrow: false,
                    font: { size: 32, weight: 'bold' }
                }]
            };

            Plotly.newPlot('progressChart', data, layout, { responsive: true });
        }

        // ============================================
        // MARK AS COMPLETE FUNCTIONALITY
        // ============================================

        async function markProductComplete() {
            if (!curateMode || !currentCurator) {
                alert('Please enter curate mode first.');
                return;
            }

            const product = products[currentIndex];
            const notes = prompt('Optional notes about this curation:', '');

            if (notes === null) return; // User cancelled

            try {
                const response = await fetch('/api/curation_status', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        product_id: product.product_id,
                        curator: currentCurator,
                        notes: notes || null
                    })
                });

                const result = await response.json();
                if (result.success) {
                    console.log(`✓ Marked product ${product.product_id} as complete`);
                    await displayProduct(currentIndex);
                    showCurateInputs();
                } else {
                    alert('Failed to mark as complete: ' + result.error);
                }
            } catch (error) {
                console.error('Error marking complete:', error);
                alert('Error marking product as complete');
            }
        }

        async function unmarkProductComplete() {
            if (!curateMode || !currentCurator) {
                alert('Please enter curate mode first.');
                return;
            }

            const product = products[currentIndex];

            if (!confirm('Remove completion status from this product?')) {
                return;
            }

            try {
                const response = await fetch('/api/curation_status', {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        product_id: product.product_id
                    })
                });

                const result = await response.json();
                if (result.success) {
                    console.log(`✓ Unmarked product ${product.product_id}`);
                    await displayProduct(currentIndex);
                    showCurateInputs();
                } else {
                    alert('Failed to unmark: ' + result.error);
                }
            } catch (error) {
                console.error('Error unmarking:', error);
                alert('Error removing completion status');
            }
        }
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    """Serve the main viewer page."""
    supabase_url = os.getenv("SUPABASE_URL", "")
    return render_template_string(
        HTML_TEMPLATE, use_supabase=USE_SUPABASE, supabase_url=supabase_url
    )


@app.route("/api/products")
def api_products():
    """API endpoint to get all products."""
    products = get_all_products()
    return jsonify(products)


@app.route("/api/products/<product_id>", methods=["DELETE"])
def delete_product(product_id):
    """Delete a product from the database and storage."""
    if not USE_SUPABASE or not supabase_client:
        return (
            jsonify(
                {"error": "Supabase not configured. Deletion only works with Supabase."}
            ),
            400,
        )

    try:
        # First, get the product to find its image paths
        product_result = (
            supabase_client.table("products")
            .select("image_paths, name")
            .eq("product_id", product_id)
            .execute()
        )

        if not product_result.data:
            return jsonify({"error": "Product not found"}), 404

        product = product_result.data[0]
        image_paths = product.get("image_paths", [])
        images_deleted = 0

        # Delete images from storage
        if image_paths:
            try:
                supabase_client.storage.from_(BUCKET_NAME).remove(image_paths)
                images_deleted = len(image_paths)
            except Exception as e:
                print(f"Warning: Could not delete some images: {e}")

        # Delete from curated_metadata table (if exists)
        try:
            supabase_client.table("curated_metadata").delete().eq(
                "product_id", product_id
            ).execute()
        except Exception:
            pass  # Table may not exist

        # Delete from curation_status table (if exists)
        try:
            supabase_client.table("curation_status").delete().eq(
                "product_id", product_id
            ).execute()
        except Exception:
            pass  # Table may not exist

        # Delete from rejected_tags table (if exists)
        try:
            supabase_client.table("rejected_tags").delete().eq(
                "product_id", product_id
            ).execute()
        except Exception:
            pass  # Table may not exist

        # Delete from ai_generated_tags table (if exists)
        try:
            supabase_client.table("ai_generated_tags").delete().eq(
                "product_id", product_id
            ).execute()
        except Exception:
            pass  # Table may not exist

        # Delete the product itself
        supabase_client.table("products").delete().eq(
            "product_id", product_id
        ).execute()

        # Also remove from local tracking database
        try:
            from src.tracking import ProductTracker

            tracker = ProductTracker()
            tracker.remove_product(product_id)
        except Exception as e:
            print(f"Warning: Could not remove from tracking DB: {e}")

        return jsonify(
            {
                "success": True,
                "message": f"Product {product_id} deleted successfully",
                "images_deleted": images_deleted,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/curated", methods=["POST"])
def save_curated_metadata():
    """Save a curated metadata entry to the database."""
    if not USE_SUPABASE or not supabase_client:
        return jsonify({"error": "Supabase not configured"}), 400

    from flask import request

    data = request.get_json()
    product_id = data.get("product_id")
    field_name = data.get("field_name")
    field_value = data.get("field_value")
    curator = data.get("curator")

    if not all([product_id, field_name, field_value, curator]):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        result = (
            supabase_client.table("curated_metadata")
            .insert(
                {
                    "product_id": product_id,
                    "field_name": field_name,
                    "field_value": field_value,
                    "curator": curator,
                }
            )
            .execute()
        )
        return jsonify({"success": True, "data": result.data})
    except Exception as e:
        # Handle duplicate entries gracefully
        if "duplicate" in str(e).lower():
            return jsonify({"success": True, "message": "Already exists"})
        return jsonify({"error": str(e)}), 500


@app.route("/api/curated/<product_id>")
def get_curated_metadata(product_id):
    """Get all curated metadata for a product."""
    if not USE_SUPABASE or not supabase_client:
        return jsonify([])

    try:
        result = (
            supabase_client.table("curated_metadata")
            .select("*")
            .eq("product_id", product_id)
            .execute()
        )
        return jsonify(result.data or [])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/curated", methods=["DELETE"])
def delete_curated_metadata():
    """Delete a curated metadata entry from the database."""
    if not USE_SUPABASE or not supabase_client:
        return jsonify({"error": "Supabase not configured"}), 400

    data = request.get_json()
    product_id = data.get("product_id")
    field_name = data.get("field_name")
    field_value = data.get("field_value")
    curator = data.get("curator")

    if not all([product_id, field_name, field_value, curator]):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        result = (
            supabase_client.table("curated_metadata")
            .delete()
            .eq("product_id", product_id)
            .eq("field_name", field_name)
            .eq("field_value", field_value)
            .eq("curator", curator)
            .execute()
        )
        return jsonify({"success": True, "data": result.data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/rejected_tags", methods=["POST"])
def reject_inferred_tag():
    """Mark an inferred tag as rejected (incorrect). Saved for ML training."""
    if not USE_SUPABASE or not supabase_client:
        return jsonify({"error": "Supabase not configured"}), 400

    data = request.get_json()
    product_id = data.get("product_id")
    field_name = data.get("field_name")
    field_value = data.get("field_value")
    original_reasoning = data.get("original_reasoning")
    curator = data.get("curator")
    rejection_reason = data.get("rejection_reason")

    if not all([product_id, field_name, field_value, curator]):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        result = (
            supabase_client.table("rejected_inferred_tags")
            .insert(
                {
                    "product_id": product_id,
                    "field_name": field_name,
                    "field_value": field_value,
                    "original_reasoning": original_reasoning,
                    "curator": curator,
                    "rejection_reason": rejection_reason,
                }
            )
            .execute()
        )
        return jsonify({"success": True, "data": result.data})
    except Exception as e:
        # Handle duplicate entries gracefully
        if "duplicate" in str(e).lower():
            return jsonify({"success": True, "message": "Already rejected"})
        return jsonify({"error": str(e)}), 500


@app.route("/api/rejected_tags/<product_id>")
def get_rejected_tags(product_id):
    """Get all rejected inferred tags for a product."""
    if not USE_SUPABASE or not supabase_client:
        return jsonify([])

    try:
        result = (
            supabase_client.table("rejected_inferred_tags")
            .select("*")
            .eq("product_id", product_id)
            .execute()
        )
        return jsonify(result.data or [])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/rejected_tags", methods=["DELETE"])
def unreject_inferred_tag():
    """Remove a tag from the rejected list (undo rejection)."""
    if not USE_SUPABASE or not supabase_client:
        return jsonify({"error": "Supabase not configured"}), 400

    data = request.get_json()
    product_id = data.get("product_id")
    field_name = data.get("field_name")
    field_value = data.get("field_value")

    if not all([product_id, field_name, field_value]):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        result = (
            supabase_client.table("rejected_inferred_tags")
            .delete()
            .eq("product_id", product_id)
            .eq("field_name", field_name)
            .eq("field_value", field_value)
            .execute()
        )
        return jsonify({"success": True, "data": result.data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================
# AI GENERATED TAGS ENDPOINTS
# ============================================


@app.route("/api/ai_tags/<product_id>")
def get_ai_generated_tags(product_id):
    """Get all AI-generated tags for a product."""
    if not USE_SUPABASE or not supabase_client:
        return jsonify([])

    try:
        result = (
            supabase_client.table("ai_generated_tags")
            .select("*")
            .eq("product_id", product_id)
            .execute()
        )
        return jsonify(result.data or [])
    except Exception as e:
        # Table might not exist yet
        print(f"Error fetching AI tags: {e}")
        return jsonify([])


@app.route("/api/ai_tags", methods=["POST"])
def save_ai_generated_tag():
    """Save an AI-generated tag to the database."""
    if not USE_SUPABASE or not supabase_client:
        return jsonify({"error": "Supabase not configured"}), 400

    data = request.get_json()
    product_id = data.get("product_id")
    field_name = data.get("field_name", "style_tag")
    field_value = data.get("field_value")
    model_name = data.get("model_name", "moondream")
    reasoning = data.get("reasoning")

    if not all([product_id, field_value]):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        result = (
            supabase_client.table("ai_generated_tags")
            .upsert(
                {
                    "product_id": product_id,
                    "field_name": field_name,
                    "field_value": field_value,
                    "model_name": model_name,
                    "reasoning": reasoning,
                },
                on_conflict="product_id,field_name,field_value",
            )
            .execute()
        )
        return jsonify({"success": True, "data": result.data})
    except Exception as e:
        # Handle duplicate entries gracefully
        if "duplicate" in str(e).lower():
            return jsonify({"success": True, "message": "Already exists"})
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai_tags", methods=["DELETE"])
def delete_ai_generated_tag():
    """Delete an AI-generated tag from the database."""
    if not USE_SUPABASE or not supabase_client:
        return jsonify({"error": "Supabase not configured"}), 400

    data = request.get_json()
    product_id = data.get("product_id")
    field_name = data.get("field_name")
    field_value = data.get("field_value")

    if not all([product_id, field_name, field_value]):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        result = (
            supabase_client.table("ai_generated_tags")
            .delete()
            .eq("product_id", product_id)
            .eq("field_name", field_name)
            .eq("field_value", field_value)
            .execute()
        )
        return jsonify({"success": True, "data": result.data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai_tags/batch", methods=["POST"])
def save_ai_generated_tags_batch():
    """Save multiple AI-generated tags for a product at once."""
    if not USE_SUPABASE or not supabase_client:
        return jsonify({"error": "Supabase not configured"}), 400

    data = request.get_json()
    product_id = data.get("product_id")
    tags = data.get("tags", [])
    model_name = data.get("model_name", "moondream")

    if not product_id or not tags:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        # Prepare batch insert data
        records = [
            {
                "product_id": product_id,
                "field_name": "style_tag",
                "field_value": tag,
                "model_name": model_name,
            }
            for tag in tags
        ]

        result = (
            supabase_client.table("ai_generated_tags")
            .upsert(records, on_conflict="product_id,field_name,field_value")
            .execute()
        )
        return jsonify({"success": True, "count": len(tags), "data": result.data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================
# CURATION STATUS ENDPOINTS
# ============================================


@app.route("/api/curation_status/<product_id>")
def get_curation_status(product_id):
    """Get curation status for a product."""
    if not USE_SUPABASE or not supabase_client:
        return jsonify(None)

    try:
        result = (
            supabase_client.table("curation_status")
            .select("*")
            .eq("product_id", product_id)
            .execute()
        )
        if result.data and len(result.data) > 0:
            return jsonify(result.data[0])
        return jsonify(None)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/curation_status", methods=["POST"])
def mark_product_curated():
    """Mark a product as fully curated/complete."""
    if not USE_SUPABASE or not supabase_client:
        return jsonify({"error": "Supabase not configured"}), 400

    data = request.get_json()
    product_id = data.get("product_id")
    curator = data.get("curator")
    notes = data.get("notes")

    if not all([product_id, curator]):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        # Upsert - insert or update if exists
        result = (
            supabase_client.table("curation_status")
            .upsert(
                {
                    "product_id": product_id,
                    "curator": curator,
                    "status": "complete",
                    "notes": notes,
                    "updated_at": "now()",
                },
                on_conflict="product_id",
            )
            .execute()
        )
        return jsonify({"success": True, "data": result.data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/curation_status", methods=["DELETE"])
def unmark_product_curated():
    """Remove curation status from a product (mark as incomplete)."""
    if not USE_SUPABASE or not supabase_client:
        return jsonify({"error": "Supabase not configured"}), 400

    data = request.get_json()
    product_id = data.get("product_id")

    if not product_id:
        return jsonify({"error": "Missing product_id"}), 400

    try:
        result = (
            supabase_client.table("curation_status")
            .delete()
            .eq("product_id", product_id)
            .execute()
        )
        return jsonify({"success": True, "data": result.data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================
# DASHBOARD STATISTICS ENDPOINTS
# ============================================


@app.route("/api/dashboard/stats")
def get_dashboard_stats():
    """Get comprehensive dashboard statistics."""
    if not USE_SUPABASE or not supabase_client:
        return jsonify({"error": "Supabase not configured"}), 400

    try:
        # Get all products
        products_result = supabase_client.table("products").select("*").execute()
        products = products_result.data or []

        # Get curation statuses
        curation_result = supabase_client.table("curation_status").select("*").execute()
        curation_data = curation_result.data or []
        curated_ids = {c["product_id"]: c["curator"] for c in curation_data}

        # Get curated metadata counts
        curated_meta_result = (
            supabase_client.table("curated_metadata").select("*").execute()
        )
        curated_metadata = curated_meta_result.data or []

        # Get rejected tags counts
        rejected_result = (
            supabase_client.table("rejected_inferred_tags").select("*").execute()
        )
        rejected_tags = rejected_result.data or []

        # Calculate statistics
        total_products = len(products)
        curated_products = len(curated_ids)
        pending_products = total_products - curated_products

        # Category breakdown with curator info
        category_stats = {}
        for p in products:
            cat = p.get("category", "Unknown")
            if cat not in category_stats:
                category_stats[cat] = {
                    "total": 0,
                    "curated": 0,
                    "pending": 0,
                    "by_curator": {},
                }
            category_stats[cat]["total"] += 1
            if p["product_id"] in curated_ids:
                category_stats[cat]["curated"] += 1
                curator = curated_ids[p["product_id"]]
                if curator not in category_stats[cat]["by_curator"]:
                    category_stats[cat]["by_curator"][curator] = 0
                category_stats[cat]["by_curator"][curator] += 1
            else:
                category_stats[cat]["pending"] += 1

        # Curator activity
        curator_stats = {}
        for c in curation_data:
            curator = c.get("curator", "Unknown")
            if curator not in curator_stats:
                curator_stats[curator] = {
                    "completed": 0,
                    "tags_added": 0,
                    "tags_rejected": 0,
                }
            curator_stats[curator]["completed"] += 1

        for cm in curated_metadata:
            curator = cm.get("curator", "Unknown")
            if curator not in curator_stats:
                curator_stats[curator] = {
                    "completed": 0,
                    "tags_added": 0,
                    "tags_rejected": 0,
                }
            curator_stats[curator]["tags_added"] += 1

        for rt in rejected_tags:
            curator = rt.get("curator", "Unknown")
            if curator not in curator_stats:
                curator_stats[curator] = {
                    "completed": 0,
                    "tags_added": 0,
                    "tags_rejected": 0,
                }
            curator_stats[curator]["tags_rejected"] += 1

        # Curated by curator breakdown for pie chart
        curated_by_curator = {}
        for c in curation_data:
            curator = c.get("curator", "Unknown")
            if curator not in curated_by_curator:
                curated_by_curator[curator] = 0
            curated_by_curator[curator] += 1

        # Recent activity (last 10 curated products)
        recent_curation = sorted(
            curation_data,
            key=lambda x: x.get("created_at", ""),
            reverse=True,
        )[:10]

        return jsonify(
            {
                "overview": {
                    "total_products": total_products,
                    "curated_products": curated_products,
                    "pending_products": pending_products,
                    "percent_complete": (
                        round(curated_products / total_products * 100, 1)
                        if total_products > 0
                        else 0
                    ),
                    "total_curated_tags": len(curated_metadata),
                    "total_rejected_tags": len(rejected_tags),
                    "curated_by_curator": curated_by_curator,
                },
                "by_category": category_stats,
                "by_curator": curator_stats,
                "recent_activity": recent_curation,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================
# AI ENDPOINTS
# ============================================

# Global AI clients (initialized lazily)
ai_ollama_client = None


def get_ai_client():
    """Get or create the Ollama client."""
    global ai_ollama_client
    if ai_ollama_client is None:
        try:
            from src.ai import OllamaClient

            ai_ollama_client = OllamaClient()
        except ImportError as e:
            print(f"Could not import AI modules: {e}")
            return None
    return ai_ollama_client


@app.route("/api/ai/status")
def ai_status():
    """Check if AI service (Ollama) is available."""
    import asyncio

    try:
        from src.ai import OllamaClient

        async def check():
            async with OllamaClient() as client:
                available = await client.is_available()
                models = await client.list_models() if available else []
                return {"available": available, "models": models}

        result = asyncio.run(check())
        return jsonify(result)
    except Exception as e:
        return jsonify({"available": False, "error": str(e)})


@app.route("/api/ai/search", methods=["POST"])
def ai_search():
    """Semantic search for products using AI embeddings."""
    import asyncio

    if not USE_SUPABASE or not supabase_client:
        return jsonify({"error": "Supabase not configured"}), 400

    data = request.get_json() or {}
    query = data.get("query", "")
    limit = data.get("limit", 10)

    if not query:
        return jsonify({"error": "Query is required"}), 400

    try:
        from src.ai import EmbeddingsService, OllamaClient

        async def search():
            async with OllamaClient() as client:
                if not await client.is_available():
                    return {"error": "Ollama is not running. Start with: ollama serve"}

                embeddings_service = EmbeddingsService(
                    supabase_client=supabase_client,
                    ollama_client=client,
                )

                # Generate query embedding
                query_embedding = await embeddings_service.embed_text(query)

                if not query_embedding:
                    return {"error": "Failed to generate query embedding"}

                # Get all products and calculate similarity in memory
                # (until pgvector is set up in Supabase)
                products_result = (
                    supabase_client.table("products").select("*").execute()
                )
                products = products_result.data or []

                if not products:
                    return {"results": [], "message": "No products in database"}

                # Generate embeddings for products without them and calculate similarity
                results = []
                for product in products:
                    # Build text for embedding
                    text_parts = [product.get("name", "")]
                    if product.get("description"):
                        text_parts.append(product["description"][:300])
                    if product.get("category"):
                        text_parts.append(product["category"])
                    if product.get("colors"):
                        colors = product["colors"]
                        if isinstance(colors, list):
                            text_parts.append(" ".join(colors))

                    product_text = " ".join(text_parts)
                    product_embedding = await embeddings_service.embed_text(
                        product_text
                    )

                    if product_embedding:
                        similarity = embeddings_service._cosine_similarity(
                            query_embedding, product_embedding
                        )

                        if similarity > 0.3:  # Minimum threshold
                            # Build image URLs
                            image_paths = product.get("image_paths", [])
                            supabase_url = (
                                os.getenv("SUPABASE_URL") or DEFAULT_SUPABASE_URL
                            )
                            image_urls = (
                                [
                                    f"{supabase_url}/storage/v1/object/public/{BUCKET_NAME}/{path}"
                                    for path in image_paths
                                ]
                                if image_paths
                                else []
                            )

                            results.append(
                                {
                                    "product_id": product.get("product_id"),
                                    "name": product.get("name"),
                                    "price": f"${product.get('price_current', 'N/A')}",
                                    "category": product.get("category"),
                                    "image_urls": image_urls,
                                    "primary_image": (
                                        image_urls[0] if image_urls else None
                                    ),
                                    "similarity": similarity,
                                }
                            )

                # Sort by similarity and limit
                results.sort(key=lambda x: x["similarity"], reverse=True)
                return {"results": results[:limit]}

        result = asyncio.run(search())
        return jsonify(result)

    except ImportError as e:
        return jsonify({"error": f"AI modules not available: {e}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai/generate-tags", methods=["POST"])
def ai_generate_tags():
    """Generate style tags for products using AI vision."""
    import asyncio

    if not USE_SUPABASE or not supabase_client:
        return jsonify({"error": "Supabase not configured"}), 400

    data = request.get_json() or {}
    product_id = data.get("product_id")
    generate_all = data.get("all", False)

    try:
        from src.ai import OllamaClient, StyleTagger

        async def generate():
            async with OllamaClient() as client:
                if not await client.is_available():
                    return {"error": "Ollama is not running. Start with: ollama serve"}

                tagger = StyleTagger(ollama_client=client)

                if product_id:
                    # Generate tags for a single product
                    product_result = (
                        supabase_client.table("products")
                        .select("*")
                        .eq("product_id", product_id)
                        .execute()
                    )

                    if not product_result.data:
                        return {"error": f"Product {product_id} not found"}

                    product = product_result.data[0]

                    # Get image URL
                    image_paths = product.get("image_paths", [])
                    supabase_url = os.getenv("SUPABASE_URL") or DEFAULT_SUPABASE_URL
                    image_url = (
                        f"{supabase_url}/storage/v1/object/public/{BUCKET_NAME}/{image_paths[0]}"
                        if image_paths
                        else None
                    )

                    if not image_url:
                        return {"error": "Product has no images"}

                    tags = await tagger.generate_tags(
                        image_url=image_url,
                        product_name=product.get("name", ""),
                        product_description=product.get("description", ""),
                    )

                    # Save tags to ai_generated_tags table (separate from inferred/curated)
                    if tags:
                        records = [
                            {
                                "product_id": product_id,
                                "field_name": "style_tag",
                                "field_value": tag,
                                "model_name": "moondream",
                            }
                            for tag in tags
                        ]
                        try:
                            supabase_client.table("ai_generated_tags").upsert(
                                records, on_conflict="product_id,field_name,field_value"
                            ).execute()
                        except Exception as e:
                            print(f"Warning: Could not save AI tags to database: {e}")

                    return {"tags": tags, "product_id": product_id}

                elif generate_all:
                    # Generate tags for all products without tags
                    products_result = (
                        supabase_client.table("products").select("*").execute()
                    )
                    products = products_result.data or []

                    # Filter to products without tags
                    products_to_tag = [
                        p
                        for p in products
                        if not p.get("style_tags") or len(p.get("style_tags", [])) == 0
                    ]

                    count = 0
                    supabase_url = os.getenv("SUPABASE_URL") or DEFAULT_SUPABASE_URL

                    for product in products_to_tag:
                        image_paths = product.get("image_paths", [])
                        if not image_paths:
                            continue

                        image_url = f"{supabase_url}/storage/v1/object/public/{BUCKET_NAME}/{image_paths[0]}"

                        tags = await tagger.generate_tags(
                            image_url=image_url,
                            product_name=product.get("name", ""),
                            product_description=product.get("description", ""),
                        )

                        if tags:
                            # Save to ai_generated_tags table
                            records = [
                                {
                                    "product_id": product.get("product_id"),
                                    "field_name": "style_tag",
                                    "field_value": tag,
                                    "model_name": "moondream",
                                }
                                for tag in tags
                            ]
                            try:
                                supabase_client.table("ai_generated_tags").upsert(
                                    records,
                                    on_conflict="product_id,field_name,field_value",
                                ).execute()
                                count += 1
                            except Exception as e:
                                print(f"Warning: Could not save AI tags: {e}")

                    return {
                        "count": count,
                        "message": f"Generated tags for {count} products",
                    }

                else:
                    return {"error": "Specify product_id or set all=true"}

        result = asyncio.run(generate())
        return jsonify(result)

    except ImportError as e:
        return jsonify({"error": f"AI modules not available: {e}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai/chat", methods=["POST"])
def ai_chat():
    """Chat with the AI fashion assistant."""
    import asyncio

    data = request.get_json() or {}
    messages = data.get("messages", [])

    if not messages:
        return jsonify({"error": "Messages are required"}), 400

    try:
        from src.ai import ChatAssistant, OllamaClient

        async def chat():
            async with OllamaClient() as client:
                if not await client.is_available():
                    return {"error": "Ollama is not running. Start with: ollama serve"}

                # Create chat assistant with Supabase if available
                assistant = ChatAssistant(
                    supabase_client=supabase_client if USE_SUPABASE else None,
                    ollama_client=client,
                )

                response = await assistant.chat(
                    messages=messages,
                    include_context=USE_SUPABASE,  # Only use product context if Supabase is available
                )

                return {"response": response}

        result = asyncio.run(chat())
        return jsonify(result)

    except ImportError as e:
        return jsonify({"error": f"AI modules not available: {e}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/images/<category>/<product_id>/<filename>")
def serve_image(category, product_id, filename):
    """Serve product images from local files."""
    image_dir = DATA_DIR / category / product_id
    return send_from_directory(image_dir, filename)


# ============================================
# SCRAPER ENDPOINTS
# ============================================


def run_scraper_process(categories, products_per_category):
    """Run the scraper in a background thread."""
    global scraper_status
    import time

    scraper_status["running"] = True
    scraper_status["completed"] = False
    scraper_status["error"] = None
    scraper_status["progress"] = 0
    scraper_status["products_scraped"] = 0
    scraper_status["products_skipped"] = 0
    scraper_status["start_time"] = time.time()
    scraper_status["total"] = len(categories) * products_per_category
    scraper_status["logs"] = []  # Clear previous logs

    try:
        # Build the command
        cmd = [
            "python",
            str(Path(__file__).parent / "main.py"),
            "--products",
            str(products_per_category),
            "--categories",
        ] + categories

        # Add supabase flag if we're using it
        if not USE_SUPABASE:
            cmd.append("--no-supabase")

        # Run the scraper process
        scraper_status["current_category"] = "Starting..."
        scraper_status["logs"].append(f"$ {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(Path(__file__).parent),
        )

        # Read output line by line to track progress
        for line in iter(process.stdout.readline, ""):
            line = line.strip()
            if not line:
                continue

            # Add to logs (keep last 100 lines)
            scraper_status["logs"].append(line)
            if len(scraper_status["logs"]) > 100:
                scraper_status["logs"] = scraper_status["logs"][-100:]

            # Parse progress from output
            if "Processing category:" in line:
                cat = line.split("Processing category:")[-1].strip()
                scraper_status["current_category"] = cat
            elif "Extracting product:" in line or "Scraping:" in line:
                scraper_status["current_product"] = line.split(":")[-1].strip()[:50]
            elif "Skipping already scraped" in line:
                scraper_status["products_skipped"] += 1
                scraper_status["progress"] = (
                    scraper_status["products_scraped"]
                    + scraper_status["products_skipped"]
                )
            elif "Saved to Supabase" in line or "Saved product" in line:
                scraper_status["products_scraped"] += 1
                scraper_status["progress"] = (
                    scraper_status["products_scraped"]
                    + scraper_status["products_skipped"]
                )
            elif "Extracted" in line and "new products" in line:
                # Extract count from "Extracted X new products"
                try:
                    count = int(line.split("Extracted")[1].split("new")[0].strip())
                    scraper_status["products_scraped"] = count
                except (ValueError, IndexError):
                    pass

        process.wait()

        if process.returncode == 0:
            scraper_status["completed"] = True
            scraper_status["current_category"] = "Complete!"
            scraper_status["current_product"] = ""
            scraper_status["logs"].append("✅ Scraping completed successfully!")
        else:
            scraper_status["error"] = (
                f"Process exited with code {process.returncode}. Check logs for details."
            )
            scraper_status["logs"].append(
                f"❌ Process exited with code {process.returncode}"
            )

    except Exception as e:
        scraper_status["error"] = str(e)
        scraper_status["logs"].append(f"❌ Error: {str(e)}")
    finally:
        scraper_status["running"] = False
        scraper_status["end_time"] = time.time()


@app.route("/api/scraper/start", methods=["POST"])
def start_scraper():
    """Start the web scraper process."""
    global scraper_status

    if scraper_status["running"]:
        return jsonify({"error": "Scraper is already running"}), 400

    # Reset status for new scrape
    scraper_status["refresh_handled"] = False
    scraper_status["completed"] = False
    scraper_status["error"] = None

    data = request.get_json() or {}
    categories = data.get(
        "categories",
        [
            "tshirts",
            "shirts",
            "trousers",
            "jeans",
            "shorts",
            "jackets",
            "blazers",
            "suits",
            "shoes",
            "bags",
            "accessories",
            "underwear",
            "new-in",
        ],
    )
    products_per_category = data.get("products_per_category", 2)

    # Start scraper in background thread
    thread = threading.Thread(
        target=run_scraper_process,
        args=(categories, products_per_category),
        daemon=True,
    )
    thread.start()

    return jsonify({"success": True, "message": "Scraper started"})


@app.route("/api/scraper/status")
def get_scraper_status():
    """Get the current scraper status."""
    return jsonify(scraper_status)


@app.route("/api/scraper/stop", methods=["POST"])
def stop_scraper():
    """Stop the scraper (not fully implemented - would need process tracking)."""
    global scraper_status
    # Note: This is a soft stop - sets a flag but doesn't kill the process
    scraper_status["running"] = False
    scraper_status["error"] = "Stopped by user"
    return jsonify({"success": True, "message": "Stop requested"})


@app.route("/api/scraper/reset", methods=["POST"])
def reset_scraper_status():
    """Reset scraper status after refresh has been handled."""
    global scraper_status
    scraper_status["refresh_handled"] = True
    return jsonify({"success": True})


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
