# Facebook Automation Tool

A Python-based Facebook automation tool using Playwright for browser control and Flask for the dashboard UI. It supports posting to Groups, Pages, and Threads with advanced anti-detection mechanisms like Spintax, human typing simulation, and randomized delays.

## Features
- **Bulk Posting:** Post to multiple groups/pages/threads in one run.
- **Google Sheets Integration:** Fetch targets and content directly from a public Google Sheets CSV.
- **Anti-Detection:**
  - Spintax support (e.g. `{Hello|Hi}`)
  - Human typing simulation with random delays and occasional typos.
  - Mouse movement and scrolling simulation.
  - Randomized anti-spam delays (30-60s) between posts.
- **Image Support:** Attach images to your posts.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/NatoandUSA/fbpost.git
   cd fbpost
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   ```

## Usage

1. Start the Flask Server:
   ```bash
   source venv/bin/activate
   python server.py
   ```
2. Open `http://127.0.0.1:5000` in your browser.
3. Authenticate with your Facebook account by clicking **Authenticate (Login)** in the dashboard (only needed once to save session state).
4. Enter your targets manually or via Google Sheets CSV and click **Post Now**.
