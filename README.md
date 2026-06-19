# Agentic Job Scraper

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Node.js](https://img.shields.io/badge/Node.js-18+-green.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal.svg)
![React](https://img.shields.io/badge/React-18+-61DAFB.svg)
![TypeScript](https://img.shields.io/badge/TypeScript-5+-3178C6.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

**AI-powered job scraping system for Telegram channels and RSS feeds**

[Features](#-features) • [Screenshots](#-screenshots) • [Architecture](#-architecture) • [Installation](#-installation) • [Usage](#-usage) • [API](#-api-endpoints)

</div>

---

## 🎯 Overview

Agentic Job Scraper is an automated system that fetches software development job postings from Telegram channels, RSS feeds (e.g., V2EX, 电鸭社区), and job boards (Bossjob.com), analyzes them using local AI (Ollama), and presents them in a modern web interface. Perfect for developers hunting for remote opportunities or recruiters monitoring market trends.

## ✨ Features

### Core Functionality
- **📡 Telegram Integration** — Monitor multiple Telegram channels for job postings with multi-account support
- **📡 Real-time Listener** — Start/stop real-time message listener from dashboard for instant job posting capture
- **🌐 RSS Feed Support** — Fetch and analyze job postings from RSS feeds (V2EX, 电鸭社区, etc.)
- **🎯 Bossjob.com Integration** — Playwright-based scraping with structured job extraction (title, company, location, requirements)
- **🤖 AI-Powered Analysis** — Uses Ollama (qwen2.5:14b or qwen2.5:7b) to extract structured job/developer data
- **📊 Real-time Progress** — WebSocket-based progress tracking with per-message status updates
- **🔔 Browser Notifications** — Get notified when new jobs or developers are discovered
- **🛑 Stop Operations** — Gracefully stop ongoing analysis with visual feedback

### Data Management
- **🔍 Smart Search** — Server-side search across jobs (title, company, skills, role) and developers (name, skills, experience)
- **📈 Analytics Dashboard** — Daily charts for job postings, developers contacted, and jobs applied
- **🧹 Message Cleanup** — Auto-cleanup messages older than 2 days (preserves applied jobs and contacted developers)
- **🏷 Status Tracking** — Mark jobs as applied and developers as contacted with notes
- **👻 Soft-Delete** — Hide jobs/developers instead of deleting to prevent duplicate re-fetching
- **📋 Copy to Clipboard** — Copy original message content on Messages, Jobs, and Developers pages

### User Experience
- **🎨 Modern UI** — Clean, responsive interface built with React, TypeScript, and shadcn/ui
- **🌍 Internationalization** — Full UI translation support (English, Chinese)
- **📱 Responsive Design** — Works seamlessly on desktop and mobile
- **⚡ Fast Performance** — Sequential processing with real-time progress updates

### Advanced Features
- **🔐 Multi-Account Auth** — Manage multiple Telegram accounts with interactive authentication
- **🎯 Remote-First** — Prioritizes remote/work-from-home opportunities
- **🧠 Smart Filtering** — Spam pre-filter before AI analysis for faster processing
- **📝 Custom Prompts** — Customize extraction prompts per website source
- **🇨🇳 V2EX-Specific** — Specialized prompt for Chinese tech job posts with translation
- **💾 Token Monitoring** — Real-time token usage tracking for Ollama API calls
- **🔄 Cron Auto-Analysis** — Continuous scanner automatically analyzes after fetching (both Telegram and RSS)
- **⏱ Robust RSS Fetching** — 30-second timeout and 7-day lookback window for RSS feeds

## 🚀 Planned Features

- [ ] Extended job board support (more career sites beyond Bossjob.com)
- [ ] Additional i18n languages
- [ ] Docker containerization
- [ ] CI/CD pipeline

## 🔄 Workflow

### High-Level Data Flow

```mermaid
graph TD
    A[Telegram Channels] -->|Telethon| B[Backend FastAPI]
    C[RSS Feeds<br/>V2EX, 电鸭社区] -->|feedparser| B
    B -->|Store in PostgreSQL| D[(Database)]
    B -->|WebSocket| E[Frontend React]
    F[Ollama LLM] -->|AI Analysis| B
    B -->|Send to Ollama| F
    E -->|User Actions| B
    E -->|Display Data| D
    
    style A fill:#3b82f6,color:#fff
    style C fill:#10b981,color:#fff
    style B fill:#f59e0b,color:#fff
    style D fill:#8b5cf6,color:#fff
    style E fill:#ec4899,color:#fff
    style F fill:#06b6d4,color:#fff
```

**Process Overview:**
1. **Data Sources** — Telegram channels and RSS feeds provide raw job postings
2. **Backend Processing** — FastAPI fetches, stores, and analyzes messages
3. **AI Analysis** — Ollama extracts structured job/developer data from messages
4. **Real-time Updates** — WebSocket streams progress to frontend
5. **User Interface** — React displays results with search and filtering

### Detailed Data Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant Telegram
    participant RSS
    participant Ollama
    participant DB

    User->>Frontend: Add Channel/Website
    Frontend->>Backend: POST /api/channels or /api/website-sources
    Backend->>DB: Store channel/website info

    User->>Frontend: Click Fetch
    Frontend->>Backend: POST /api/fetch or /api/website-sources/{id}/fetch
    Backend->>Telegram: Fetch messages (Telethon)
    Telegram-->>Backend: Return messages
    Backend->>RSS: Fetch RSS feed (feedparser)
    RSS-->>Backend: Return feed entries
    Backend->>DB: Store messages with status="pending"

    User->>Frontend: Click Analyze
    Frontend->>Backend: POST /api/analyze or /api/website-sources/{id}/analyze
    Backend->>DB: Get pending messages (ordered by date desc)
    loop For each message (sequential)
        Backend->>Ollama: Send message for analysis
        Ollama-->>Backend: Return job/developer data
        Backend->>Frontend: WebSocket progress update
        Backend->>DB: Store extracted jobs/developers
        Backend->>DB: Update message status to "analyzed"
    end
    Backend-->>Frontend: Analysis complete
    Frontend->>User: Display results with notifications

    User->>Frontend: View Dashboard
    Frontend->>Backend: GET /api/stats, /api/daily-jobs
    Backend->>DB: Query analytics data
    Backend-->>Frontend: Return stats
    Frontend->>User: Display charts
```

**Key Flow Details:**
- **Fetch Phase** — Messages are stored with `analysis_status="pending"`
- **Analysis Phase** — Messages processed sequentially one at a time
- **Progress Tracking** — WebSocket sends real-time updates per message
- **Notifications** — Browser alerts for job/developer discoveries and completion
- **Data Persistence** — Jobs and developers stored separately from original messages

### System Architecture

```mermaid
graph TB
    subgraph Frontend["🎨 Frontend Layer"]
        direction TB
        A[React UI<br/>Dashboard, Channels, Jobs, Developers]
        B[WebSocket Client<br/>Real-time Progress Updates]
        C[API Client<br/>RESTful API Calls]
        D[Notification Manager<br/>Browser Alerts]
        E[Search & Filter<br/>Client-side UI]
    end

    subgraph Backend["⚙ Backend Layer"]
        direction TB
        F[FastAPI Server<br/>REST API Endpoints]
        G[WebSocket Server<br/>Progress Broadcasting]
        H[Task Orchestrator<br/>Background Jobs]
        I[Data Layer<br/>SQLAlchemy ORM]
        J[Telegram Processor<br/>Multi-account Manager]
        K[RSS Crawler<br/>Feed Parser]
        L[AI Service<br/>Ollama Integration]
        M[Analytics Engine<br/>Daily Statistics]
    end

    subgraph External["🌐 External Services"]
        direction TB
        N[Telegram API<br/>Message Fetching]
        O[RSS Feeds<br/>V2EX, 电鸭社区]
        P[Ollama LLM<br/>qwen2.5:14b/7b]
        Q[PostgreSQL<br/>Data Persistence]
    end

    A <--> C
    A <--> B
    A <--> D
    A <--> E
    C <--> F
    B <--> G
    J <--> N
    K <--> O
    L <--> P
    I <--> Q
    J --> H
    K --> H
    L --> H
    M --> I
    H --> I
    F --> I
    G --> H

    style Frontend fill:#ec4899,color:#fff
    style Backend fill:#f59e0b,color:#fff
    style External fill:#3b82f6,color:#fff
    style A fill:#be185d,color:#fff
    style B fill:#be185d,color:#fff
    style C fill:#be185d,color:#fff
    style D fill:#be185d,color:#fff
    style E fill:#be185d,color:#fff
    style F fill:#b45309,color:#fff
    style G fill:#b45309,color:#fff
    style H fill:#b45309,color:#fff
    style I fill:#b45309,color:#fff
    style J fill:#b45309,color:#fff
    style K fill:#b45309,color:#fff
    style L fill:#b45309,color:#fff
    style M fill:#b45309,color:#fff
    style N fill:#1d4ed8,color:#fff
    style O fill:#1d4ed8,color:#fff
    style P fill:#1d4ed8,color:#fff
    style Q fill:#1d4ed8,color:#fff
```

**Component Responsibilities:**

#### Frontend Layer
- **React UI** — Main application interface with pages for Dashboard, Channels, Jobs, Developers, Messages, and Settings
- **WebSocket Client** — Maintains persistent connection for real-time progress updates during analysis operations
- **API Client** — Handles all RESTful API calls with proper error handling and loading states
- **Notification Manager** — Manages browser notifications for job/developer discoveries and analysis completion
- **Search & Filter** — Client-side UI components for filtering and searching jobs and developers

#### Backend Layer
- **FastAPI Server** — Provides RESTful API endpoints for all CRUD operations and business logic
- **WebSocket Server** — Broadcasts progress updates to connected clients during long-running tasks
- **Task Orchestrator** — Manages background tasks for fetching, analyzing, and cron jobs
- **Data Layer** — SQLAlchemy async ORM with PostgreSQL for all database operations
- **Telegram Processor** — Telethon-based client for fetching messages with multi-account support
- **RSS Crawler** — feedparser-based RSS feed fetcher with website source management
- **AI Service** — Ollama integration for AI-powered job/developer extraction with token tracking
- **Analytics Engine** — Aggregates daily statistics for jobs posted, developers contacted, and jobs applied

#### External Services
- **Telegram API** — Official Telegram API for message fetching and account authentication
- **RSS Feeds** — External RSS feeds from job boards (V2EX, 电鸭社区, etc.)
- **Ollama LLM** — Local LLM service running qwen2.5:14b or qwen2.5:7b for AI analysis
- **PostgreSQL** — Relational database for persistent storage of all application data

**Data Flow Patterns:**
- **Fetch Flow** — Telegram/RSS → Backend → Database → WebSocket → Frontend
- **Analyze Flow** — Database → Ollama → Backend → Database → WebSocket → Frontend
- **Query Flow** — Frontend → API → Database → API → Frontend
- **Notification Flow** — Backend → WebSocket → Frontend → Browser Notification

## 📸 Screenshots

### Dashboard
![Dashboard](screenshots/Dashboard.png)

### Channels
![Channels](screenshots/Channels.png)

### Add Channel
![Add Channel](screenshots/Channels%20-%20add.png)

### Messages
![Messages](screenshots/Messages.png)

### Jobs
![Jobs](screenshots/Job.png)

### Job Detail
![Job Detail](screenshots/Job%20Detail%202.png)

### Developers
![Developers](screenshots/Developers.png)

### Telegram Accounts
![Telegram Accounts](screenshots/Telegrams.png)

### Websites
![Websites](screenshots/Websites.png)

### Backend API
![Backend API](screenshots/Backend.png)

## 👥 Who is this for?

### Primary Users
- **👨‍💻 Software Developers** — Job hunters looking for remote/work-from-home opportunities who want to monitor multiple Telegram job channels in one place
- **🎯 Tech Recruiters** — Recruiters monitoring competitor job postings and hiring managers tracking market trends
- **📢 Channel Managers** — Telegram channel admins analyzing job posting effectiveness and community engagement

### Secondary Users
- **🌍 Remote Work Enthusiasts** — Developers seeking remote opportunities in regions with limited local job markets
- **🤖 AI/ML Enthusiasts** — Developers interested in practical applications of local LLMs (Ollama) for content analysis

## ⚠ Project Status

> **Note:** This project is designed for personal use. While fully functional, it may not have all enterprise-grade best practices:

**Current State:**
- ✅ Fully functional for personal job hunting and monitoring
- ✅ Solid foundation for AI-powered web scraping
- ✅ Active development and maintenance

**Missing Enterprise Features:**
- ⬜ Comprehensive testing suite (unit, integration, E2E)
- ⬜ CI/CD pipeline configuration
- ⬜ Code quality tools (ESLint, Prettier, Black, isort)
- ⬜ Pre-commit hooks
- ⬜ Docker containerization
- ⬜ Database migration management (Alembic)
- ⬜ Security hardening (rate limiting, input validation)
- ⬜ Monitoring and logging infrastructure
- ⬜ Backup and disaster recovery documentation

Feel free to extend it with additional features and best practices for your use case.

## 🏗 Architecture

### Backend Stack
- **FastAPI** — Async web framework for high-performance API endpoints
- **SQLAlchemy** — Async ORM with PostgreSQL for database operations
- **Telethon** — Telegram client for fetching messages and authentication
- **Ollama** — Local LLM for AI-powered message analysis
- **WebSocket** — Real-time progress updates to frontend
- **feedparser** — RSS feed parsing for website sources

### Frontend Stack
- **React 18** — Modern React with hooks for state management
- **TypeScript** — Type-safe development with full type coverage
- **Vite** — Fast build tool and dev server with HMR
- **shadcn/ui** — Beautiful, accessible UI components built on Radix UI
- **Tailwind CSS** — Utility-first CSS framework for rapid styling
- **React Router** — Client-side routing with lazy loading
- **react-i18next** — Internationalization (English, Chinese)

## 📋 Prerequisites

- **Python 3.10+** — Backend runtime
- **Node.js 18+** — Frontend runtime
- **PostgreSQL 14+** — Database (or SQLite for development)
- **Ollama** — Local LLM with qwen2.5:14b or qwen2.5:7b model
- **Telegram API credentials** — Optional, can be added via UI

## 🛠 Installation

### Backend Setup

1. **Navigate to the backend directory:**
```bash
cd backend
```

2. **Create a virtual environment:**
```bash
python -m venv env
env\Scripts\activate  # On Windows
source env/bin/activate  # On Linux/Mac
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables:**
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```env
# Telegram API credentials (optional - can be added via UI)
# Get from https://my.telegram.org/apps
# TELEGRAM_API_ID=your_api_id_here
# TELEGRAM_API_HASH=your_api_hash_here
# TELEGRAM_PHONE=+1234567890

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b
DATABASE_URL=postgresql+asyncpg://user:password@localhost/job_scraper
```

> **Tip:** Telegram credentials are optional. You can add and manage multiple Telegram accounts entirely through the web UI with interactive authentication (verification code and 2FA password entered in browser).

5. **Initialize the database:**
```bash
python reset_db.py
```

This creates all necessary tables including `telegram_accounts` for multi-account support.

### Frontend Setup

1. **Navigate to the frontend directory:**
```bash
cd frontend
```

2. **Install dependencies:**
```bash
npm install
```

3. **Configure environment variables:**
```bash
cp .env.example .env
```

Edit `.env` with your API URL:
```env
# For local development (separate backend server)
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000/ws/progress

# For production (same domain - FastAPI serves static files)
VITE_API_BASE_URL=
VITE_WS_BASE_URL=

# For ngrok
VITE_API_BASE_URL=https://your-ngrok-url.ngrok-free.app
VITE_WS_BASE_URL=wss://your-ngrok-url.ngrok-free.app/ws/progress
```

### Ollama Setup

1. **Install Ollama** from [ollama.com](https://ollama.com)

2. **Pull the recommended model:**
```bash
ollama pull qwen2.5:14b  # Better accuracy
# or
ollama pull qwen2.5:7b   # Faster performance
```

3. **Start Ollama server:**
```bash
ollama serve
```

> **💡 Tip:** Larger models produce significantly better inference results. If your hardware supports it, prefer `qwen2.5:14b` or higher (e.g., `qwen2.5:32b`) for more accurate job/developer extraction. Smaller models like `7b` are faster but may miss details or produce lower-confidence classifications.

## 🚀 Running the Application

### Development Mode

**Start the Backend:**
```bash
cd backend
python web_app.py
```
Backend runs on `http://localhost:8000`

**Start the Frontend:**
```bash
cd frontend
npm run dev
```
Frontend runs on `http://localhost:5173`

### Production Mode

#### Option 1: Serve Static Files from FastAPI (Simplest)

1. **Build the frontend:**
```bash
cd frontend
npm run build
```

2. **Run the backend** (serves both API and frontend):
```bash
cd backend
python web_app.py
```

Access at `http://localhost:8000`

#### Option 2: Separate Deployment (Nginx + Gunicorn)

1. **Build the frontend:**
```bash
cd frontend
npm run build
```

2. **Configure Nginx:**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        root /path/to/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://localhost:8000;
    }

    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

3. **Run backend with Gunicorn:**
```bash
cd backend
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker web_app:app --bind 0.0.0.0:8000
```

### Using ngrok for Remote Access

1. **Start the backend:**
```bash
cd backend
python web_app.py
```

2. **Start ngrok in a separate terminal:**
```bash
ngrok http 8000
```

3. **Copy the ngrok URL** (e.g., `https://abc123.ngrok-free.app`)

4. **Configure frontend `.env`:**
```env
VITE_API_BASE_URL=https://abc123.ngrok-free.app
VITE_WS_BASE_URL=wss://abc123.ngrok-free.app/ws/progress
```

5. **Start the frontend:**
```bash
cd frontend
npm run dev
```

## 📖 Usage

### Setting Up Telegram Accounts

1. **Get API Credentials** — Visit [my.telegram.org/apps](https://my.telegram.org/apps) to create an application and obtain your `api_id` and `api_hash`

2. **Add Account via UI:**
   - Navigate to "Telegram Accounts" in the sidebar
   - Click "Add Account"
   - Enter your API ID, API Hash, and phone number
   - Click "Add Account"

3. **Authenticate Your Account:**
   - Click "Authenticate" next to your unauthenticated account
   - Enter the verification code sent to your phone
   - If 2FA is enabled, enter your 2FA password when prompted
   - Account shows "Authenticated" badge when complete

4. **Manage Multiple Accounts:**
   - Add as many accounts as needed
   - Toggle accounts as active/inactive
   - Delete accounts you no longer need
   - Select which account to use when fetching channels

### Using the Application

1. **Add Channels** — Go to Channels page and add Telegram channels to monitor
2. **Add Website Sources** — Go to Websites page and add RSS feed URLs (V2EX, 电鸭社区, etc.)
3. **Select Account** — Choose which Telegram account to use when fetching (if multiple)
4. **Fetch Messages** — Click "Fetch" to retrieve recent messages from channels or RSS feeds
5. **Analyze** — Click "Analyze" to process messages with AI and extract job/developer info
6. **Stop Analysis** — Click "Stop" to gracefully stop ongoing analysis (shows "Stopping..." state)
7. **Monitor Progress** — View real-time progress including token usage and per-message status
8. **View Results** — Browse Jobs and Developers pages to see extracted information
9. **Track Progress** — Mark jobs as applied and developers as contacted with notes
10. **Continuous Scanning** — Enable cron job for automatic periodic fetching and analysis
11. **Analytics** — View daily charts on Dashboard for job postings, developers contacted, jobs applied
12. **Cleanup** — Messages older than 2 days are auto-cleaned on startup (applied jobs and contacted developers preserved)
13. **Copy Messages** — Click the copy button on Messages, Jobs, or Developers pages to copy original message text
14. **Custom Prompts** — Customize extraction prompts per website source for better accuracy
15. **V2EX Configuration** — Set `site_type="v2ex"` when adding V2EX for specialized Chinese job post prompt

## 🔌 API Endpoints

### Channels
- `GET /api/channels` — List all channels
- `POST /api/channels` — Add a new channel
- `DELETE /api/channels/{id}` — Delete a channel

### Telegram Accounts
- `GET /api/telegram-accounts` — List all Telegram accounts
- `POST /api/telegram-accounts` — Add a new Telegram account
- `DELETE /api/telegram-accounts/{id}` — Delete a Telegram account
- `PATCH /api/telegram-accounts/{id}/toggle-active` — Toggle account active status
- `POST /api/telegram-accounts/authenticate` — Start authentication process
- `POST /api/telegram-accounts/verify-code` — Verify authentication code
- `POST /api/telegram-accounts/verify-password` — Verify 2FA password

### Website Sources
- `GET /api/website-sources` — List all website sources
- `POST /api/website-sources` — Add a new website source (RSS feed)
- `DELETE /api/website-sources/{id}` — Delete a website source
- `PUT /api/website-sources/{id}` — Update website source (custom prompt, site_type)
- `POST /api/website-sources/{id}/fetch` — Fetch RSS content from a source
- `POST /api/website-sources/fetch-all` — Fetch from all active sources
- `POST /api/website-sources/{id}/analyze` — Analyze messages from a source
- `POST /api/website-sources/analyze-all` — Analyze messages from all sources
- `POST /api/website-sources/{id}/stop` — Stop ongoing operation for a source

> **Note:** Set `site_type="v2ex"` when adding V2EX sources for specialized Chinese job post prompt.

### Messages
- `GET /api/messages` — List messages with pagination
- `GET /api/messages/{id}` — Get message details

### Jobs
- `GET /api/jobs` — List extracted jobs (with search filters)
- `GET /api/jobs/{id}` — Get job details
- `POST /api/jobs/{id}/toggle-applied` — Mark job as applied/unapplied
- `DELETE /api/jobs/{id}` — Hide a job (soft-delete)

### Developers
- `GET /api/developers` — List extracted developers (with search filters)
- `GET /api/developers/{id}` — Get developer details
- `POST /api/developers/{id}/toggle-contacted` — Mark developer as contacted/uncontacted
- `DELETE /api/developers/{id}` — Hide a developer (soft-delete)

### Actions
- `POST /api/fetch/{channel_id}` — Fetch messages from a channel
- `POST /api/analyze/{channel_id}` — Analyze messages in a channel
- `POST /api/stop-analyze?channel_id={id}` — Stop ongoing analysis for a channel
- `POST /api/listener/start` — Start real-time Telegram message listener
- `POST /api/listener/stop` — Stop real-time Telegram message listener
- `POST /api/listener/add-channels` — Add channels to running listener
- `POST /api/listener/remove-channels` — Remove channels from running listener
- `POST /api/cron/start` — Start continuous scanner
- `POST /api/cron/stop` — Stop continuous scanner
- `POST /api/cleanup/old-messages?days={n}` — Delete messages older than N days

### Analytics
- `GET /api/daily-jobs?days={n}` — Daily job postings by channel (last N days)
- `GET /api/daily-developers-contacted?days={n}` — Daily developers contacted (last N days)
- `GET /api/daily-jobs-applied?days={n}` — Daily jobs applied (last N days)

### WebSocket
- `WS /ws/progress` — Real-time progress updates

## 📁 Project Structure

```
agentic-job-scraper/
├── backend/
│   ├── app/
│   │   ├── models.py          # Database models (Job, Developer, Channel, etc.)
│   │   ├── routes/            # API endpoints (channels, jobs, developers, etc.)
│   │   ├── connection.py      # Database & WebSocket connection
│   │   └── tasks.py           # Background tasks (fetch, analyze, cron)
│   ├── services/
│   │   └── ollama_service.py  # AI analysis service
│   ├── telegram_processor/    # Telegram client (Telethon)
│   ├── web_crawler/           # RSS feed crawler and extractor
│   │   ├── rss_fetcher.py     # RSS feed fetching
│   │   ├── rss_extractor.py   # Ollama-based extraction
│   │   ├── models.py          # Pydantic models for extraction
│   │   └── prompts.py         # Extraction prompts
│   └── web_app.py             # FastAPI entry point
├── frontend/
│   ├── src/
│   │   ├── components/        # React components (Layout, UI)
│   │   ├── pages/             # Page components (Dashboard, Channels, etc.)
│   │   ├── services/          # API client
│   │   ├── hooks/             # Custom hooks (useWebSocketProgress)
│   │   └── locales/           # i18n translation files (en.json, zh.json)
│   └── package.json
└── README.md
```

## ⚙ Configuration

### Telegram Account Management

The application supports managing multiple Telegram accounts through the web UI. Each account is stored in the database with:

- **API ID & API Hash** — Credentials from my.telegram.org
- **Phone Number** — The phone number associated with the account
- **Session Name** — Unique identifier for the session file
- **Authentication Status** — Whether the account has been authenticated
- **Active Status** — Whether the account is currently active for use

**Authentication Flow:**
1. Add account credentials via UI
2. Click "Authenticate" to start the process
3. Enter verification code sent to your phone
4. If 2FA is enabled, enter your 2FA password
5. Account is marked as authenticated and ready to use

**Session Management:**
- Session files stored in `backend/session/`
- Each account has its own session file
- Sessions persist across server restarts
- Re-authentication only needed if session is deleted or expires

### Telegram API

Get your API credentials from [my.telegram.org/apps](https://my.telegram.org/apps). You can create multiple applications for different accounts.

### Ollama Configuration

**Recommended Models:**
- `qwen2.5:14b` — Better accuracy for complex extraction
- `qwen2.5:7b` — Faster performance for high-volume processing

**Configuration Options:**
- Remote Ollama instance support
- GPU acceleration for faster processing
- Sequential processing (one message at a time, no semaphore contention)
- Real-time token usage tracking (input/output/total tokens)
- Spam pre-filter to skip non-tech messages before Ollama
- V2EX-specific prompt for Chinese job posts with translation
- Generic RSS prompt for other website sources

**Environment Variables:**
```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b
```

**Advanced Options** (in `ollama_service.py`):
- `num_predict` — Maximum tokens to generate (dynamically adjusted based on message length + system prompt)
- `num_ctx` — Context window size (dynamically adjusted based on message length + system prompt)
- `num_gpu` — GPU layers to offload (default: 99, full GPU offload)
- `keep_alive` — Keep model in memory (default: -1, indefinitely)
- `timeout` — Request timeout (default: 180s)

**Dynamic Context Sizing:**
- Automatically calculates `num_ctx` and `num_predict` based on message length plus system prompt length
- Four tiers: <512 chars (1024/512), <1024 chars (2048/1024), <2048 chars (4096/2048), ≥2048 chars (8192/4096)

**RSS Extractor Options** (in `rss_extractor.py`):
- `MAX_CHARS` — Chunk size for content (default: 3000, ~1000-1500 tokens)
- `temperature` — Low temp for factual extraction (default: 0.1)

### Database

- **PostgreSQL** with async support (or SQLite for development)
- Connection pooling configured for performance
- Automatic table creation on startup
- Session files stored in `backend/session/` directory

### Database Migrations

When updating the application, you may need to run database migrations:

```bash
cd backend/migrations
for f in *.sql; do psql -U your_username -d job_scraper -f "$f"; done
```

Available migrations:
- `add_telegram_accounts.sql` — Add Telegram accounts table
- `add_phone_code_hash.sql` — Add phone code hash column
- `add_telegram_account_id_to_channels.sql` — Add telegram_account_id to channels
- `make_developer_message_id_nullable.sql` — Make developer.message_id nullable
- `add_channel_name_to_jobs.sql` — Add channel_name column to jobs
- `add_last_fetch_tracking.sql` — Add last fetch tracking columns
- `add_message_analysis_flags.sql` — Add message analysis flags
- `add_operations_table.sql` — Add operations tracking table
- `add_analysis_runs_table.sql` — Add analysis runs table
- `migrate_add_skip_reason.sql` — Add skip_reason column to messages
- `migrate_operations_cascade.sql` — Add cascade delete to operations
- `fix_skills_default.sql` — Fix skills column default value
- `add_is_hidden_to_jobs_developers.sql` — Add is_hidden column for soft-delete

## 🔧 Troubleshooting

### Telegram Authentication Issues

**Code not received:**
- Check phone number includes country code (e.g., +1234567890)
- Ensure you're not logged in to Telegram on another device with the same number
- Try clicking "Resend Code" in the authentication dialog
- Check if Telegram is blocking verification requests (wait a few minutes)

**Authentication session expired:**
- Click "Authenticate" again to request a new code
- Old session will be automatically cleaned up

**2FA password incorrect:**
- Ensure you're entering your Telegram 2FA password (not phone passcode)
- Check for typos and try again
- Reset 2FA password through Telegram if forgotten

**Account shows as not authenticated after successful auth:**
- Refresh the page to see updated status
- Check backend logs for errors during authentication
- Try authenticating again if session was interrupted

### Ollama Connection Issues
- Ensure Ollama server is running: `ollama serve`
- Check `OLLAMA_BASE_URL` in `.env`
- Verify model is installed: `ollama list`
- Ensure remote Ollama instance is accessible from your network

### Telegram Flood Errors
- System automatically handles FloodWaitError
- Will retry after required wait time
- No manual intervention needed
- Reduce fetch frequency if errors persist

### Database Connection
- Verify PostgreSQL is running
- Check `DATABASE_URL` in `.env`
- Ensure database exists: `createdb job_scraper`
- Check database credentials are correct

### Session File Issues
- Delete session file in `backend/session/` if authentication fails with "Two-steps verification is enabled"
- Session files named like `session_+1234567890.session`
- Authentication flow automatically cleans up old sessions

### Channel Fetching Issues
- Ensure you have at least one authenticated and active Telegram account
- Check selected account is active in the dropdown
- Verify channel username is correct (without @ symbol)
- Check backend logs for specific error messages
- Ensure selected Telegram account has access to the channel
- **Channels without public username:** The listener now supports channels without public usernames by using their internal Telegram ID. These channels will be auto-created in the database when messages are received.

### Frontend API Connection Issues
- Check backend is running on expected port (default: 8000)
- Verify `VITE_API_BASE_URL` in frontend `.env`
- Check browser console for CORS errors
- Ensure WebSocket URL is correct (`VITE_WS_BASE_URL`)

## 🌍 Internationalization (i18n)

The frontend supports English and Chinese (Simplified) with a language switcher in the top navigation bar.

- **Locale files:** `frontend/src/locales/en.json` and `frontend/src/locales/zh.json`
- **Translated content:** All UI text, buttons, labels, toast notifications, error messages, and placeholders
- **Adding languages:** Create a new locale file and register it in `frontend/src/i18n.ts`
- **Persistence:** Selected language is persisted in `localStorage`

## 📄 License

MIT

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
