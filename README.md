# Agentic Job Scraper

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Node.js](https://img.shields.io/badge/Node.js-18+-green.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal.svg)
![React](https://img.shields.io/badge/React-18+-61DAFB.svg)
![TypeScript](https://img.shields.io/badge/TypeScript-5+-3178C6.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

**[English](#english) • [中文](#chinese)**

</div>

---

<a id="english"></a>

<div align="center">

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

### AI Resume Tools
- **📄 Generate Resume** — AI generates a tailored resume from scratch based on any job posting (streaming, Ollama or NVIDIA)
- **✨ Enhance Resume** — Paste your existing resume and AI rewrites it specifically for the target job while preserving real experience
- **🎯 Match Score** — AI scores your resume against the job (0–100) with matched skills, missing skills, strengths, and improvement suggestions
- **🔄 Real-time Streaming** — Resume generation and enhancement stream token-by-token for instant feedback
- **🌐 Cross-browser Sync** — WebSocket broadcasts generation status so multiple users can't generate simultaneously
- **📋 Copy & Download** — Copy to clipboard or download generated/enhanced resumes as `.txt`

### Advanced Features
- **🔐 Multi-Account Auth** — Manage multiple Telegram accounts with interactive authentication
- **🎯 Remote-First** — Prioritizes remote/work-from-home opportunities
- **🧠 Smart Filtering** — Spam pre-filter before AI analysis for faster processing
- **📝 Custom Prompts** — Customize extraction prompts per website source
- **🇨🇳 V2EX-Specific** — Specialized prompt for Chinese tech job posts with translation
- **💾 Token Monitoring** — Real-time token usage tracking for Ollama API calls
- **🔄 Cron Auto-Analysis** — Continuous scanner automatically analyzes after fetching (both Telegram and RSS)
- **⏱ Robust RSS Fetching** — 30-second timeout and 7-day lookback window for RSS feeds
- **🍪 Cookie Extension** — Chrome extension for one-click Bossjob.com cookie export
- **🤖 Autonomous Agent Mode** — Self-adjusting schedules, self-healing Playwright scrapers, and automated source discovery
- **🗑 Cascade Delete** — Deleting a channel or website source automatically removes all associated messages, jobs, and developers

### Autonomous Agent Mode (Optional)

The system can run as a self-sustaining agent when `ENABLE_AUTONOMOUS_MODE=true` is set:

- **Self-Adjusting Cron** — Analyzes historical yield per source and shifts fetch frequency dynamically (10 min to 12 hours)
- **Self-Healing Playwright** — Rotates fingerprints/proxies and uses LLM to recover from broken selectors
- **Token Budget Guard** — Enforces a daily Ollama token budget so self-learning cannot exhaust resources

Works with existing sources: Telegram channels, Bossjob.com, Dianya (电鸭社区), V2EX.

Auto-apply is explicitly **not** implemented; autonomy is limited to optimizing existing sources.

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
16. **AI Resume Tools** — Click "Generate Resume" on any job to open the AI Resume Tools dialog:
    - **Generate tab** — Generate a tailored resume from scratch, then copy or download
    - **Enhance tab** — Paste your existing resume and AI rewrites it for the job
    - **Match Score tab** — Paste your resume to get a 0–100 match score with skill breakdown
    - > **💡 Tip:** Resume tools work out of the box with Ollama (default). To use NVIDIA instead, set `RESUME_PROVIDER=nvidia` and `NVIDIA_API_KEY` in your backend `.env`. Get a free key at [build.nvidia.com](https://build.nvidia.com).

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

### Resume (NVIDIA API)
- `POST /api/resume/generate` — Generate a tailored resume for a job (streaming SSE)
- `POST /api/resume/enhance` — Enhance an existing resume for a job (streaming SSE)
- `POST /api/resume/score` — Score resume match against a job (returns JSON breakdown)

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

### NVIDIA API (Resume Tools)

Resume tools default to **Ollama** (`RESUME_PROVIDER=ollama`) and work without any API key. To switch to NVIDIA:

```env
RESUME_PROVIDER=nvidia
NVIDIA_API_KEY=your_nvidia_api_key_here
```

> Get a free NVIDIA API key at [build.nvidia.com](https://build.nvidia.com). Ollama is the default and requires no key.

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

---

<a id="chinese"></a>

<div align="center">

**AI 驱动的 Telegram 频道和 RSS 订阅源职位抓取系统**

[功能特性](#-功能特性) • [截图](#-截图) • [架构](#-架构) • [安装](#-安装) • [使用方法](#-使用方法) • [API](#-api-端点)

</div>

---

## 🎯 概述

Agentic Job Scraper 是一个自动化系统，从 Telegram 频道、RSS 订阅源（如 V2EX、电鸭社区）和招聘网站（Bossjob.com）获取软件开发职位信息，使用本地 AI (Ollama) 进行分析，并在现代化的 Web 界面中展示。非常适合寻找远程机会的开发者或监控市场趋势的招聘人员。

## ✨ 功能特性

### 核心功能
- **📡 Telegram 集成** — 监控多个 Telegram 频道的职位发布，支持多账号
- **📡 实时监听器** — 从仪表板启动/停止实时消息监听器，即时捕获职位发布
- **🌐 RSS 订阅源支持** — 从 RSS 订阅源获取和分析职位信息（V2EX、电鸭社区等）
- **🎯 Bossjob.com 集成** — 基于 Playwright 的抓取，结构化职位提取（标题、公司、地点、要求）
- **🤖 AI 驱动分析** — 使用 Ollama (qwen2.5:14b 或 qwen2.5:7b) 提取结构化职位/开发者数据
- **📊 实时进度** — 基于 WebSocket 的进度跟踪，每条消息状态更新
- **🔔 浏览器通知** — 发现新职位或开发者时收到通知
- **🛑 停止操作** — 优雅地停止正在进行的分析，提供视觉反馈

### 数据管理
- **🔍 智能搜索** — 服务器端搜索职位（标题、公司、技能、角色）和开发者（姓名、技能、经验）
- **📈 分析仪表板** — 按频道、联系的开发者、申请职位的每日图表
- **🧹 消息清理** — 自动清理 2 天前的消息（保留已申请职位和已联系开发者）
- **🏷 状态跟踪** — 标记职位为已申请，开发者为已联系并添加备注
- **👻 软删除** — 隐藏职位/开发者而非删除，防止重复抓取
- **📋 复制到剪贴板** — 在消息、职位、开发者页面复制原始消息内容

### 用户体验
- **🎨 现代 UI** — 使用 React、TypeScript 和 shadcn/ui 构建的简洁响应式界面
- **🌍 国际化** — 完整的 UI 翻译支持（英语、中文）
- **📱 响应式设计** — 在桌面和移动设备上完美运行
- **⚡ 快速性能** — 可配置并发数的批处理

### AI 简历工具
- **📄 生成简历** — AI 根据职位描述从零生成量身定制的简历，支持 Ollama 和 NVIDIA（流式输出）
- **✨ 优化简历** — 粘贴您现有的简历，AI 针对目标职位进行改写，同时保留真实工作经历
- **🎯 匹配评分** — AI 对您的简历与职位进行匹配评分（0–100），包含已匹配技能、缺失技能、优势和改进建议
- **🔄 实时流式输出** — 简历生成和优化逐 token 流式传输，即时反馈
- **🌐 跨浏览器同步** — WebSocket 广播生成状态，防止多用户同时生成
- **📋 复制与下载** — 将生成/优化的简历复制到剪贴板或下载为 `.txt`

### 高级功能
- **🔐 多账号认证** — 通过交互式认证管理多个 Telegram 账号
- **🎯 远程优先** — 优先考虑远程/居家办公机会
- **🧠 智能过滤** — AI 分析前进行垃圾邮件预过滤
- **📝 自定义提示词** — 为每个网站源自定义提取提示词
- **🇨🇳 V2EX 专用** — 针对中文技术职位的专用提示词，支持翻译
- **💾 Token 监控** — 实时跟踪 Ollama API 调用的 token 使用情况
- **🔄 定时自动分析** — 持续扫描器在获取后自动分析（Telegram 和 RSS）
- **⏱ 健壮的 RSS 获取** — 30 秒超时和 7 天回看窗口
- **🍪 Cookie 扩展** — Chrome 扩展，一键导出 Bossjob.com Cookie
- **🤖 自主智能体模式** — 自动调整调度、自我修复 Playwright 抓取器、自动发现新来源
- **🗑 级联删除** — 删除频道或网站源时自动删除所有关联的消息、职位和开发者

### 自主智能体模式（可选）

当设置 `ENABLE_AUTONOMOUS_MODE=true` 时，系统可作为自主运行的智能体：

- **自适应定时调度** — 根据历史产量自动调整每个来源的抓取频率（10 分钟到 12 小时）
- **自我修复 Playwright** — 轮换指纹/代理，并通过 LLM 恢复损坏的选择器
- **Token 预算守护** — 限制每日 Ollama token 使用量，防止自主学习耗尽资源

适用于现有来源：Telegram 频道、Bossjob.com、电鸭社区、V2EX。

自动投递职位功能**未实现**；自主性仅限于优化现有来源。

## 🚀 计划功能

- [ ] 扩展职位板支持（Bossjob.com 之外的更多招聘网站）
- [ ] 更多 i18n 语言
- [ ] Docker 容器化
- [ ] CI/CD 管道

## 🔄 工作流程

### 高层数据流

```mermaid
graph TD
    A[Telegram 频道] -->|Telethon| B[后端 FastAPI]
    C[RSS 订阅源<br/>V2EX, 电鸭社区] -->|feedparser| B
    B -->|存储到 PostgreSQL| D[(数据库)]
    B -->|WebSocket| E[前端 React]
    F[Ollama LLM] -->|AI 分析| B
    B -->|发送到 Ollama| F
    E -->|用户操作| B
    E -->|显示数据| D
    
    style A fill:#3b82f6,color:#fff
    style C fill:#10b981,color:#fff
    style B fill:#f59e0b,color:#fff
    style D fill:#8b5cf6,color:#fff
    style E fill:#ec4899,color:#fff
    style F fill:#06b6d4,color:#fff
```

**流程概述:**
1. **数据源** — Telegram 频道和 RSS 订阅源提供原始职位发布
2. **后端处理** — FastAPI 获取、存储和分析消息
3. **AI 分析** — Ollama 从消息中提取结构化职位/开发者数据
4. **实时更新** — WebSocket 将进度流式传输到前端
5. **用户界面** — React 显示结果并提供搜索和过滤

### 详细数据流

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant Telegram
    participant RSS
    participant Ollama
    participant DB

    User->>Frontend: 添加频道/网站
    Frontend->>Backend: POST /api/channels 或 /api/website-sources
    Backend->>DB: 存储频道/网站信息

    User->>Frontend: 点击获取
    Frontend->>Backend: POST /api/fetch 或 /api/website-sources/{id}/fetch
    Backend->>Telegram: 获取消息 (Telethon)
    Telegram-->>Backend: 返回消息
    Backend->>RSS: 获取 RSS 订阅源 (feedparser)
    RSS-->>Backend: 返回订阅源条目
    Backend->>DB: 存储消息，状态为"pending"

    User->>Frontend: 点击分析
    Frontend->>Backend: POST /api/analyze 或 /api/website-sources/{id}/analyze
    Backend->>DB: 获取待分析消息（按日期降序）
    loop 对于每条消息（顺序处理）
        Backend->>Ollama: 发送消息进行分析
        Ollama-->>Backend: 返回职位/开发者数据
        Backend->>Frontend: WebSocket 进度更新
        Backend->>DB: 存储提取的职位/开发者
        Backend->>DB: 更新消息状态为"analyzed"
    end
    Backend-->>Frontend: 分析完成
    Frontend->>User: 显示结果并发送通知

    User->>Frontend: 查看仪表板
    Frontend->>Backend: GET /api/stats, /api/daily-jobs
    Backend->>DB: 查询分析数据
    Backend-->>Frontend: 返回统计数据
    Frontend->>User: 显示图表
```

**关键流程细节:**
- **获取阶段** — 消息存储时 `analysis_status="pending"`
- **分析阶段** — 消息逐条顺序处理
- **进度跟踪** — WebSocket 每条消息发送实时更新
- **通知** — 职位/开发者发现和完成时发送浏览器警报
- **数据持久化** — 职位和开发者与原始消息分开存储

### 系统架构

```mermaid
graph TB
    subgraph Frontend["🎨 前端层"]
        direction TB
        A[React UI<br/>仪表板、频道、职位、开发者]
        B[WebSocket 客户端<br/>实时进度更新]
        C[API 客户端<br/>RESTful API 调用]
        D[通知管理器<br/>浏览器警报]
        E[搜索与过滤<br/>客户端 UI]
    end

    subgraph Backend["⚙ 后端层"]
        direction TB
        F[FastAPI 服务器<br/>REST API 端点]
        G[WebSocket 服务器<br/>进度广播]
        H[任务编排器<br/>后台任务]
        I[数据层<br/>SQLAlchemy ORM]
        J[Telegram 处理器<br/>多账号管理器]
        K[RSS 爬虫<br/>订阅源解析器]
        L[AI 服务<br/>Ollama 集成]
        M[分析引擎<br/>每日统计]
    end

    subgraph External["🌐 外部服务"]
        direction TB
        N[Telegram API<br/>消息获取]
        O[RSS 订阅源<br/>V2EX、电鸭社区]
        P[Ollama LLM<br/>qwen2.5:14b/7b]
        Q[PostgreSQL<br/>数据持久化]
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

**组件职责:**

#### 前端层
- **React UI** — 主应用程序界面，包含仪表板、频道、职位、开发者、消息和设置页面
- **WebSocket 客户端** — 维持持久连接，在分析操作期间提供实时进度更新
- **API 客户端** — 处理所有 RESTful API 调用，具有适当的错误处理和加载状态
- **通知管理器** — 管理职位/开发者发现和分析完成的浏览器通知
- **搜索与过滤** — 用于过滤和搜索职位和开发者的客户端 UI 组件

#### 后端层
- **FastAPI 服务器** — 为所有 CRUD 操作和业务逻辑提供 RESTful API 端点
- **WebSocket 服务器** — 在长时间运行的任务期间向连接的客户端广播进度更新
- **任务编排器** — 管理获取、分析和 cron 任务的后台任务
- **数据层** — SQLAlchemy 异步 ORM，使用 PostgreSQL 进行所有数据库操作
- **Telegram 处理器** — 基于 Telethon 的客户端，用于获取消息并支持多账号
- **RSS 爬虫** — 基于 feedparser 的 RSS 订阅源获取器，具有网站源管理功能
- **AI 服务** — Ollama 集成，用于 AI 驱动的职位/开发者提取，具有 token 跟踪功能
- **分析引擎** — 聚合每日统计信息，包括发布的职位、联系的开发者和申请的职位

#### 外部服务
- **Telegram API** — 官方 Telegram API，用于消息获取和账号认证
- **RSS 订阅源** — 来自职位板的外部 RSS 订阅源（V2EX、电鸭社区等）
- **Ollama LLM** — 运行 qwen2.5:14b 或 qwen2.5:7b 的本地 LLM 服务，用于 AI 分析
- **PostgreSQL** — 关系数据库，用于所有应用程序数据的持久存储

**数据流模式:**
- **获取流程** — Telegram/RSS → 后端 → 数据库 → WebSocket → 前端
- **分析流程** — 数据库 → Ollama → 后端 → 数据库 → WebSocket → 前端
- **查询流程** — 前端 → API → 数据库 → API → 前端
- **通知流程** — 后端 → WebSocket → 前端 → 浏览器通知

## 截图

### 仪表板
![仪表板](screenshots/Dashboard.png)

### 频道
![频道](screenshots/Channels.png)

### 添加频道
![添加频道](screenshots/Channels%20-%20add.png)

### 消息
![消息](screenshots/Messages.png)

### 职位
![职位](screenshots/Job.png)

### 职位详情
![职位详情](screenshots/Job%20Detail%202.png)

### 开发者
![开发者](screenshots/Developers.png)

### Telegram 账号
![Telegram 账号](screenshots/Telegrams.png)

### 网站
![网站](screenshots/Websites.png)

### 后端 API
![后端 API](screenshots/Backend.png)

## 👥 适用人群

### 主要用户
- **👨‍💻 软件开发者** — 寻找远程/居家办公机会的开发者，希望在一个地方监控多个 Telegram 职位频道
- **🎯 技术招聘人员** — 监控竞争对手职位发布的招聘人员，跟踪市场趋势
- **📢 频道管理员** — 分析其频道职位发布效果和社区参与度的管理员

### 次要用户
- **🌍 远程工作爱好者** — 在本地就业市场有限的地区寻找远程机会的开发者
- **🤖 AI/ML 爱好者** — 对本地 LLM (Ollama) 在内容分析和网页抓取集成中的实际应用感兴趣的开发者

## ⚠ 项目状态

> **注意:** 本项目专为个人使用设计。虽然功能完整，但可能缺少一些企业级最佳实践：

**当前状态:**
- ✅ 功能完整，可用于个人求职和监控
- ✅ AI 驱动网页抓取的坚实基础
- ✅ 持续开发和维护

**缺少的企业功能:**
- ⬜ 全面的测试套件（单元测试、集成测试、E2E）
- ⬜ CI/CD 管道配置
- ⬜ 代码质量工具（ESLint、Prettier、Black、isort）
- ⬜ 预提交钩子
- ⬜ Docker 容器化
- ⬜ 数据库迁移管理（Alembic）
- ⬜ 安全加固（速率限制、输入验证）
- ⬜ 监控和日志基础设施
- ⬜ 备份和灾难恢复文档

您可以根据需要扩展其他功能和最佳实践。

## 🏗 架构

### 后端技术栈
- **FastAPI** — 用于高性能 API 端点的异步 Web 框架
- **SQLAlchemy** — 带 PostgreSQL 的异步 ORM，用于数据库操作
- **Telethon** — Telegram 客户端，用于获取消息和认证
- **Ollama** — 本地 LLM，用于 AI 驱动的消息分析
- **WebSocket** — 实时进度更新到前端
- **feedparser** — RSS 订阅源解析，用于网站源

### 前端技术栈
- **React 18** — 带有 hooks 的现代 React，用于状态管理
- **TypeScript** — 类型安全开发，完整类型覆盖
- **Vite** — 快速构建工具和开发服务器，支持 HMR
- **shadcn/ui** — 基于 Radix UI 的美观、可访问的 UI 组件
- **Tailwind CSS** — 实用优先的 CSS 框架，快速样式
- **React Router** — 客户端路由，支持懒加载
- **react-i18next** — 国际化（英语、中文）

## 📋 前置要求

- **Python 3.10+** — 后端运行时
- **Node.js 18+** — 前端运行时
- **PostgreSQL 14+** — 数据库（或 SQLite 用于开发）
- **Ollama** — 本地 LLM，需安装 qwen2.5:14b 或 qwen2.5:7b 模型
- **Telegram API 凭证** — 可选，可通过 UI 添加

## 🛠 安装

### 后端设置

1. **导航到后端目录：**
```bash
cd backend
```

2. **创建虚拟环境：**
```bash
python -m venv env
env\Scripts\activate  # Windows
source env/bin/activate  # Linux/Mac
```

3. **安装依赖：**
```bash
pip install -r requirements.txt
```

4. **配置环境变量：**
```bash
cp .env.example .env
```

编辑 `.env` 填入您的凭证：
```env
# Telegram API 凭证（可选 - 可通过 UI 添加）
# 从 https://my.telegram.org/apps 获取
# TELEGRAM_API_ID=your_api_id_here
# TELEGRAM_API_HASH=your_api_hash_here
# TELEGRAM_PHONE=+1234567890

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b
DATABASE_URL=postgresql+asyncpg://user:password@localhost/job_scraper
```

> **提示:** Telegram 凭证是可选的。您可以通过 Web UI 的"Telegram Accounts"完全添加和管理多个 Telegram 账号，支持交互式认证（在浏览器中输入验证码和 2FA 密码）。

5. **初始化数据库：**
```bash
python reset_db.py
```

这将创建所有必要的表，包括用于多账号支持的 `telegram_accounts` 表。

### 前端设置

1. **导航到前端目录：**
```bash
cd frontend
```

2. **安装依赖：**
```bash
npm install
```

3. **配置环境变量：**
```bash
cp .env.example .env
```

编辑 `.env` 填入您的 API URL：
```env
# 本地开发（独立的后端服务器）
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000/ws/progress

# 生产环境（相同域名 - FastAPI 提供静态文件）
VITE_API_BASE_URL=
VITE_WS_BASE_URL=

# 对于 ngrok
VITE_API_BASE_URL=https://your-ngrok-url.ngrok-free.app
VITE_WS_BASE_URL=wss://your-ngrok-url.ngrok-free.app/ws/progress
```

### Ollama 设置

1. **从 [ollama.com](https://ollama.com) 安装 Ollama**

2. **拉取推荐模型：**
```bash
ollama pull qwen2.5:14b  # 更高精度
# 或
ollama pull qwen2.5:7b   # 更快性能
```

3. **启动 Ollama 服务器：**
```bash
ollama serve
```

> **💡 提示：** 更大的模型能显著提升推理质量。如果硬件允许，建议使用 `qwen2.5:14b` 或更高版本（如 `qwen2.5:32b`），以获得更准确的职位/开发者信息提取。较小的模型如 `7b` 速度更快，但可能遗漏细节或产生低置信度的分类结果。

## 🚀 运行应用程序

### 开发模式

**启动后端:**
```bash
cd backend
python web_app.py
```
后端运行在 `http://localhost:8000`

**启动前端:**
```bash
cd frontend
npm run dev
```
前端运行在 `http://localhost:5173`

### 生产模式

#### 选项 1: 从 FastAPI 提供静态文件（最简单）

1. **构建前端:**
```bash
cd frontend
npm run build
```

2. **运行后端**（同时提供 API 和前端）:
```bash
cd backend
python web_app.py
```

在 `http://localhost:8000` 访问

#### 选项 2: 单独部署（Nginx + Gunicorn）

1. **构建前端:**
```bash
cd frontend
npm run build
```

2. **配置 Nginx:**
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

3. **使用 Gunicorn 运行后端:**
```bash
cd backend
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker web_app:app --bind 0.0.0.0:8000
```

### 使用 ngrok 进行远程访问

1. **启动后端:**
```bash
cd backend
python web_app.py
```

2. **在单独终端启动 ngrok:**
```bash
ngrok http 8000
```

3. **复制 ngrok URL**（例如 `https://abc123.ngrok-free.app`）

4. **配置前端 `.env`:**
```env
VITE_API_BASE_URL=https://abc123.ngrok-free.app
VITE_WS_BASE_URL=wss://abc123.ngrok-free.app/ws/progress
```

5. **启动前端:**
```bash
cd frontend
npm run dev
```

## 📖 使用方法

### 设置 Telegram 账号

1. **获取 API 凭证** — 访问 [my.telegram.org/apps](https://my.telegram.org/apps) 创建应用程序并获取 `api_id` 和 `api_hash`

2. **通过 UI 添加账号:**
   - 导航到侧边栏中的"Telegram Accounts"
   - 点击"Add Account"
   - 输入您的 API ID、API Hash 和电话号码
   - 点击"Add Account"

3. **认证您的账号:**
   - 点击未认证账号旁边的"Authenticate"按钮
   - 输入发送到您手机的验证码
   - 如果启用了 2FA，输入您的 2FA 密码
   - 认证后，账号将显示"Authenticated"徽章

4. **管理多个账号:**
   - 根据需要添加任意数量的 Telegram 账号
   - 切换账号为活跃/非活跃状态
   - 删除您不再需要的账号
   - 获取频道时选择要使用的账号

### 使用应用程序

1. **添加频道** — 进入 Channels 页面并添加要监控的 Telegram 频道
2. **添加网站源** — 进入 Websites 页面并添加 RSS 订阅源 URL（V2EX、电鸭社区等）
3. **选择账号** — 获取频道时，选择要使用的 Telegram 账号（如果有多个）
4. **获取消息** — 点击"Fetch"从频道或 RSS 订阅源检索最新消息
5. **分析** — 点击"Analyze"使用 AI 处理消息并提取职位/开发者信息
6. **停止分析** — 点击"Stop"优雅地停止正在进行的分析（显示"Stopping..."状态）
7. **监控进度** — 查看实时进度，包括 token 使用情况和每条消息状态
8. **查看结果** — 浏览 Jobs 和 Developers 页面查看提取的信息
9. **跟踪进度** — 标记职位为已申请或开发者为已联系并添加备注
10. **持续扫描** — 启用 cron 任务进行自动定期获取和分析
11. **分析** — 在仪表板上查看按频道、联系的开发者和申请职位的每日图表
12. **清理** — 2 天前的消息在启动时自动清理（保留已申请职位和已联系开发者）
13. **复制消息** — 在消息、职位、开发者页面点击复制按钮复制原始消息文本
14. **自定义提示词** — 为每个网站源自定义提取提示词以提高准确性
15. **V2EX 配置** — 添加 V2EX 时设置 `site_type="v2ex"` 以使用专用的中文职位提示词
16. **AI 简历工具** — 在任意职位详情中点击「Generate Resume」打开 AI 简历工具对话框：
    - **Generate（生成）** — 从零生成量身定制的简历，可复制或下载
    - **Enhance（优化）** — 粘贴您的现有简历，AI 针对该职位进行改写
    - **Match Score（匹配评分）** — 粘贴您的简历，获取 0–100 匹配分数及技能分析
    - > **💡 提示：** 简历工具默认使用 Ollama，无需配置。如要使用 NVIDIA，请在后端 `.env` 中设置 `RESUME_PROVIDER=nvidia` 和 `NVIDIA_API_KEY`。可在 [build.nvidia.com](https://build.nvidia.com) 免费获取 API Key。

## 🔌 API 端点

### 频道
- `GET /api/channels` — 列出所有频道
- `POST /api/channels` — 添加新频道
- `DELETE /api/channels/{id}` — 删除频道

### Telegram 账号
- `GET /api/telegram-accounts` — 列出所有 Telegram 账号
- `POST /api/telegram-accounts` — 添加新 Telegram 账号
- `DELETE /api/telegram-accounts/{id}` — 删除 Telegram 账号
- `PATCH /api/telegram-accounts/{id}/toggle-active` — 切换账号活跃状态
- `POST /api/telegram-accounts/authenticate` — 启动认证过程
- `POST /api/telegram-accounts/verify-code` — 验证认证代码
- `POST /api/telegram-accounts/verify-password` — 验证 2FA 密码

### 网站源
- `GET /api/website-sources` — 列出所有网站源
- `POST /api/website-sources` — 添加新网站源（RSS 订阅源）
- `DELETE /api/website-sources/{id}` — 删除网站源
- `PUT /api/website-sources/{id}` — 更新网站源（自定义提示词、site_type）
- `POST /api/website-sources/{id}/fetch` — 从网站源获取 RSS 内容
- `POST /api/website-sources/fetch-all` — 从所有活跃网站源获取
- `POST /api/website-sources/{id}/analyze` — 分析网站源的消息
- `POST /api/website-sources/analyze-all` — 分析所有网站源的消息
- `POST /api/website-sources/{id}/stop` — 停止网站源的正在进行的操作

> **注意:** 添加 V2EX 源时设置 `site_type="v2ex"` 以使用专用的中文职位提示词。

### 消息
- `GET /api/messages` — 列出消息（带分页）
- `GET /api/messages/{id}` — 获取消息详情

### 职位
- `GET /api/jobs` — 列出提取的职位（带搜索过滤器）
- `GET /api/jobs/{id}` — 获取职位详情
- `POST /api/jobs/{id}/toggle-applied` — 标记职位为已申请/未申请
- `DELETE /api/jobs/{id}` — 隐藏职位（软删除）

### 简历工具（NVIDIA API）
- `POST /api/resume/generate` — 为职位生成量身简历（流式 SSE）
- `POST /api/resume/enhance` — 优化现有简历使其匹配职位（流式 SSE）
- `POST /api/resume/score` — 评估简历与职位的匹配度（返回 JSON 详细分析）

### 开发者
- `GET /api/developers` — 列出提取的开发者（带搜索过滤器）
- `GET /api/developers/{id}` — 获取开发者详情
- `POST /api/developers/{id}/toggle-contacted` — 标记开发者为已联系/未联系
- `DELETE /api/developers/{id}` — 隐藏开发者（软删除）

### 操作
- `POST /api/fetch/{channel_id}` — 从频道获取消息
- `POST /api/analyze/{channel_id}` — 分析频道中的消息
- `POST /api/stop-analyze?channel_id={id}` — 停止频道的正在进行的分析
- `POST /api/listener/start` — 启动实时 Telegram 消息监听器
- `POST /api/listener/stop` — 停止实时 Telegram 消息监听器
- `POST /api/listener/add-channels` — 向运行中的监听器添加频道
- `POST /api/listener/remove-channels` — 从运行中的监听器移除频道
- `POST /api/cron/start` — 启动持续扫描器
- `POST /api/cron/stop` — 停止持续扫描器
- `POST /api/cleanup/old-messages?days={n}` — 删除 N 天前的消息

### 分析
- `GET /api/daily-jobs?days={n}` — 按频道的每日职位发布（最近 N 天）
- `GET /api/daily-developers-contacted?days={n}` — 每日联系的开发者（最近 N 天）
- `GET /api/daily-jobs-applied?days={n}` — 每日申请的职位（最近 N 天）

### WebSocket
- `WS /ws/progress` — 实时进度更新

## 📁 项目结构

```
agentic-job-scraper/
├── backend/
│   ├── app/
│   │   ├── models.py          # 数据库模型（Job, Developer, Channel 等）
│   │   ├── routes/            # API 端点（channels, jobs, developers 等）
│   │   ├── connection.py      # 数据库和 WebSocket 连接
│   │   └── tasks.py           # 后台任务（fetch, analyze, cron）
│   ├── services/
│   │   └── ollama_service.py  # AI 分析服务
│   ├── telegram_processor/    # Telegram 客户端（Telethon）
│   ├── web_crawler/           # RSS 订阅源爬虫和提取器
│   │   ├── rss_fetcher.py     # RSS 订阅源获取
│   │   ├── rss_extractor.py   # 基于 Ollama 的提取
│   │   ├── models.py          # 提取的 Pydantic 模型
│   │   └── prompts.py         # 提取提示词
│   └── web_app.py             # FastAPI 入口点
├── frontend/
│   ├── src/
│   │   ├── components/        # React 组件（Layout, UI）
│   │   ├── pages/             # 页面组件（Dashboard, Channels 等）
│   │   ├── services/          # API 客户端
│   │   ├── hooks/             # 自定义 hooks（useWebSocketProgress）
│   │   └── locales/           # i18n 翻译文件（en.json, zh.json）
│   └── package.json
└── README.md
```

## ⚙ 配置

### Telegram 账号管理

应用程序支持通过 Web UI 管理多个 Telegram 账号。每个账号在数据库中存储：

- **API ID 和 API Hash** — 来自 my.telegram.org 的凭证
- **电话号码** — 与账号关联的电话号码
- **会话名称** — 会话文件的唯一标识符
- **认证状态** — 账号是否已认证
- **活跃状态** — 账号当前是否可用于使用

**认证流程:**
1. 通过 UI 添加账号凭证
2. 点击"Authenticate"启动流程
3. 输入发送到您手机的验证码
4. 如果启用了 2FA，输入您的 2FA 密码
5. 账号被标记为已认证并准备使用

**会话管理:**
- 会话文件存储在 `backend/session/`
- 每个账号都有自己的会话文件
- 会话在服务器重启后持久化
- 仅在会话被删除或过期时才需要重新认证

### Telegram API

从 [my.telegram.org/apps](https://my.telegram.org/apps) 获取您的 API 凭证。您可以为不同账号创建多个应用程序。

### Ollama 配置

**推荐模型:**
- `qwen2.5:14b` — 更高精度，用于复杂提取
- `qwen2.5:7b` — 更快性能，用于高容量处理

**配置选项:**
- 远程 Ollama 实例支持
- GPU 加速以加快处理速度
- 顺序处理（逐条分析，无并发冲突）
- 实时 token 使用跟踪（输入/输出/总 token）
- 垃圾邮件预过滤器，在 Ollama 之前跳过非技术消息
- V2EX 专用提示词用于中文职位，支持翻译
- 通用 RSS 提示词用于其他网站源

**环境变量:**
```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b
```

### NVIDIA API（简历工具）

简历工具默认使用 **Ollama**（`RESUME_PROVIDER=ollama`），无需 API Key 即可使用。切换到 NVIDIA：

```env
RESUME_PROVIDER=nvidia
NVIDIA_API_KEY=your_nvidia_api_key_here
```

> 在 [build.nvidia.com](https://build.nvidia.com) 免费获取 NVIDIA API Key。默认使用 Ollama，无需配置 API Key。

**高级选项**（在 `ollama_service.py` 中）:
- `num_predict` — 最大生成 token 数（根据消息长度 + 系统提示词动态调整）
- `num_ctx` — 上下文窗口大小（根据消息长度 + 系统提示词动态调整）
- `num_gpu` — GPU 层数卸载（默认：99，完全 GPU 卸载）
- `keep_alive` — 将模型保留在内存中（默认：-1，无限期）
- `timeout` — 请求超时（默认：180s）

**动态上下文调整:**
- 根据消息长度加上系统提示词长度自动计算 `num_ctx` 和 `num_predict`
- 四个层级：<512 字符 (1024/512)，<1024 字符 (2048/1024)，<2048 字符 (4096/2048)，≥2048 字符 (8192/4096)

**RSS 提取器选项**（在 `rss_extractor.py` 中）:
- `MAX_CHARS` — 内容分块大小（默认：3000，约 1000-1500 token）
- `temperature` — 低温度用于事实提取（默认：0.1）

### 数据库

- **PostgreSQL** 带异步支持（或 SQLite 用于开发）
- 为性能配置的连接池
- 启动时自动创建表
- 会话文件存储在 `backend/session/` 目录

### 数据库迁移

更新应用程序时，您可能需要运行数据库迁移：

```bash
cd backend/migrations
for f in *.sql; do psql -U your_username -d job_scraper -f "$f"; done
```

可用迁移：
- `add_telegram_accounts.sql` — 添加 Telegram 账号表
- `add_phone_code_hash.sql` — 添加电话代码哈希列
- `add_telegram_account_id_to_channels.sql` — 添加 telegram_account_id 到频道
- `make_developer_message_id_nullable.sql` — 使 developer.message_id 可为空
- `add_channel_name_to_jobs.sql` — 添加 channel_name 列到职位
- `add_last_fetch_tracking.sql` — 添加最后获取跟踪列
- `add_message_analysis_flags.sql` — 添加消息分析标志
- `add_operations_table.sql` — 添加操作跟踪表
- `add_analysis_runs_table.sql` — 添加分析运行表
- `migrate_add_skip_reason.sql` — 添加 skip_reason 列到消息
- `migrate_operations_cascade.sql` — 添加操作级联删除
- `fix_skills_default.sql` — 修复 skills 列默认值
- `add_is_hidden_to_jobs_developers.sql` — 添加 is_hidden 列用于软删除

## 🔧 故障排除

### Telegram 认证问题

**未收到代码:**
- 检查电话号码包含国家代码（例如 +1234567890）
- 确保您没有在另一台设备上使用相同号码登录 Telegram
- 尝试在认证对话框中点击"Resend Code"
- 检查 Telegram 是否阻止验证请求（等待几分钟）

**认证会话过期:**
- 点击"Authenticate"再次请求新代码
- 旧会话将自动清理

**2FA 密码错误:**
- 确保您输入的是 Telegram 2FA 密码（不是手机密码）
- 检查拼写错误并重试
- 通过 Telegram 重置 2FA 密码（如果忘记）

**成功认证后账号显示为未认证:**
- 刷新页面以查看更新状态
- 检查后端日志中是否有认证期间的错误
- 如果会话中断，请尝试再次认证

### Ollama 连接问题
- 确保 Ollama 服务器正在运行: `ollama serve`
- 检查 `.env` 中的 OLLAMA_BASE_URL
- 验证模型已安装: `ollama list`
- 确保远程 Ollama 实例可从您的网络访问

### Telegram 洪水错误
- 系统自动处理 FloodWaitError
- 将在所需等待时间后重试
- 无需手动干预
- 减少获取频率如果错误持续存在

### 数据库连接
- 验证 PostgreSQL 正在运行
- 检查 `.env` 中的 DATABASE_URL
- 确保数据库存在: `createdb job_scraper`
- 检查数据库凭证是否正确

### 会话文件问题
- 删除 `backend/session/` 中的会话文件如果认证失败并显示"Two-steps verification is enabled"
- 会话文件命名为 `session_+1234567890.session`
- 认证流程会自动清理旧会话

### 频道获取问题
- 确保您至少有一个已认证且活跃的 Telegram 账号
- 检查下拉列表中选择的账号是否活跃
- 验证频道用户名是否正确（不带 @ 符号）
- 检查后端日志中的具体错误消息
- 确保所选 Telegram 账号有权访问该频道
- **没有公开用户名的频道：** 监听器现在支持没有公开用户名的频道，通过使用其内部 Telegram ID。当收到消息时，这些频道将自动在数据库中创建。

### 前端 API 连接问题
- 检查后端是否在预期端口上运行（默认：8000）
- 验证前端 `.env` 中的 VITE_API_BASE_URL
- 检查浏览器控制台是否有 CORS 错误
- 确保 WebSocket URL 正确（VITE_WS_BASE_URL）

## 📄 许可证

MIT

## 🤝 贡献

欢迎贡献！请随时提交 Pull Request。
