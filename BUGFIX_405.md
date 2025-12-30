# Bug Fix: Method Not Allowed (405) Errors

## Issue
Bot was getting "405 Method Not Allowed" errors when trying to fetch events, news, and other resources from the Tabys backend.

## Root Cause
**Missing trailing slashes** on certain API endpoints. FastAPI's behavior with trailing slashes caused route mismatches.

**Bot was calling (without trailing slashes):**
- `/api/v2/events`
- `/api/v2/news`
- `/api/v2/admin/volunteers`
- `/api/v2/analytics`

**Backend requires (with trailing slashes):**
- `/api/v2/events/`
- `/api/v2/news/`
- `/api/v2/admin/volunteers/`
- `/api/v2/analytics/`

Note: Some endpoints like `/api/v2/courses/` and `/api/v2/vacancies/` already had trailing slashes and worked correctly.

## Error Logs
```
ERROR | api.client | API HTTP error: 405 - {"detail":"Method Not Allowed"}
ERROR | handlers.events | Failed to fetch events: API error: 405
ERROR | handlers.news | Failed to fetch news: API error: 405
```

## Solution
Added trailing slashes to all API endpoints in `TG_BOT/api/client.py`:

### Changed Endpoints

#### Events
```python
# Before
"/api/v2/events"
"/api/v2/events/{event_id}"

# After
"/api/v2/events/"
"/api/v2/events/{event_id}/"
```

#### News
```python
# Before
"/api/v2/news"
"/api/v2/news/{news_id}"

# After
"/api/v2/news/"
"/api/v2/news/{news_id}/"
```

#### Volunteers
```python
# Before
"/api/v2/admin/volunteers"

# After
"/api/v2/admin/volunteers/"
```

#### Analytics
```python
# Before
"/api/v2/analytics"

# After
"/api/v2/analytics/"
```

## Additional Fixes

1. **Redis URL**: Changed from `redis://localhost:6379/0` to `redis://redis:6379/0` for Docker networking

2. **Docker Compose Warning**: Removed obsolete `version: '3.8'` declaration

## Verification
After rebuilding and restarting:
```bash
docker-compose build telegram-bot
docker-compose up -d telegram-bot
docker-compose logs telegram-bot --tail=20
```

✅ Bot starts successfully
✅ No 405 errors
✅ Connects to Redis
✅ Ready to handle requests

## Testing Checklist
- [x] Bot starts without errors
- [x] Events menu loads data
- [x] News menu loads data
- [x] No 405 errors in logs
- [x] Redis connection successful
- [ ] Full end-to-end test with all modules

## Files Modified
- `TG_BOT/api/client.py` - Updated API endpoints
- `TG_BOT/.env` - Fixed Redis URL for Docker
- `TG_BOT/docker-compose.yml` - Removed version declaration

## Diagnosis Process

1. **Initial Assumption**: Thought it was an API version issue (v1 vs v2)
2. **Testing**: Tested backend endpoints directly with curl:
   ```bash
   curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v2/events"
   # Result: 405 Method Not Allowed

   curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v2/events/"
   # Result: 200 OK with data
   ```
3. **Root Cause Found**: Trailing slashes were required by FastAPI routing

## Prevention
To avoid this in the future:

1. **Consistent trailing slashes** - Always use trailing slashes in API paths or configure FastAPI to redirect
2. **Test endpoints directly** - When debugging 405 errors, test with curl first
3. **Request logging** - Added detailed logging in `_auth_request()` to show full URLs
4. **Integration tests** - Add tests that verify endpoint URLs match backend expectations

## API Endpoint Reference

| Module | Backend Endpoint | Bot Method | Status |
|--------|-----------------|------------|--------|
| Events | `GET /api/v2/events/` | `get_events()` | ✅ Fixed |
| Courses | `GET /api/v2/courses/` | `get_courses()` | ✅ Already correct |
| Vacancies | `GET /api/v2/vacancies/` | `get_vacancies()` | ✅ Already correct |
| News | `GET /api/v2/news/` | `get_news()` | ✅ Fixed |
| Projects | `GET /api/v2/projects/` | `get_projects()` | ✅ Already correct |
| Volunteers | `GET /api/v2/admin/volunteers/` | `get_volunteers()` | ✅ Fixed |
| Analytics | `GET /api/v2/analytics/` | `get_dashboard_stats()` | ✅ Fixed |
| Auth | `POST /api/v1/telegram-auth/*` | OTP methods | ✅ Correct |

**Note:** Authentication endpoints use `/api/v1/` without trailing slashes and work correctly.

## Key Learnings

1. **FastAPI trailing slash behavior**: FastAPI doesn't automatically redirect between `/path` and `/path/`
2. **Consistency matters**: Some endpoints had trailing slashes, some didn't - causing confusion
3. **Test with actual HTTP calls**: Assumptions about API versions were wrong; direct testing revealed the real issue
4. **Detailed logging helps**: Adding request/response logging in `_auth_request()` will help future debugging
