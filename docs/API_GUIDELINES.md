# AppSuite Ecosystem — API Guidelines

**Version:** 1.0.0 | **Status:** Production | **Author:** Aachman Studios | **Last Updated:** 2026-08-04

---

## FastAPI Conventions

All AppSuite Jarvis API endpoints follow these conventions.

### Base URL

```
http://localhost:8000/api/v1/
```

### Endpoint Naming

- Resources: plural nouns (`/jobs`, `/assets`, `/providers`)
- Actions: verb + noun (`/jobs/{id}/cancel`)
- No trailing slashes

### HTTP Methods

| Action | Method |
|---|---|
| List resources | `GET /resources` |
| Get one | `GET /resources/{id}` |
| Create | `POST /resources` |
| Update | `PUT /resources/{id}` |
| Delete | `DELETE /resources/{id}` |
| Trigger action | `POST /resources/{id}/action` |

### Response Format

```json
{
  "status": "success" | "error",
  "data": { ... },
  "message": "Optional human-readable message",
  "error": "Error string if status=error"
}
```

### Key Endpoints (from `appsuite/api/routes.py`)

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/jobs` | POST | Submit a new Jarvis job |
| `/api/v1/jobs` | GET | List all jobs |
| `/api/v1/jobs/{id}` | GET | Get job details and status |
| `/api/v1/jobs/{id}/timeline` | GET | Get job event timeline |
| `/api/v1/status` | GET | System status (CPU, RAM, uptime) |
| `/api/v1/providers` | GET | List registered LLM providers |
| `/api/v1/assets` | GET | List asset registry |
| `/api/v1/memory` | GET | Query semantic memory |
| `/docs` | GET | Auto-generated Swagger UI |

### Error Codes

| HTTP Status | Meaning |
|---|---|
| 200 | Success |
| 201 | Created |
| 400 | Bad request (validation error) |
| 404 | Resource not found |
| 422 | Unprocessable entity (Pydantic validation) |
| 500 | Internal server error |

### Authentication

Currently none (development mode). For production deployment, add `APIKeyMiddleware` or JWT bearer token authentication.

---

## Related Documents

| Document | Purpose |
|---|---|
| [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md) | Jarvis engine |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Developer setup |
| [CODING_STANDARD.md](CODING_STANDARD.md) | Code style |
