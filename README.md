# Agentic Job Scraper

An automated job scraping system that fetches software development job postings from Telegram channels and RSS feeds (e.g., V2EX, 电鸭社区), analyzes them using AI (Ollama), and presents them in a modern web interface.

## Features

- **Automated Fetching**: Continuously monitors Telegram channels for new job postings
- **Website Source Support**: Fetch and analyze job postings from RSS feeds (e.g., V2EX, 电鸭社区)
- **AI-Powered Analysis**: Uses Ollama (qwen2.5 recommended) to analyze messages and extract job/developer information
- **Real-time Progress**: WebSocket-based progress tracking for analysis operations
- **Token Usage Monitoring**: Real-time token usage tracking for Ollama API calls
- **Stop Analysis**: Gracefully stop ongoing analysis operations with visual feedback
- **Concurrent Processing**: Batch processing with configurable concurrency for faster analysis
- **Per-Message Status**: Visual indicators for each analyzed message (success, JSON cutoff, failed, other)
- **Analytics Dashboard**: Daily charts for job postings by channel, developers contacted, and jobs applied
- **Message Cleanup**: Remove messages older than N days (associated jobs deleted, developers preserved)
- **Modern UI**: Clean, responsive interface built with React, TypeScript, and shadcn/ui
- **Multi-language Support**: Analyzes job postings in multiple languages (English, Chinese, etc.)
- **Smart Filtering**: Spam pre-filter before sending to Ollama for faster processing
- **Remote Jobs Focus**: Prioritizes remote/work-from-home opportunities
- **Multi-Account Support**: Manage multiple Telegram accounts dynamically through the UI with interactive authentication
- **Custom Extraction Prompts**: Customize Ollama prompts per website source for better extraction accuracy

## Planned Features

- **Extended Job Board Support**: Add more job boards and career sites based on user demand
- **Smart Content Fetching**: Use Playwright to fetch full content from job posting detail pages for better analysis

## Workflow

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
    Backend->>DB: Store messages

    User->>Frontend: Click Analyze
    Frontend->>Backend: POST /api/analyze or /api/website-sources/{id}/analyze
    Backend->>DB: Get pending messages
    loop For each message batch
        Backend->>Ollama: Send message for analysis
        Ollama-->>Backend: Return job/developer data
        Backend->>Frontend: WebSocket progress update
        Backend->>DB: Store extracted jobs/developers
    end
    Backend-->>Frontend: Analysis complete
    Frontend->>User: Display results

    User->>Frontend: View Dashboard
    Frontend->>Backend: GET /api/stats, /api/daily-jobs
    Backend->>DB: Query analytics data
    Backend-->>Frontend: Return stats
    Frontend->>User: Display charts
```

### System Architecture

```mermaid
graph LR
    subgraph Frontend
        A[React UI]
        B[WebSocket Client]
        C[API Client]
    end

    subgraph Backend
        D[FastAPI Server]
        E[WebSocket Server]
        F[Telegram Client]
        G[RSS Fetcher]
        H[Ollama Service]
        I[Task Scheduler]
    end

    subgraph External Services
        J[Telegram API]
        K[RSS Feeds]
        L[Ollama LLM]
        M[PostgreSQL]
    end

    A <--> C
    A <--> B
    C <--> D
    B <--> E
    F <--> J
    G <--> K
    H <--> L
    D <--> M
    F --> D
    G --> D
    H --> D
    I --> D
```

## Screenshots

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

## Who is this for?

**Primary Users:**
- **Software Developers Job Hunting** - Developers looking for remote/work-from-home opportunities who want to monitor multiple Telegram job channels in one place
- **Tech Recruiters/Hiring Managers** - Recruiters monitoring competitor job postings, hiring managers tracking market trends and salary information
- **Telegram Channel Managers** - Admins analyzing their channel's job posting effectiveness and community engagement

**Secondary Users:**
- **Remote Work Enthusiasts** - Developers specifically seeking remote opportunities, especially in regions with limited local job markets
- **AI/ML Enthusiasts** - Developers interested in practical applications of local LLMs (Ollama) for content analysis and web scraping integration

## Project Status

**Note:** This project is designed for personal use. While it provides a solid foundation for automated job scraping and AI analysis, it is not 100% production-ready and may be missing some enterprise-grade best practices such as:

- Comprehensive testing suite (unit, integration, E2E tests)
- CI/CD pipeline configuration
- Code quality tools (ESLint, Prettier, Black, isort)
- Pre-commit hooks for automated checks
- Containerization (Docker, docker-compose)
- Database migration management (Alembic)
- Security hardening (rate limiting, input validation)
- Monitoring and logging infrastructure
- Backup and disaster recovery documentation

However, the project is fully functional and can be used effectively for personal job hunting, monitoring Telegram channels, and learning about AI-powered web scraping. Feel free to extend it with additional features and best practices as needed for your use case.

## Architecture

### Backend (FastAPI + Python)
- **FastAPI**: Async web framework for API endpoints
- **SQLAlchemy**: Async ORM with PostgreSQL
- **Telethon**: Telegram client for fetching messages
- **Ollama**: Local LLM for message analysis
- **WebSocket**: Real-time progress updates

### Frontend (React + TypeScript)
- **React 18**: Modern React with hooks
- **TypeScript**: Type-safe development
- **Vite**: Fast build tool and dev server
- **shadcn/ui**: Beautiful, accessible UI components
- **Tailwind CSS**: Utility-first styling
- **React Router**: Client-side routing

## Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- Ollama (with Mistral model installed)
- Telegram API credentials (optional - can be added via UI)

## Installation

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv env
env\Scripts\activate  # On Windows
source env/bin/activate  # On Linux/Mac
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```env
# Telegram API credentials (optional - can be added via UI in Telegram Accounts page)
# Get from https://my.telegram.org/apps
# TELEGRAM_API_ID=your_api_id_here
# TELEGRAM_API_HASH=your_api_hash_here
# TELEGRAM_PHONE=+1234567890

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
DATABASE_URL=postgresql+asyncpg://user:password@localhost/job_scraper
```

**Note:** Telegram credentials are now optional. You can add and manage multiple Telegram accounts entirely through the web UI at "Telegram Accounts" in the sidebar. The UI supports interactive authentication (entering verification code and 2FA password directly in the browser). If you prefer to use environment variables, uncomment and fill in the Telegram credentials above.

5. Initialize the database:
```bash
python reset_db.py
```

This will create all necessary tables including the new `telegram_accounts` table for multi-account support.

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Configure environment variables (optional):
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

1. Install Ollama from [ollama.com](https://ollama.com)
2. Pull the Mistral model:
```bash
ollama pull mistral
```

3. Start Ollama server:
```bash
ollama serve
```

## Running the Application

### Development Mode

**Start the Backend:**
```bash
cd backend
python web_app.py
```
The backend will run on `http://localhost:8000`

**Start the Frontend:**
```bash
cd frontend
npm run dev
```
The frontend will run on `http://localhost:5173`

### Production Mode

**Option 1: Serve Static Files from FastAPI (Simplest)**

1. Build the frontend:
```bash
cd frontend
npm run build
```

2. Run the backend (it will serve both API and frontend):
```bash
cd backend
python web_app.py
```

Access the application at `http://localhost:8000`

**Option 2: Separate Deployment (Nginx + Gunicorn)**

1. Build the frontend:
```bash
cd frontend
npm run build
```

2. Configure Nginx to serve the frontend and proxy API requests:
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

3. Run backend with Gunicorn:
```bash
cd backend
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker web_app:app --bind 0.0.0.0:8000
```

### Using ngrok for Remote Access

If you want to access the application remotely using ngrok:

1. Start the backend:
```bash
cd backend
python web_app.py
```

2. In a separate terminal, start ngrok:
```bash
ngrok http 8000
```

3. Copy the ngrok URL (e.g., `https://abc123.ngrok-free.app`)

4. Configure the frontend to use the ngrok URL:
```bash
cd frontend
cp .env.example .env
```

Edit `.env`:
```env
VITE_API_BASE_URL=https://abc123.ngrok-free.app
VITE_WS_BASE_URL=wss://abc123.ngrok-free.app/ws/progress
```

5. Start the frontend:
```bash
npm run dev
```

Now the frontend will connect to your backend through the ngrok tunnel.

## Usage

### Setting Up Telegram Accounts

1. **Get API Credentials**: Visit [my.telegram.org/apps](https://my.telegram.org/apps) to create a new application and obtain your `api_id` and `api_hash`

2. **Add Account via UI**:
   - Navigate to "Telegram Accounts" in the sidebar
   - Click "Add Account"
   - Enter your API ID, API Hash, and phone number
   - Click "Add Account"

3. **Authenticate Your Account**:
   - Click the "Authenticate" button next to your unauthenticated account
   - A dialog will appear - enter the verification code sent to your phone
   - If you have 2FA enabled, enter your 2FA password when prompted
   - Once authenticated, the account will show an "Authenticated" badge

4. **Manage Multiple Accounts**:
   - Add as many Telegram accounts as you need
   - Toggle accounts as active/inactive
   - Delete accounts you no longer need
   - Select which account to use when fetching channels

### Using the Application

1. **Add Channels**: Go to the Channels page and add Telegram channels to monitor
2. **Add Website Sources**: Go to the Websites page and add RSS feed URLs (e.g., V2EX, 电鸭社区)
3. **Select Account**: When fetching channels, select which Telegram account to use (if you have multiple)
4. **Fetch Messages**: Click "Fetch" to retrieve recent messages from channels or RSS feeds
5. **Analyze**: Click "Analyze" to process messages with AI and extract job/developer info
6. **Stop Analysis**: Click "Stop" to gracefully stop an ongoing analysis operation (shows "Stopping..." state)
7. **Monitor Progress**: View real-time progress including token usage and per-message status (success/cutoff/failed)
8. **View Results**: Browse Jobs and Developers pages to see extracted information
9. **Track Progress**: Use the status indicators to mark jobs as applied or developers as contacted
10. **Continuous Scanning**: Enable the cron job for automatic periodic fetching
11. **Analytics**: View daily charts on the Dashboard for job postings by channel, developers contacted, and jobs applied
12. **Cleanup**: Use "Cleanup Old Messages" in Quick Actions to remove messages older than N days
13. **Custom Prompts**: Customize extraction prompts per website source for better accuracy

## API Endpoints

### Channels
- `GET /api/channels` - List all channels
- `POST /api/channels` - Add a new channel
- `DELETE /api/channels/{id}` - Delete a channel

### Telegram Accounts
- `GET /api/telegram-accounts` - List all Telegram accounts
- `POST /api/telegram-accounts` - Add a new Telegram account
- `DELETE /api/telegram-accounts/{id}` - Delete a Telegram account
- `PATCH /api/telegram-accounts/{id}/toggle-active` - Toggle account active status
- `POST /api/telegram-accounts/authenticate` - Start authentication process (sends code to phone)
- `POST /api/telegram-accounts/verify-code` - Verify authentication code
- `POST /api/telegram-accounts/verify-password` - Verify 2FA password

### Website Sources
- `GET /api/website-sources` - List all website sources
- `POST /api/website-sources` - Add a new website source (RSS feed)
- `DELETE /api/website-sources/{id}` - Delete a website source
- `PUT /api/website-sources/{id}` - Update a website source (including custom extraction prompt)
- `POST /api/website-sources/{id}/fetch` - Fetch RSS content from a website source
- `POST /api/website-sources/fetch-all` - Fetch from all active website sources
- `POST /api/website-sources/{id}/analyze` - Analyze messages from a website source
- `POST /api/website-sources/analyze-all` - Analyze messages from all website sources
- `POST /api/website-sources/{id}/stop` - Stop ongoing operation for a website source

### Messages
- `GET /api/messages` - List messages with pagination
- `GET /api/messages/{id}` - Get message details

### Jobs
- `GET /api/jobs` - List extracted jobs
- `GET /api/jobs/{id}` - Get job details
- `POST /api/jobs/{id}/apply` - Mark job as applied

### Developers
- `GET /api/developers` - List extracted developers
- `GET /api/developers/{id}` - Get developer details

### Actions
- `POST /api/fetch/{channel_id}` - Fetch messages from a channel
- `POST /api/analyze/{channel_id}` - Analyze messages in a channel
- `POST /api/fetch-analyze/{channel_id}` - Fetch and analyze in one operation
- `POST /api/stop-analyze?channel_id={id}` - Stop ongoing analysis for a channel
- `POST /api/cron/start` - Start continuous scanner
- `POST /api/cron/stop` - Stop continuous scanner
- `POST /api/cleanup/old-messages?days={n}` - Delete messages older than N days (jobs deleted, developers kept)

### Analytics
- `GET /api/daily-jobs?days={n}` - Daily job postings by channel (last N days)
- `GET /api/daily-developers-contacted?days={n}` - Daily developers contacted (last N days)
- `GET /api/daily-jobs-applied?days={n}` - Daily jobs applied (last N days)

### WebSocket
- `WS /ws/progress` - Real-time progress updates

## Project Structure

```
agentic-job-scraper/
├── backend/
│   ├── app/
│   │   ├── models.py          # Database models
│   │   ├── routes/            # API endpoints
│   │   ├── connection.py      # Database & WebSocket
│   │   └── tasks.py           # Background tasks
│   ├── services/
│   │   └── ollama_service.py  # AI analysis service
│   ├── telegram_processor/    # Telegram client
│   ├── web_crawler/           # RSS feed crawler and extractor
│   │   ├── rss_fetcher.py     # RSS feed fetching
│   │   ├── rss_extractor.py   # Ollama-based extraction
│   │   ├── models.py          # Pydantic models for extraction
│   │   └── prompts.py         # Extraction prompts
│   └── web_app.py             # FastAPI entry point
├── frontend/
│   ├── src/
│   │   ├── components/        # React components
│   │   ├── pages/             # Page components
│   │   ├── services/          # API client
│   │   └── hooks/             # Custom hooks
│   └── package.json
└── README.md
```

## Configuration

### Telegram Account Management

The application supports managing multiple Telegram accounts through the web UI without requiring environment variables. Each account is stored in the database with the following information:

- **API ID & API Hash**: Credentials from my.telegram.org
- **Phone Number**: The phone number associated with the account
- **Session Name**: Unique identifier for the session file
- **Authentication Status**: Whether the account has been authenticated
- **Active Status**: Whether the account is currently active for use

**Authentication Flow:**
1. Add account credentials via UI
2. Click "Authenticate" to start the process
3. Enter verification code sent to your phone
4. If 2FA is enabled, enter your 2FA password
5. Account is marked as authenticated and ready to use

**Session Management:**
- Session files are stored in `backend/session/`
- Each account has its own session file
- Sessions persist across server restarts
- Re-authentication is only needed if session is deleted or expires

### Telegram API

Get your API credentials from [my.telegram.org/apps](https://my.telegram.org/apps). You can create multiple applications if needed for different accounts.

### Ollama Configuration
- Recommended model: `qwen2.5:7b-instruct-q4_K_M`
- Can be configured to use remote Ollama instance
- Supports GPU acceleration for faster processing
- Concurrent processing with semaphore (default: 3 concurrent requests)
- Batch processing (default: 3 messages per batch)
- Real-time token usage tracking (input/output/total tokens)
- Spam pre-filter (`should_analyze_message`) skips obvious non-tech messages before Ollama
- Configure via `OLLAMA_BASE_URL` and `OLLAMA_MODEL` in `.env`
- Advanced options in `ollama_service.py`:
  - `num_predict`: Maximum tokens to generate (default: 2048)
  - `num_ctx`: Context window size (default: 2048)
  - `num_gpu`: GPU layers to offload (default: 99, full GPU offload)
  - `keep_alive`: Keep model in memory (default: -1, indefinitely)
  - `timeout`: Request timeout (default: 120s)

### Database
- PostgreSQL with async support
- Connection pooling configured for performance
- Automatic table creation on startup
- Session files stored in `backend/session/` directory

### Database Migrations

When updating the application, you may need to run database migrations:

**Add Telegram Accounts Table:**
```bash
psql -U your_username -d job_scraper -f backend/migrations/add_telegram_accounts.sql
```

**Add Phone Code Hash Column:**
```bash
psql -U your_username -d job_scraper -f backend/migrations/add_phone_code_hash.sql
```

**Make developer.message_id nullable (required for message cleanup feature):**
```bash
psql -U your_username -d job_scraper -f backend/migrations/make_developer_message_id_nullable.sql
```

**Add Website Sources Table (for RSS feed support):**
```bash
psql -U your_username -d job_scraper -f backend/migrate_website_crawler.sql
```

**Make telegram_id nullable in messages table (for website sources):**
```bash
psql -U your_username -d job_scraper -f backend/migrate_make_telegram_id_nullable.sql
```

**Add extraction_prompt column to website_sources table:**
```bash
psql -U your_username -d job_scraper -f backend/migrate_add_extraction_prompt.sql
```

Or run all migrations at once:
```bash
cd backend/migrations
for f in *.sql; do psql -U your_username -d job_scraper -f "$f"; done
```

## Troubleshooting

### Telegram Authentication Issues

**Code not received:**
- Check that the phone number is correct and includes the country code (e.g., +1234567890)
- Ensure you're not already logged in to Telegram on another device with the same number
- Try clicking "Resend Code" in the authentication dialog
- Check if Telegram is blocking verification requests (wait a few minutes and try again)

**Authentication session expired:**
- This happens if too much time passes between requesting the code and entering it
- Click "Authenticate" again to request a new code
- The old session will be automatically cleaned up

**2FA password incorrect:**
- Ensure you're entering your Telegram 2FA password (not your phone's passcode)
- Check for typos and try again
- If you've forgotten your 2FA password, you'll need to reset it through Telegram

**Account shows as not authenticated after successful auth:**
- Refresh the page to see the updated status
- Check the backend logs for any errors during authentication
- Try authenticating again if the session was interrupted

### Ollama Connection Issues
- Ensure Ollama server is running: `ollama serve`
- Check OLLAMA_BASE_URL in `.env`
- Verify model is installed: `ollama list`
- If using a remote Ollama instance, ensure it's accessible from your network

### Telegram Flood Errors
- The system automatically handles FloodWaitError
- It will retry after the required wait time
- No manual intervention needed
- If errors persist, reduce the frequency of fetch operations

### Database Connection
- Verify PostgreSQL is running
- Check DATABASE_URL in `.env`
- Ensure database exists: `createdb job_scraper`
- Check database credentials are correct

### Session File Issues
- If authentication fails with "Two-steps verification is enabled", delete the session file in `backend/session/`
- Session files are named like `session_+1234567890.session`
- The authentication flow automatically cleans up old sessions, but manual deletion may be needed in some cases

### Channel Fetching Issues
- Ensure you have at least one authenticated and active Telegram account
- Check that the selected account is active in the dropdown
- Verify the channel username is correct (without @ symbol)
- Check backend logs for specific error messages
- Ensure the selected Telegram account has access to the channel

### Frontend API Connection Issues
- Check that the backend is running on the expected port (default: 8000)
- Verify VITE_API_BASE_URL in frontend `.env`
- Check browser console for CORS errors
- Ensure WebSocket URL is correct (VITE_WS_BASE_URL)

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
