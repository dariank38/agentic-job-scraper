# Bossjob Cookie Exporter Chrome Extension

One-click export of bossjob.com cookies to your job scraper dashboard.

## Installation

1. **Open Chrome Extensions page:**
   - Go to `chrome://extensions/`
   - Enable **"Developer mode"** (toggle in top-right)

2. **Load the extension:**
   - Click **"Load unpacked"**
   - Select the `cookie-extension` folder (`e:\agentic-job-scraper\cookie-extension`)

3. **Pin the extension:**
   - Click the puzzle icon in Chrome toolbar
   - Pin "Bossjob Cookie Exporter" for easy access

## Usage

1. **Login to bossjob.com** in Chrome (using Google login)
2. **Click the extension icon** in Chrome toolbar
3. **Enter your settings:**
   - Dashboard API URL: `http://localhost:8000` (or your backend URL)
   - Website Source ID: The ID of your bossjob source (check Websites page)
4. **Click "Export Cookies to Dashboard"**

## How it works

- Extension reads cookies from `bossjob.com` domain
- Formats them for Playwright authentication
- Sends via API to update your website source
- Cookies are then used automatically when scraping

## Troubleshooting

- **"No cookies found"** - Make sure you're logged into bossjob.com
- **"Connection refused"** - Check that your backend is running
- **404 error** - Verify the source ID exists in your dashboard

## Security

- Extension only reads cookies from bossjob.com
- Cookies are sent directly to your backend API
- No data is stored or sent to third parties
