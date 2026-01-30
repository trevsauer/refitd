# Supabase Setup Guide

This guide explains how to connect to the shared Supabase database for the Zara Product Viewer.

## Quick Start (For Collaborators)

If you're working with someone who has already set up the Supabase project, you just need the credentials.

### Step 1: Install Dependencies

```bash
cd refitd
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Create Your `.env` File

Copy the example file and fill in the credentials:

```bash
cp .env.example .env
```

Then edit `.env` with the provided credentials:

```env
# Supabase Configuration
SUPABASE_URL=https://uochfddhtkzrvcmfwksm.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVvY2hmZGRodGt6cnZjbWZ3a3NtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg1MDA1NDEsImV4cCI6MjA4NDA3NjU0MX0.mzBTf1GV8_Vk-nIMvf26PxI_MAqZfStzRTEZBEvHyLU
```

### Step 3: Run the Viewer

```bash
python viewer.py --supabase
```

Open http://localhost:5000 in your browser.

---

## Troubleshooting

### "Supabase credentials not found" Error

Make sure:
1. You have a `.env` file in the `refitd` directory (not `.env.example`)
2. The file contains both `SUPABASE_URL` and `SUPABASE_KEY`
3. There are no extra spaces around the `=` sign
4. The file is saved

### "Module 'supabase' not found" Error

Install the dependencies:
```bash
pip install supabase python-dotenv
```

Or install all dependencies:
```bash
pip install -r requirements.txt
```

### Connection Timeout

Check your internet connection. The Supabase database is hosted in the cloud.

### "Table 'products' does not exist" Error

The database tables need to be created. If you're setting up a new Supabase project, run the SQL in `supabase_schema.sql`.

---

## Setting Up Your Own Supabase Project (New Project)

If you want to create your own Supabase project:

### Step 1: Create a Supabase Account

1. Go to https://supabase.com
2. Sign up for a free account
3. Create a new project

### Step 2: Get Your Credentials

1. Go to your project dashboard
2. Click on **Settings** (gear icon) in the sidebar
3. Click on **API** under Project Settings
4. Copy:
   - **Project URL** → This is your `SUPABASE_URL`
   - **anon public** key → This is your `SUPABASE_KEY`

### Step 3: Create the Database Tables

1. In your Supabase dashboard, click **SQL Editor**
2. Copy the contents of `supabase_schema.sql`
3. Paste and run it

### Step 4: Create the Storage Bucket

1. Go to **Storage** in the sidebar
2. Click **New bucket**
3. Name it `product-images`
4. Make it **Public** (toggle public access on)

### Step 5: Update Your `.env` File

```env
SUPABASE_URL=https://YOUR-PROJECT-ID.supabase.co
SUPABASE_KEY=your-anon-public-key-here
```

---

## Project Credentials (Current)

For collaborators working on this project, use these credentials:

| Setting | Value |
|---------|-------|
| **SUPABASE_URL** | `https://uochfddhtkzrvcmfwksm.supabase.co` |
| **SUPABASE_KEY** | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVvY2hmZGRodGt6cnZjbWZ3a3NtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg1MDA1NDEsImV4cCI6MjA4NDA3NjU0MX0.mzBTf1GV8_Vk-nIMvf26PxI_MAqZfStzRTEZBEvHyLU` |

---

## Running the App

### View Products from Supabase
```bash
python viewer.py --supabase
```

### View Products from Local Files (no database)
```bash
python viewer.py
```

### Run the Scraper and Save to Supabase
```bash
python main.py --supabase
```

---

## File Overview

| File | Purpose |
|------|---------|
| `.env` | Your local credentials (create from `.env.example`) |
| `.env.example` | Template showing required environment variables |
| `supabase_schema.sql` | Database schema - run in Supabase SQL Editor |
| `src/loaders/supabase_loader.py` | Python code that connects to Supabase |
| `viewer.py` | Web viewer application |
| `requirements.txt` | Python dependencies |
