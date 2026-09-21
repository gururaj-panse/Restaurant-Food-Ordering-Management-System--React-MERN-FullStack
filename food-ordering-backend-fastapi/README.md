# food-ordering-backend-fastapi

Module 3 structure-only skeleton for the Python/FastAPI backend modernization. **No business logic has been migrated yet** — see `docs/module-3-development-plan.md` at the repo root for the implementation sequence.

The existing Node.js backend (`food-ordering-backend/`) is untouched and remains the system of record until each module below is actually migrated.

## What exists

- FastAPI app entry point (`app/main.py`) with lifespan-managed MongoDB (Motor) connection
- Config via `pydantic-settings`, reading the same env var names as the Node backend
- CORS + request-logging middleware
- Centralized exception handling (placeholder shapes — see `app/core/errors.py` docstring)
- Five routers matching the approved target modules (`auth`, `user`, `my_restaurant`/`restaurant`, `order`, `analytics`), all 22 confirmed endpoints wired
- A repository layer (generic Motor CRUD, no business rules) and a service layer (all methods currently raise `NotImplementedFeatureError` → HTTP 501)
- Pydantic schemas matching `TARGET_ERD.md` field-for-field, including the two confirmed data gaps (no `country` on delivery details, no `price` on cart items) preserved as-is
- A real, working health check (`/`, `/health`, `/api/health`)
- `pytest` test structure with smoke tests for the health endpoints and a 501-stub check

## Running it

```bash
cd food-ordering-backend-fastapi
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env         # fill in MONGODB_URI at minimum to exercise DB-backed routes
uvicorn app.main:app --reload --port 8000
```

Without a `.env`/`MONGODB_URI`, the app still boots (health endpoints work); every other route stub still responds, just with a 501.

## Testing

```bash
pytest
```
