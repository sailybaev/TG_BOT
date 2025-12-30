# Tabys CRM Telegram Bot

Production-ready Telegram bot for Tabys CRM platform. Provides secure admin access to manage events, courses, vacancies, news, projects, and volunteers via Telegram.

## Architecture

```
TG_BOT/
├── main.py                 # Bot entry point
├── config/
│   └── settings.py         # Pydantic configuration
├── api/
│   └── client.py           # Tabys backend HTTP client
├── services/
│   └── session.py          # Redis session management
├── middlewares/
│   ├── auth.py             # Authentication middleware
│   ├── rbac.py             # Role-based access control
│   └── rate_limit.py       # Rate limiting
├── handlers/
│   ├── auth.py             # /start, /login, /logout
│   ├── events.py           # Event management
│   ├── courses.py          # Course management
│   ├── vacancies.py        # Vacancy management
│   ├── news.py             # News management
│   ├── projects.py         # Project management
│   └── admin.py            # Admin-only features
├── keyboards/
│   └── main.py             # Inline keyboard builders
├── models/
│   └── session.py          # Pydantic models
├── utils/
│   ├── formatters.py       # Message formatters
│   └── logging_config.py   # Structured logging
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Authentication Flow

The bot uses **OTP-based authentication** integrated with the Tabys backend:

```
┌─────────────────────────────────────────────────────────────────┐
│                    OTP Authentication Flow                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Admin logs into Tabys Web Admin Panel                       │
│                    │                                             │
│                    ▼                                             │
│  2. Admin clicks "Generate Telegram OTP"                        │
│     → Backend creates OTP (8 chars, 10 min expiry)              │
│     → Returns: "/login A7B9C3D5"                                │
│                    │                                             │
│                    ▼                                             │
│  3. Admin sends "/login A7B9C3D5" to Telegram Bot               │
│                    │                                             │
│                    ▼                                             │
│  4. Bot calls POST /api/v1/telegram-auth/verify-otp             │
│     → Sends: otp_token + telegram_user_id                       │
│                    │                                             │
│                    ▼                                             │
│  5. Backend validates OTP:                                       │
│     - Not used, not expired, not revoked                        │
│     - Returns: JWT token + admin role                           │
│     - Marks OTP as used                                         │
│                    │                                             │
│                    ▼                                             │
│  6. Bot stores session in Redis:                                 │
│     - JWT token                                                  │
│     - Admin ID and role                                         │
│     - 24-hour TTL                                               │
│                    │                                             │
│                    ▼                                             │
│  7. Admin is authenticated!                                      │
│     → Bot shows menu based on RBAC permissions                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Security Features

- **OTP-only authentication**: No phone/username auth
- **One-time tokens**: Each OTP can only be used once
- **Short-lived OTPs**: 10-minute default expiry
- **Redis session storage**: Secure, fast session management
- **RBAC enforcement**: Mirrors backend permissions exactly
- **Rate limiting**: Prevents brute-force attacks on /login
- **No user creation**: Bot only binds to existing backend users

## RBAC Permissions

The bot mirrors the Tabys backend RBAC system:

| Role | Access |
|------|--------|
| `client` | No admin access |
| `volunteer_admin` | Volunteers module |
| `msb` | Vacancies, Leisure |
| `npo` | Projects, Events |
| `government` | Read-only access to all |
| `administrator` | Full CRUD on all modules |
| `super_admin` | Full access + admin panel |

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Tabys backend running
- Telegram Bot Token from @BotFather

### 1. Configure Environment

```bash
cd TG_BOT
cp .env.example .env
```

Edit `.env`:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TABYS_API_URL=http://localhost:8000
```

### 2. Start with Docker

```bash
# Development
docker-compose up -d

# Production
docker-compose -f docker-compose.prod.yml up -d
```

### 3. Start without Docker (Development)

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Start Redis (required)
docker run -d -p 6379:6379 redis:7-alpine

# Run bot
python main.py
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Show welcome message and auth status |
| `/login <OTP>` | Authenticate with OTP token |
| `/logout` | End current session |
| `/status` | Show session information |
| `/menu` | Show main menu |
| `/help` | Show available commands |

## API Endpoints Used

The bot communicates with these Tabys backend endpoints:

### Authentication
- `POST /api/v1/telegram-auth/verify-otp` - Verify OTP
- `POST /api/v1/telegram-auth/logout` - End session
- `POST /api/v1/telegram-auth/restore-session` - Restore session after restart

### Data Access (authenticated)
- `GET /api/v1/events/` - List events
- `GET /api/v2/courses/` - List courses
- `GET /api/v2/vacancies/` - List vacancies
- `GET /api/v1/news/` - List news
- `GET /api/v2/projects/` - List projects
- `GET /api/v1/admin/volunteers/` - List volunteers

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | - | Bot token from @BotFather |
| `TABYS_API_URL` | `http://localhost:8000` | Backend API URL |
| `TABYS_API_TIMEOUT` | `30` | API timeout (seconds) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `REDIS_SESSION_TTL` | `86400` | Session TTL (24h) |
| `LOGIN_RATE_LIMIT` | `5` | Max login attempts/min |
| `GENERAL_RATE_LIMIT` | `30` | Max requests/min |
| `LOG_LEVEL` | `INFO` | Log level |
| `DEBUG` | `false` | Debug mode |

## Session Management

Sessions are stored in Redis with the following structure:

```json
{
  "telegram_user_id": "123456789",
  "admin_id": 42,
  "role": "administrator",
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "admin_name": "Admin User",
  "created_at": "2025-12-28T10:00:00Z",
  "last_activity": "2025-12-28T10:30:00Z"
}
```

Key pattern: `tg_session:{telegram_user_id}`

## Extending the Bot

### Adding a New Handler

1. Create handler file in `handlers/`:

```python
# handlers/new_feature.py
from aiogram import Router, F
from middlewares import RBACContext
from models import Module

router = Router(name="new_feature")

@router.callback_query(F.data == "menu:new_feature")
async def show_new_feature(callback, session, rbac: RBACContext):
    if not rbac.can_read(Module.YOUR_MODULE):
        await callback.answer("Access denied", show_alert=True)
        return
    # ... implementation
```

2. Register in `handlers/__init__.py`:

```python
from .new_feature import router as new_feature_router
```

3. Include in `main.py`:

```python
dp.include_router(new_feature_router)
```

### Adding a New API Endpoint

Add method to `api/client.py`:

```python
async def get_new_entities(self, access_token: str, page: int = 1) -> Dict[str, Any]:
    return await self._auth_request(
        "GET",
        "/api/v1/new-entities/",
        access_token,
        params={"page": page}
    )
```

## Troubleshooting

### Bot not responding
1. Check bot token is correct
2. Verify Redis is running: `redis-cli ping`
3. Check logs: `docker-compose logs -f telegram-bot`

### Authentication fails
1. Ensure OTP is not expired (10 min default)
2. Check backend is accessible from bot
3. Verify admin account exists in database

### Permission denied
1. Check user role in Tabys admin panel
2. Review RBAC configuration in `middlewares/rbac.py`
3. Ensure role matches backend RBAC

### Session issues
1. Check Redis connection: `redis-cli info`
2. Clear session: `redis-cli DEL tg_session:USER_ID`
3. Re-authenticate with new OTP

## License

Part of the SARYARQAJASTARY platform.
