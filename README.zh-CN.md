# Agentic Job Scraper

一个自动化职位抓取系统，从 Telegram 频道和 RSS 订阅源（如 V2EX、电鸭社区）获取软件开发职位信息，使用 AI (Ollama) 进行分析，并在现代化的 Web 界面中展示。

## 功能特性

- **自动获取**: 持续监控 Telegram 频道的新职位发布
- **网站源支持**: 从 RSS 订阅源获取和分析职位信息（如 V2EX、电鸭社区）
- **AI 驱动分析**: 使用 Ollama（推荐 qwen2.5）分析消息并提取职位/开发者信息
- **实时进度**: 基于 WebSocket 的分析操作进度跟踪
- **Token 使用监控**: 实时跟踪 Ollama API 调用的 token 使用情况
- **停止分析**: 优雅地停止正在进行的分析操作，并提供视觉反馈
- **并发处理**: 可配置并发数的批处理，加快分析速度
- **单条消息状态**: 每条分析消息的视觉指示器（成功、JSON 截断、失败、其他）
- **分析仪表板**: 按频道、联系的开发者、申请职位的每日图表
- **消息清理**: 删除 N 天前的消息（关联的职位被删除，开发者保留）
- **现代 UI**: 使用 React、TypeScript 和 shadcn/ui 构建的简洁响应式界面
- **多语言支持**: 分析多种语言的职位发布（英语、中文等）
- **智能过滤**: 在发送到 Ollama 之前进行垃圾邮件预过滤，加快处理速度
- **远程工作优先**: 优先考虑远程/居家办公机会
- **多账号支持**: 通过 UI 动态管理多个 Telegram 账号，支持交互式认证
- **自定义提取提示词**: 为每个网站源自定义 Ollama 提示词，提高提取准确性

## 计划功能

- **扩展职位板支持**: 根据用户需求添加更多职位板和招聘网站
- **智能内容获取**: 使用 Playwright 获取职位详情页面的完整内容以进行更好的分析

## 工作流程

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
    Backend->>DB: 存储消息

    User->>Frontend: 点击分析
    Frontend->>Backend: POST /api/analyze 或 /api/website-sources/{id}/analyze
    Backend->>DB: 获取待分析消息
    loop 对于每批消息
        Backend->>Ollama: 发送消息进行分析
        Ollama-->>Backend: 返回职位/开发者数据
        Backend->>Frontend: WebSocket 进度更新
        Backend->>DB: 存储提取的职位/开发者
    end
    Backend-->>Frontend: 分析完成
    Frontend->>User: 显示结果

    User->>Frontend: 查看仪表板
    Frontend->>Backend: GET /api/stats, /api/daily-jobs
    Backend->>DB: 查询分析数据
    Backend-->>Frontend: 返回统计数据
    Frontend->>User: 显示图表
```

### 系统架构

```mermaid
graph LR
    subgraph Frontend
        A[React UI]
        B[WebSocket 客户端]
        C[API 客户端]
    end

    subgraph Backend
        D[FastAPI 服务器]
        E[WebSocket 服务器]
        F[Telegram 客户端]
        G[RSS 获取器]
        H[Ollama 服务]
        I[任务调度器]
    end

    subgraph External Services
        J[Telegram API]
        K[RSS 订阅源]
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

## 适用人群

**主要用户:**
- **求职的软件开发者** - 寻找远程/居家办公机会的开发者，希望在一个地方监控多个 Telegram 职位频道
- **技术招聘人员/招聘经理** - 监控竞争对手职位发布的招聘人员，跟踪市场趋势和薪资信息的招聘经理
- **Telegram 频道管理员** - 分析其频道职位发布效果和社区参与度的管理员

**次要用户:**
- **远程工作爱好者** - 特别是在本地就业市场有限的地区寻找远程机会的开发者
- **AI/ML 爱好者** - 对本地 LLM (Ollama) 在内容分析和网页抓取集成中的实际应用感兴趣的开发者

## 项目状态

**注意:** 本项目专为个人使用设计。虽然它为自动化职位抓取和 AI 分析提供了坚实的基础，但并非 100% 生产就绪，可能缺少一些企业级最佳实践，例如：

- 全面的测试套件（单元测试、集成测试、E2E 测试）
- CI/CD 管道配置
- 代码质量工具（ESLint、Prettier、Black、isort）
- 预提交钩子进行自动检查
- 容器化（Docker、docker-compose）
- 数据库迁移管理（Alembic）
- 安全加固（速率限制、输入验证）
- 监控和日志基础设施
- 备份和灾难恢复文档

但是，该项目功能完整，可以有效地用于个人求职、监控 Telegram 频道以及学习 AI 驱动的网页抓取。您可以根据需要扩展其他功能和最佳实践。

## 架构

### 后端 (FastAPI + Python)
- **FastAPI**: 用于 API 端点的异步 Web 框架
- **SQLAlchemy**: 带 PostgreSQL 的异步 ORM
- **Telethon**: 用于获取消息的 Telegram 客户端
- **Ollama**: 用于消息分析的本地 LLM
- **WebSocket**: 实时进度更新

### 前端 (React + TypeScript)
- **React 18**: 带有 hooks 的现代 React
- **TypeScript**: 类型安全开发
- **Vite**: 快速构建工具和开发服务器
- **shadcn/ui**: 美观、可访问的 UI 组件
- **Tailwind CSS**: 实用优先的样式
- **React Router**: 客户端路由

## 前置要求

- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- Ollama（已安装 Mistral 模型）
- Telegram API 凭证（可选 - 可通过 UI 添加）

## 安装

### 后端设置

1. 导航到后端目录：
```bash
cd backend
```

2. 创建虚拟环境：
```bash
python -m venv env
env\Scripts\activate  # Windows
source env/bin/activate  # Linux/Mac
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

4. 配置环境变量：
```bash
cp .env.example .env
```

编辑 `.env` 填入您的凭证：
```env
# Telegram API 凭证（可选 - 可通过侧边栏的 Telegram Accounts 页面添加）
# 从 https://my.telegram.org/apps 获取
# TELEGRAM_API_ID=your_api_id_here
# TELEGRAM_API_HASH=your_api_hash_here
# TELEGRAM_PHONE=+1234567890

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
DATABASE_URL=postgresql+asyncpg://user:password@localhost/job_scraper
```

**注意:** Telegram 凭证现在是可选的。您可以通过 Web UI 的"Telegram Accounts"完全添加和管理多个 Telegram 账号。UI 支持交互式认证（直接在浏览器中输入验证码和 2FA 密码）。如果您更喜欢使用环境变量，请取消注释并填写上面的 Telegram 凭证。

5. 初始化数据库：
```bash
python reset_db.py
```

这将创建所有必要的表，包括用于多账号支持的新 `telegram_accounts` 表。

### 前端设置

1. 导航到前端目录：
```bash
cd frontend
```

2. 安装依赖：
```bash
npm install
```

3. 配置环境变量（可选）：
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

1. 从 [ollama.com](https://ollama.com) 安装 Ollama
2. 拉取 Mistral 模型：
```bash
ollama pull mistral
```

3. 启动 Ollama 服务器：
```bash
ollama serve
```

## 运行应用程序

### 开发模式

**启动后端:**
```bash
cd backend
python web_app.py
```
后端将在 `http://localhost:8000` 运行

**启动前端:**
```bash
cd frontend
npm run dev
```
前端将在 `http://localhost:5173` 运行

### 生产模式

**选项 1: 从 FastAPI 提供静态文件（最简单）**

1. 构建前端：
```bash
cd frontend
npm run build
```

2. 运行后端（它将同时提供 API 和前端）：
```bash
cd backend
python web_app.py
```

在 `http://localhost:8000` 访问应用程序

**选项 2: 单独部署（Nginx + Gunicorn）**

1. 构建前端：
```bash
cd frontend
npm run build
```

2. 配置 Nginx 提供前端并代理 API 请求：
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

3. 使用 Gunicorn 运行后端：
```bash
cd backend
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker web_app:app --bind 0.0.0.0:8000
```

### 使用 ngrok 进行远程访问

如果您想使用 ngrok 远程访问应用程序：

1. 启动后端：
```bash
cd backend
python web_app.py
```

2. 在单独的终端中，启动 ngrok：
```bash
ngrok http 8000
```

3. 复制 ngrok URL（例如 `https://abc123.ngrok-free.app`）

4. 配置前端使用 ngrok URL：
```bash
cd frontend
cp .env.example .env
```

编辑 `.env`:
```env
VITE_API_BASE_URL=https://abc123.ngrok-free.app
VITE_WS_BASE_URL=wss://abc123.ngrok-free.app/ws/progress
```

5. 启动前端：
```bash
npm run dev
```

现在前端将通过 ngrok 隧道连接到您的后端。

## 使用方法

### 设置 Telegram 账号

1. **获取 API 凭证**: 访问 [my.telegram.org/apps](https://my.telegram.org/apps) 创建新应用程序并获取您的 `api_id` 和 `api_hash`

2. **通过 UI 添加账号**:
   - 导航到侧边栏中的"Telegram Accounts"
   - 点击"Add Account"
   - 输入您的 API ID、API Hash 和电话号码
   - 点击"Add Account"

3. **认证您的账号**:
   - 点击未认证账号旁边的"Authenticate"按钮
   - 将出现一个对话框 - 输入发送到您手机的验证码
   - 如果您启用了 2FA，请在提示时输入您的 2FA 密码
   - 认证后，账号将显示"Authenticated"徽章

4. **管理多个账号**:
   - 根据需要添加任意数量的 Telegram 账号
   - 切换账号为活跃/非活跃状态
   - 删除您不再需要的账号
   - 获取频道时选择要使用的账号

### 使用应用程序

1. **添加频道**: 进入 Channels 页面并添加要监控的 Telegram 频道
2. **添加网站源**: 进入 Websites 页面并添加 RSS 订阅源 URL（如 V2EX、电鸭社区）
3. **选择账号**: 获取频道时，选择要使用的 Telegram 账号（如果您有多个）
4. **获取消息**: 点击"Fetch"从频道或 RSS 订阅源检索最新消息
5. **分析**: 点击"Analyze"使用 AI 处理消息并提取职位/开发者信息
6. **停止分析**: 点击"Stop"优雅地停止正在进行的分析操作（显示"Stopping..."状态）
7. **监控进度**: 查看实时进度，包括 token 使用情况和每条消息状态（成功/截断/失败）
8. **查看结果**: 浏览 Jobs 和 Developers 页面查看提取的信息
9. **跟踪进度**: 使用状态指示器标记职位为已申请或开发者为已联系
10. **持续扫描**: 启用 cron 任务进行自动定期获取
11. **分析**: 在仪表板上查看按频道、联系的开发者和申请职位的每日图表
12. **清理**: 使用快速操作中的"Cleanup Old Messages"删除 N 天前的消息
13. **自定义提示词**: 为每个网站源自定义提取提示词以提高准确性

## API 端点

### 频道
- `GET /api/channels` - 列出所有频道
- `POST /api/channels` - 添加新频道
- `DELETE /api/channels/{id}` - 删除频道

### Telegram 账号
- `GET /api/telegram-accounts` - 列出所有 Telegram 账号
- `POST /api/telegram-accounts` - 添加新 Telegram 账号
- `DELETE /api/telegram-accounts/{id}` - 删除 Telegram 账号
- `PATCH /api/telegram-accounts/{id}/toggle-active` - 切换账号活跃状态
- `POST /api/telegram-accounts/authenticate` - 启动认证过程（向手机发送代码）
- `POST /api/telegram-accounts/verify-code` - 验证认证代码
- `POST /api/telegram-accounts/verify-password` - 验证 2FA 密码

### 网站源
- `GET /api/website-sources` - 列出所有网站源
- `POST /api/website-sources` - 添加新网站源（RSS 订阅源）
- `DELETE /api/website-sources/{id}` - 删除网站源
- `PUT /api/website-sources/{id}` - 更新网站源（包括自定义提取提示词）
- `POST /api/website-sources/{id}/fetch` - 从网站源获取 RSS 内容
- `POST /api/website-sources/fetch-all` - 从所有活跃网站源获取
- `POST /api/website-sources/{id}/analyze` - 分析网站源的消息
- `POST /api/website-sources/analyze-all` - 分析所有网站源的消息
- `POST /api/website-sources/{id}/stop` - 停止网站源的正在进行的操作

### 消息
- `GET /api/messages` - 列出消息（带分页）
- `GET /api/messages/{id}` - 获取消息详情

### 职位
- `GET /api/jobs` - 列出提取的职位
- `GET /api/jobs/{id}` - 获取职位详情
- `POST /api/jobs/{id}/apply` - 标记职位为已申请

### 开发者
- `GET /api/developers` - 列出提取的开发者
- `GET /api/developers/{id}` - 获取开发者详情

### 操作
- `POST /api/fetch/{channel_id}` - 从频道获取消息
- `POST /api/analyze/{channel_id}` - 分析频道中的消息
- `POST /api/fetch-analyze/{channel_id}` - 在一个操作中获取和分析
- `POST /api/stop-analyze?channel_id={id}` - 停止频道的正在进行的分析
- `POST /api/cron/start` - 启动持续扫描器
- `POST /api/cron/stop` - 停止持续扫描器
- `POST /api/cleanup/old-messages?days={n}` - 删除 N 天前的消息（职位删除，开发者保留）

### 分析
- `GET /api/daily-jobs?days={n}` - 按频道的每日职位发布（最近 N 天）
- `GET /api/daily-developers-contacted?days={n}` - 每日联系的开发者（最近 N 天）
- `GET /api/daily-jobs-applied?days={n}` - 每日申请的职位（最近 N 天）

### WebSocket
- `WS /ws/progress` - 实时进度更新

## 项目结构

```
agentic-job-scraper/
├── backend/
│   ├── app/
│   │   ├── models.py          # 数据库模型
│   │   ├── routes/            # API 端点
│   │   ├── connection.py      # 数据库和 WebSocket
│   │   └── tasks.py           # 后台任务
│   ├── services/
│   │   └── ollama_service.py  # AI 分析服务
│   ├── telegram_processor/    # Telegram 客户端
│   ├── web_crawler/           # RSS 订阅源爬虫和提取器
│   │   ├── rss_fetcher.py     # RSS 订阅源获取
│   │   ├── rss_extractor.py   # 基于 Ollama 的提取
│   │   ├── models.py          # 提取的 Pydantic 模型
│   │   └── prompts.py         # 提取提示词
│   └── web_app.py             # FastAPI 入口点
├── frontend/
│   ├── src/
│   │   ├── components/        # React 组件
│   │   ├── pages/             # 页面组件
│   │   ├── services/          # API 客户端
│   │   └── hooks/             # 自定义 hooks
│   └── package.json
└── README.md
```

## 配置

### Telegram 账号管理

应用程序支持通过 Web UI 管理多个 Telegram 账号，无需环境变量。每个账号在数据库中存储以下信息：

- **API ID 和 API Hash**: 来自 my.telegram.org 的凭证
- **电话号码**: 与账号关联的电话号码
- **会话名称**: 会话文件的唯一标识符
- **认证状态**: 账号是否已认证
- **活跃状态**: 账号当前是否可用于使用

**认证流程:**
1. 通过 UI 添加账号凭证
2. 点击"Authenticate"启动流程
3. 输入发送到您手机的验证码
4. 如果启用了 2FA，输入您的 2FA 密码
5. 账号被标记为已认证并准备使用

**会话管理:**
- 会话文件存储在 `backend/session/` 中
- 每个账号都有自己的会话文件
- 会话在服务器重启后持久化
- 仅在会话被删除或过期时才需要重新认证

### Telegram API

从 [my.telegram.org/apps](https://my.telegram.org/apps) 获取您的 API 凭证。如果需要，您可以为不同账号创建多个应用程序。

### Ollama 配置
- 推荐模型: `qwen2.5:7b-instruct-q4_K_M`
- 可配置为使用远程 Ollama 实例
- 支持 GPU 加速以加快处理速度
- 并发处理，使用信号量（默认：3 个并发请求）
- 批处理（默认：每批 3 条消息）
- 实时 token 使用跟踪（输入/输出/总 token）
- 垃圾邮件预过滤器（`should_analyze_message`）在 Ollama 之前跳过明显的非技术消息
- 通过 `.env` 中的 `OLLAMA_BASE_URL` 和 `OLLAMA_MODEL` 配置
- `ollama_service.py` 中的高级选项：
  - `num_predict`: 最大生成 token 数（默认：2048）
  - `num_ctx`: 上下文窗口大小（默认：2048）
  - `num_gpu`: GPU 层数卸载（默认：99，完全 GPU 卸载）
  - `keep_alive`: 将模型保留在内存中（默认：-1，无限期）
  - `timeout`: 请求超时（默认：120s）

### 数据库
- 带异步支持的 PostgreSQL
- 为性能配置的连接池
- 启动时自动创建表
- 会话文件存储在 `backend/session/` 目录中

### 数据库迁移

更新应用程序时，您可能需要运行数据库迁移：

**添加 Telegram 账号表:**
```bash
psql -U your_username -d job_scraper -f backend/migrations/add_telegram_accounts.sql
```

**添加电话代码哈希列:**
```bash
psql -U your_username -d job_scraper -f backend/migrations/add_phone_code_hash.sql
```

**使 developer.message_id 可为空（消息清理功能所需）:**
```bash
psql -U your_username -d job_scraper -f backend/migrations/make_developer_message_id_nullable.sql
```

**添加网站源表（用于 RSS 订阅源支持）:**
```bash
psql -U your_username -d job_scraper -f backend/migrate_website_crawler.sql
```

**使 messages 表中的 telegram_id 可为空（用于网站源）:**
```bash
psql -U your_username -d job_scraper -f backend/migrate_make_telegram_id_nullable.sql
```

**添加 extraction_prompt 列到 website_sources 表:**
```bash
psql -U your_username -d job_scraper -f backend/migrate_add_extraction_prompt.sql
```

或一次性运行所有迁移：
```bash
cd backend/migrations
for f in *.sql; do psql -U your_username -d job_scraper -f "$f"; done
```

## 故障排除

### Telegram 认证问题

**未收到代码:**
- 检查电话号码是否正确并包含国家代码（例如 +1234567890）
- 确保您没有在另一台设备上使用相同号码登录 Telegram
- 尝试在认证对话框中点击"Resend Code"
- 检查 Telegram 是否阻止验证请求（等待几分钟并重试）

**认证会话过期:**
- 如果在请求代码和输入代码之间经过太多时间，就会发生这种情况
- 再次点击"Authenticate"请求新代码
- 旧会话将自动清理

**2FA 密码错误:**
- 确保您输入的是 Telegram 2FA 密码（不是手机的密码）
- 检查拼写错误并重试
- 如果您忘记了 2FA 密码，您需要通过 Telegram 重置

**成功认证后账号显示为未认证:**
- 刷新页面以查看更新状态
- 检查后端日志中是否有认证期间的错误
- 如果会话中断，请尝试再次认证

### Ollama 连接问题
- 确保 Ollama 服务器正在运行: `ollama serve`
- 检查 `.env` 中的 OLLAMA_BASE_URL
- 验证模型已安装: `ollama list`
- 如果使用远程 Ollama 实例，确保它可以从您的网络访问

### Telegram 洪水错误
- 系统自动处理 FloodWaitError
- 它将在所需的等待时间后重试
- 无需手动干预
- 如果错误持续存在，减少获取操作的频率

### 数据库连接
- 验证 PostgreSQL 正在运行
- 检查 `.env` 中的 DATABASE_URL
- 确保数据库存在: `createdb job_scraper`
- 检查数据库凭证是否正确

### 会话文件问题
- 如果认证失败并显示"Two-steps verification is enabled"，请删除 `backend/session/` 中的会话文件
- 会话文件命名为 `session_+1234567890.session`
- 认证流程会自动清理旧会话，但在某些情况下可能需要手动删除

### 频道获取问题
- 确保您至少有一个已认证且活跃的 Telegram 账号
- 检查下拉列表中选择的账号是否活跃
- 验证频道用户名是否正确（不带 @ 符号）
- 检查后端日志中的具体错误消息
- 确保所选的 Telegram 账号有权访问该频道

### 前端 API 连接问题
- 检查后端是否在预期端口上运行（默认：8000）
- 验证前端 `.env` 中的 VITE_API_BASE_URL
- 检查浏览器控制台是否有 CORS 错误
- 确保 WebSocket URL 正确（VITE_WS_BASE_URL）

## 许可证

MIT

## 贡献

欢迎贡献！请随时提交 Pull Request。
