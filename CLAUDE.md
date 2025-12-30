# CLAUDE.md - Tabys CRM Telegram Bot

## Project Overview

This is a production-ready Telegram bot (aiogram 3.x) that provides secure CRM/admin interface for the Tabys FastAPI backend. The bot uses OTP-based authentication and mirrors the backend's RBAC system.

## Development Commands

```bash
# Navigate to bot directory
cd TG_BOT/

# Install dependencies
pip install -r requirements.txt

# Run with Docker Compose (recommended)
docker-compose up -d

# View logs
docker-compose logs -f telegram-bot

# Run directly (requires Redis)
python main.py

# Stop services
docker-compose down
```

## Architecture

### Core Components

- **main.py** - Bot entry point, dispatcher configuration
- **config/settings.py** - Pydantic settings from environment
- **api/client.py** - Async HTTP client for Tabys backend
- **services/session.py** - Redis session management
- **middlewares/** - Auth, RBAC, rate limiting
- **handlers/** - Command and callback handlers
- **keyboards/** - Inline keyboard builders
- **models/** - Pydantic models for sessions and data
- **utils/** - Formatters and logging

### Authentication Flow

1. Admin generates OTP in Tabys web admin
2. Admin sends `/login <OTP>` to bot
3. Bot verifies OTP via backend API
4. Backend returns JWT + role
5. Bot stores session in Redis (24h TTL)
6. User authenticated with proper RBAC

### RBAC System

Mirrors Tabys backend permissions exactly:

```python
ROLE_PERMISSIONS = {
    Role.CLIENT: {},
    Role.VOLUNTEER_ADMIN: {Module.VOLUNTEERS: {READ, CREATE, UPDATE, DELETE}},
    Role.MSB: {Module.VACANCIES: {...}, Module.LEISURE: {...}},
    Role.NPO: {Module.PROJECTS: {...}, Module.EVENTS: {...}},
    Role.GOVERNMENT: {all_modules: {READ}},
    Role.ADMINISTRATOR: {all_modules: {READ, CREATE, UPDATE, DELETE}},
    Role.SUPER_ADMIN: {all_modules: {READ, CREATE, UPDATE, DELETE}},
}
```

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | Bot initialization, middleware/router registration |
| `config/settings.py` | Environment configuration |
| `api/client.py` | Tabys API client (verify OTP, CRUD operations) |
| `services/session.py` | Redis session CRUD, rate limiting |
| `middlewares/auth.py` | Session validation, inject session to handlers |
| `middlewares/rbac.py` | Permission checking, ROLE_PERMISSIONS mapping |
| `handlers/auth.py` | /start, /login, /logout commands |
| `handlers/events.py` | Events list, view, pagination |

## Environment Variables

Required in `.env`:
```env
TELEGRAM_BOT_TOKEN=bot_token_from_botfather
TABYS_API_URL=http://localhost:8000
REDIS_URL=redis://localhost:6379/0
```

## Adding New Features

### New Handler

1. Create `handlers/new_feature.py`
2. Import router in `handlers/__init__.py`
3. Include router in `main.py`

### New API Endpoint

Add method to `api/client.py`:
```python
async def get_something(self, access_token: str) -> Dict:
    return await self._auth_request("GET", "/api/v1/something/", access_token)
```

### New RBAC Module

Add to `models/session.py`:
```python
class Module(str, Enum):
    NEW_MODULE = "new_module"
```

Add permissions in `middlewares/rbac.py`.

## Integration with Tabys Backend

### Required Backend Endpoints

- `POST /api/v1/telegram-auth/verify-otp` - Verify OTP token
- `POST /api/v1/telegram-auth/logout` - End session
- `POST /api/v1/telegram-auth/restore-session` - Restore after restart

### Backend Models Used

- `TelegramOTP` - One-time password tokens
- `TelegramSession` - Telegram to admin bindings
- `Admin` - Backend administrator accounts

## Testing

Manual testing via Telegram:

1. Generate OTP in Tabys admin panel
2. Send `/login <OTP>` to bot
3. Navigate menu based on your role
4. Test RBAC by trying unauthorized actions

## Common Issues

### Bot not starting
- Check `TELEGRAM_BOT_TOKEN` is set correctly
- Verify Redis is running

### OTP verification fails
- Check backend URL is correct
- Ensure admin account exists
- OTP may be expired (10 min default)

### Permission denied
- Check user role in database
- Review RBAC mapping matches backend
