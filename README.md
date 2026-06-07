# Agentic Job Scraper

An automated job scraping system that fetches software development job postings from Telegram channels, analyzes them using AI (Ollama), and presents them in a modern web interface.

## Features

- **Automated Fetching**: Continuously monitors Telegram channels for new job postings
- **AI-Powered Analysis**: Uses Ollama (Mistral) to analyze messages and extract job/developer information
- **Real-time Progress**: WebSocket-based progress tracking for analysis operations
- **Modern UI**: Clean, responsive interface built with React, TypeScript, and shadcn/ui
- **Multi-language Support**: Analyzes job postings in multiple languages (English, Chinese, etc.)
- **Smart Filtering**: Automatically filters out non-software-development content
- **Remote Jobs Focus**: Prioritizes remote/work-from-home opportunities

## Planned Features

- **Web Scraping from Job Boards**: Support for scraping jobs from popular job board URLs (LinkedIn, Indeed, etc.) with AI analysis
- **Source Tracking**: Distinguish between Telegram-sourced and web-sourced job postings
- **Extended Job Board Support**: Add more job boards and career sites based on user demand

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
- Telegram API credentials

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
TELEGRAM_API_ID=your_api_id_here
TELEGRAM_API_HASH=your_api_hash_here
TELEGRAM_PHONE=+1234567890
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
DATABASE_URL=postgresql+asyncpg://user:password@localhost/job_scraper
```

5. Initialize the database:
```bash
python reset_db.py
```

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

1. **Add Channels**: Go to the Channels page and add Telegram channels to monitor
2. **Fetch Messages**: Click "Fetch" to retrieve recent messages from channels
3. **Analyze**: Click "Analyze" to process messages with AI and extract job/developer info
4. **View Results**: Browse Jobs and Developers pages to see extracted information
5. **Continuous Scanning**: Enable the cron job for automatic periodic fetching

## API Endpoints

### Channels
- `GET /api/channels` - List all channels
- `POST /api/channels` - Add a new channel
- `DELETE /api/channels/{id}` - Delete a channel

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
- `POST /api/search/{channel_id}` - Fetch and analyze in one operation
- `POST /api/cron/start` - Start continuous scanner
- `POST /api/cron/stop` - Stop continuous scanner

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

### Telegram API
Get your API credentials from [my.telegram.org/apps](https://my.telegram.org/apps)

### Ollama Configuration
- Default model: `mistral`
- Can be configured to use remote Ollama instance
- Supports GPU acceleration for faster processing

### Database
- PostgreSQL with async support
- Connection pooling configured for performance
- Automatic table creation on startup

## Troubleshooting

### Ollama Connection Issues
- Ensure Ollama server is running: `ollama serve`
- Check OLLAMA_BASE_URL in `.env`
- Verify model is installed: `ollama list`

### Telegram Flood Errors
- The system automatically handles FloodWaitError
- It will retry after the required wait time
- No manual intervention needed

### Database Connection
- Verify PostgreSQL is running
- Check DATABASE_URL in `.env`
- Ensure database exists: `createdb job_scraper`

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
