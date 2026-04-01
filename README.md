# Cinema Showcase

> A fullstack one-hall cinema web application for movie browsing, session planning, grouped seat booking, and admin scheduling.

Cinema Showcase is an academic/demo monorepo built around a deliberately focused cinema model: one hall, one schedule lane, five core domain entities, and a clear split between a FastAPI backend, a React frontend, and MongoDB persistence.

It covers the full flow from public browsing to authenticated ticket booking and admin-side movie/session management, including a chronoboard-style planner for scheduling screenings in the single hall.

## At a Glance

| Area | Current implementation |
| --- | --- |
| Architecture | `frontend/` + `backend/` monorepo |
| Backend | FastAPI, Pydantic Settings, Motor, PyMongo |
| Frontend | React, Vite, TypeScript, React Router, Axios, i18next |
| Database | MongoDB single-node replica set with collection validators, indexes, and retry-aware transactions |
| Cinema model | One hall, fixed seat grid from backend settings |
| Public flows | Home, movie catalog, movie details, schedule, session details with multi-seat booking |
| User flows | Registration, login, profile editing, grouped order history, multi-ticket purchase, ticket cancellation |
| Admin flows | Movie management, session planning, attendance, ticket/user overview |
| API docs | Swagger UI at `/docs`, ReDoc at `/redoc` |
| Infrastructure | Docker Compose for MongoDB replica set + backend + frontend |
| Automated tests | Backend unit and integration tests |

## Contents

- [What the System Does](#what-the-system-does)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [Architecture](#architecture)
- [Backend Overview](#backend-overview)
- [Transactional Consistency Layer](#transactional-consistency-layer)
- [Frontend Overview](#frontend-overview)
- [Core Domain Model](#core-domain-model)
- [Roles and Main Flows](#roles-and-main-flows)
- [Schedule, Booking, and Admin Planning](#schedule-booking-and-admin-planning)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)
- [Run Locally](#run-locally)
- [Run with Docker](#run-with-docker)
- [Testing](#testing)
- [Admin Access](#admin-access)
- [API and Swagger](#api-and-swagger)
- [Deployment Notes](#deployment-notes)
- [Current Limitations and Future Work](#current-limitations-and-future-work)

## What the System Does

Cinema Showcase models a **single-hall cinema** where:

- admins maintain a movie catalog;
- admins schedule movie sessions into one shared hall timeline;
- visitors browse the active lineup and public schedule;
- authenticated users choose seats, purchase tickets, and cancel eligible bookings;
- admins monitor attendance, tickets, sessions, and recent users from one dashboard.

The one-hall constraint is intentional. There is **no separate `Hall` entity or collection** in the current model. Hall capacity comes from backend configuration:

- default rows: `8`
- default seats per row: `12`
- default total seats: `96`

## Key Features

- **Movie catalog** with active/inactive titles, genres, age rating, poster URL, and description.
- **Home page rotation** that shows only active movies that already have at least one upcoming session.
- **Public schedule browsing** in two forms: a day-based chronoboard and a filterable session list.
- **Movie details pages** with upcoming sessions for a selected title.
- **Session details pages** with a live seat map and in-page ticket purchase flow.
- **JWT-based authentication** with registration, login, protected profile access, and admin-only routes.
- **Profile management** with editable user data, ticket history, ticket cancellation, and account deactivation.
- **Admin movie management** for creating, editing, deactivating, and conditionally deleting movies.
- **Admin session management** through a drag-and-drop chronoboard/planner for the single hall.
- **Attendance reporting** plus recent tickets and recent users in the admin workspace.
- **Production-like booking consistency** through MongoDB transactions, bounded retry handling, conditional seat-counter updates, and unique active-seat indexing.

## Technology Stack

| Layer | Tools |
| --- | --- |
| Backend API | FastAPI, Uvicorn |
| Backend validation/config | Pydantic v2, `pydantic-settings` |
| Database access | Motor, PyMongo |
| Security | JWT (`python-jose`), Passlib + bcrypt |
| Frontend | React 18, TypeScript, Vite |
| Routing | React Router |
| HTTP client | Axios |
| Localization | i18next, react-i18next |
| Database | MongoDB 7 |
| Containers | Docker, Docker Compose |
| Testing | Pytest, pytest-asyncio, pytest-cov, httpx |

## Architecture

```text
Browser
  -> React + Vite frontend
  -> typed API clients + AuthContext + protected routes
  -> FastAPI routers
  -> service / command / builder layer
  -> repository layer
  -> MongoDB collections (users, movies, sessions, orders, tickets)
```

### Architectural notes

- The repository is split into `backend/` and `frontend/`, but both halves operate on the same domain model.
- The backend follows a clear layered structure: routers -> services/commands -> repositories -> MongoDB.
- The frontend is organized by route pages, reusable widgets, typed API modules, and shared utilities.
- MongoDB stores five main collections: `users`, `movies`, `sessions`, `orders`, and `tickets`.
- Hall geometry is configuration-driven, not data-driven. Seat maps are derived from hall settings and purchased tickets.
- On backend startup, the app connects to MongoDB, applies collection validators, and ensures indexes.

## Backend Overview

### Main backend layers

- `app/api/routers`: HTTP endpoints for auth, movies, schedule, sessions, orders, tickets, users, health, and admin.
- `app/api/dependencies`: reusable auth, pagination, and service wiring.
- `app/services`: business rules for auth, users, movies, schedule, orders, tickets, and admin workflows.
- `app/commands`: focused workflows such as ticket purchase and session cancellation.
- `app/repositories`: MongoDB query layer for each collection.
- `app/db`: connection management, collection validators, and indexes.
- `app/security`: password hashing and JWT token creation/validation.
- `app/tests`: unit and integration coverage.

### Important backend behaviors

- **Mongo bootstrap**: the app pings MongoDB on startup and applies collection validators plus indexes automatically.
- **Standardized responses**: successful endpoints return a common `ApiResponse` envelope with `success`, `message`, `data`, and optional `meta`.
- **Standardized errors**: validation and application errors are returned in a consistent JSON structure.
- **JWT auth**: login uses the OAuth2 password flow; bearer tokens include `sub`, `email`, `role`, and expiry.
- **Automatic status sync**: scheduled sessions are marked `completed` once their end time passes.
- **One-hall enforcement**: overlapping non-cancelled sessions are rejected.
- **Seat uniqueness**: MongoDB keeps a unique partial index on `(session_id, seat_row, seat_number)` for active purchased tickets.
- **Grouped purchases**: one order belongs to one user and one session and contains one or more seat-specific tickets.
- **Transactional booking writes**: critical booking and destructive session writes now go through one shared retry-aware MongoDB transaction runner.

## Transactional Consistency Layer

The current backend treats MongoDB as the primary source of booking correctness. Critical write flows no longer depend on an in-memory per-session lock or on best-effort cleanup after partial failures.

### Why replica set support is required

- MongoDB multi-document transactions require replica set support.
- For local development and demos, this repository runs MongoDB as a **single-node replica set** (`rs0`) rather than as a standalone server.
- That keeps the setup lightweight while still exercising real transaction semantics, commit rules, and rollback behavior.

### Unified transactional flows

- `POST /api/v1/orders/purchase` runs as one transaction: create the `Order`, create all `Ticket` documents, and decrement `Session.available_seats`.
- `PATCH /api/v1/orders/{order_id}/cancel` now runs as one transaction: cancel all still-active tickets in the order, restore the session seat counter by the exact number of newly cancelled seats, and recompute the stored order aggregate.
- `POST /api/v1/tickets/purchase` is now strictly a compatibility wrapper around the same order-based transactional path.
- `PATCH /api/v1/tickets/{ticket_id}/cancel` runs as one transaction: mark the `Ticket` cancelled, increment `Session.available_seats`, and recompute the parent `Order` aggregate.
- `PATCH /api/v1/admin/sessions/{session_id}/cancel` now runs as one transaction: cancel the session, cancel all still-active purchased tickets for that session, restore the seat counter exactly once, and recompute every affected order.
- `DELETE /api/v1/admin/sessions/{session_id}` now verifies ticket absence and deletes the session inside one transaction, so correctness does not depend on a process-local lock during admin cleanup flows.

Because one order belongs to exactly one session in this domain model, a session cancellation now effectively cancels the full order contents of that session. The explicit order-cancel endpoint is still useful for user-driven cancellation before the session starts.

### Retry policy and conflict handling

- All critical transaction bodies now go through one reusable helper: `run_transaction_with_retry(...)`.
- The helper opens a fresh client session per attempt, uses snapshot read concern plus majority write concern, and applies a small bounded backoff between retries.
- `TransientTransactionError` triggers a full transaction retry with a fresh session.
- `UnknownTransactionCommitResult` triggers commit retry handling without rerunning the transaction body.
- Non-retryable business exceptions such as `404`, `409`, and `422` are propagated immediately instead of being swallowed or silently retried.

### Practical guarantees

- Multi-document booking writes are atomic: either every related document update commits or none do.
- Failed purchases do not leave behind partial orders, partial tickets, or partially decremented seat counters.
- Failed ticket cancellations do not leave behind half-cancelled tickets, stale order aggregates, or over-restored seat counters.
- Failed full-order cancellations do not leave behind a mix of cancelled tickets and unreconciled session/order state.
- Failed session-cancellation cascades do not leave behind cancelled sessions with still-active tickets or stale orders.
- Seat conflicts are ultimately resolved by MongoDB itself through the unique partial index on active purchased seats.
- `Session.available_seats` is protected by conditional updates and collection validation, so it cannot validly drop below `0` or rise above `total_seats`.
- Cancelled tickets stop blocking seats because the uniqueness constraint applies only to active purchased tickets.

### Why this is stronger than the old model

- The older consistency story mixed MongoDB transactions with an in-memory `session_write_lock`.
- That lock only serialized writes inside one backend process, which is not a real correctness mechanism for multi-instance or restart scenarios.
- The hardened design now relies on database-native guarantees: transactions, unique indexes, conditional updates, and bounded retry handling for transient write/commit failures.
- This is more production-like than application-level best-effort reconciliation because the database, not local process memory, decides whether a write set commits.

### Remaining limitations

- The repository still uses a **single-node** replica set for coursework/demo convenience. It supports transactions, but it is not equivalent to a production MongoDB cluster.
- The retry policy is intentionally bounded. It improves resilience to transient conflicts and uncertain commit acknowledgements, but it does not hide persistent infrastructure failures or logic bugs.
- The domain is still intentionally limited to **one hall** with a fixed seat grid and no distributed coordination beyond MongoDB itself.

## Frontend Overview

The frontend is a React single-page application with route-level pages, reusable widgets, and typed API wrappers around the backend.

### Main routes

| Route | Purpose |
| --- | --- |
| `/` | Home page with the current active rotation |
| `/movies` | Full movie catalog with title/genre/status filters |
| `/movies/:movieId` | Movie details and upcoming sessions for one title |
| `/schedule` | Public schedule with a day chronoboard and session list |
| `/schedule/:sessionId` | Session details, seat map, and ticket purchase |
| `/login` | Sign-in page |
| `/register` | Registration page |
| `/profile` | Protected user profile and ticket history |
| `/admin` | Protected admin dashboard |

### Frontend structure and behavior

- `src/pages`: route-level screens.
- `src/widgets`: UI building blocks for layout, schedule, admin, movies, tickets, and session booking.
- `src/api`: typed Axios request modules for public and admin endpoints.
- `src/features/auth`: auth context, current-user loading, login/logout, and role handling.
- `src/router`: route definitions plus `ProtectedRoute` for user/admin pages.
- `src/shared`: formatting helpers, query param handling, local storage helpers, and shared UI states.
- `src/i18n`: English and Ukrainian UI resources with a header language switcher.

Auth state is stored in `localStorage`. On app load, the frontend restores the access token, fetches `/users/me`, and clears local auth state automatically if the backend returns `401`.

## Core Domain Model

| Entity | Main fields | Notes |
| --- | --- | --- |
| `Movie` | `title`, `description`, `duration_minutes`, `poster_url`, `age_rating`, `genres`, `status` | Catalog entity managed by admins |
| `Session` | `movie_id`, `start_time`, `end_time`, `price`, `status`, `total_seats`, `available_seats` | One scheduled screening in the single hall |
| `Order` | `user_id`, `session_id`, `status`, `total_price`, `tickets_count`, timestamps | One purchase action for one user and one session |
| `Ticket` | `order_id`, `user_id`, `session_id`, `seat_row`, `seat_number`, `price`, `status`, timestamps | One reserved seat inside one order |
| `User` | `name`, `email`, `role`, `is_active`, timestamps | Registered account with `user` or `admin` role |

### Domain constraints

- There is **no `Hall` collection** in the current backend.
- `Session.status` can be `scheduled`, `cancelled`, or `completed`.
- `Ticket.status` can be `purchased` or `cancelled`.
- Session seat counters cannot exceed total hall capacity.
- Ticket seat coordinates must stay within the configured hall dimensions.

## Roles and Main Flows

| Role | What this role can do |
| --- | --- |
| Guest | Browse the home page, movie catalog, movie details, schedule, and session details |
| Authenticated user | Log in, buy tickets, view personal tickets, cancel eligible tickets, update profile, deactivate account |
| Admin | Everything a user can do, plus access `/admin`, manage movies, manage sessions, and view attendance/ticket/user data |

### Typical public flow

1. Open the home page or movie catalog.
2. Browse a movie and inspect its upcoming sessions.
3. Open a specific session page.
4. Sign in if needed.
5. Choose one or more seats from the map and confirm the purchase.
6. Review the grouped order later from `/profile` and cancel individual tickets if needed.

### Typical admin flow

1. Register and log in with an email configured in `ADMIN_EMAILS`.
2. Open `/admin`.
3. Create or update movie records.
4. Place active movies onto the chronoboard and confirm session drafts.
5. Inspect attendance, recent bookings, and recent users from the same workspace.

## Schedule, Booking, and Admin Planning

### Public schedule

- The public schedule is backed by `GET /api/v1/schedule`.
- It returns **future scheduled sessions only**.
- Supported query parameters include pagination (`limit`, `offset`) plus sorting/filtering (`sort_by`, `sort_order`, `movie_id`).
- The frontend renders this data both as a **day chronoboard** and as a **session list** with title search, day filtering, date ordering, and free-seat ordering.

### Seat booking

- The seat map comes from `GET /api/v1/sessions/{session_id}/seats`.
- Seat availability is derived from the configured hall grid and active tickets for that session.
- The main booking flow is `POST /api/v1/orders/purchase`, which buys one or more seats for the same session in one order.
- Users and admins can now cancel a whole order through `PATCH /api/v1/orders/{order_id}/cancel` instead of cancelling each ticket one by one.
- `POST /api/v1/tickets/purchase` remains available as a backward-compatible single-seat wrapper around the new order flow.
- Order creation, full-order cancellation, ticket cancellation, session-cancellation cascade, order aggregate refresh, and session seat-counter updates now run through one shared retry-aware transaction pattern.
- Ticket cancellation is allowed only before the session starts, and individual tickets from a multi-ticket order can be cancelled independently.
- Regular users can cancel their own eligible tickets from the profile page.
- The backend also allows an admin to cancel any ticket or order through authorized API access, although the current admin dashboard focuses on monitoring rather than a dedicated cancel-order UI.
- When an admin cancels a future session, the backend now automatically cancels all still-active tickets for that session, refreshes the related orders, and frees the affected seats atomically.

### Admin scheduling and chronoboard behavior

- Only **active movies** can be newly scheduled.
- Admins can drag a movie from the planning shelf onto a free slot or select a movie and click a slot.
- A draft session is created in the UI first and becomes persistent only after confirmation.
- New sessions must start in the future, begin between `09:00` and `22:00`, cover at least the selected movie duration, and avoid overlap with another non-cancelled session in the only hall.
- Existing sessions can be edited only while they are still future scheduled sessions with **no purchased tickets**.
- Sessions with stored tickets cannot be deleted; they must be cancelled instead.
- Movies referenced by sessions cannot be deleted; they should be deactivated instead.

## Project Structure

```text
Cinema/
|-- backend/
|   |-- app/
|   |   |-- api/
|   |   |-- builders/
|   |   |-- commands/
|   |   |-- core/
|   |   |-- db/
|   |   |-- repositories/
|   |   |-- schemas/
|   |   |-- security/
|   |   |-- services/
|   |   |-- tests/
|   |   `-- utils/
|   |-- .env.example
|   |-- Dockerfile
|   |-- pyproject.toml
|   `-- requirements.txt
|-- frontend/
|   |-- src/
|   |   |-- api/
|   |   |-- app/
|   |   |-- entities/
|   |   |-- features/
|   |   |-- hooks/
|   |   |-- i18n/
|   |   |-- pages/
|   |   |-- router/
|   |   |-- shared/
|   |   |-- types/
|   |   `-- widgets/
|   |-- .env.example
|   |-- Dockerfile
|   |-- package.json
|   `-- vite.config.ts
|-- docker-compose.yml
`-- README.md
```

## Environment Variables

Create local `.env` files from the examples before running the app:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

PowerShell:

```powershell
Copy-Item backend\.env.example backend\.env -Force
Copy-Item frontend\.env.example frontend\.env -Force
```

### Backend variables

| Variable | Example/default | Purpose |
| --- | --- | --- |
| `PROJECT_NAME` | `Cinema Showcase API` | FastAPI project title |
| `PROJECT_VERSION` | `0.1.0` | API version shown in docs |
| `ENVIRONMENT` | `development` | Runtime environment label |
| `DEBUG` | `true` | Debug mode flag |
| `API_V1_PREFIX` | `/api/v1` | Common API prefix |
| `BACKEND_CORS_ORIGINS` | `["http://localhost:5173","http://127.0.0.1:5173"]` | Allowed frontend origins |
| `MONGODB_URI` | `mongodb://localhost:27017/?replicaSet=rs0&directConnection=true` | MongoDB connection string for the local single-node replica set |
| `MONGODB_DB_NAME` | `cinema_showcase` | Main database name |
| `JWT_SECRET_KEY` | `change-this-secret` | Secret used to sign JWTs |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Access token lifetime |
| `LOG_LEVEL` | `INFO` | Backend logging level |
| `CINEMA_TIMEZONE` | `Europe/Kyiv` | Local cinema timezone |
| `HALL_ROWS_COUNT` | `8` | Hall row count |
| `HALL_SEATS_PER_ROW` | `12` | Seats per row |
| `FIRST_SESSION_HOUR` | `9` | Earliest allowed session start |
| `LAST_SESSION_START_HOUR` | `22` | Latest allowed session start |
| `ADMIN_EMAILS` | `["admin@example.com"]` | Email whitelist for admin registration |

### Frontend variables

| Variable | Example/default | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | Base URL for frontend API calls |

### Test-only overrides

The integration test suite also recognizes:

| Variable | Default | Purpose |
| --- | --- | --- |
| `TEST_MONGODB_URI` | `mongodb://127.0.0.1:27017/?replicaSet=rs0&directConnection=true` | MongoDB URI for integration tests |
| `TEST_MONGODB_DB_NAME` | `cinema_showcase_test` | Dedicated test database name |

## Run Locally

### Prerequisites

- Python `3.12+`
- Node.js and npm
- MongoDB running as a single-node replica set on `localhost:27017`

### 1. Prepare environment files

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

### 2. Start the backend

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment:

- PowerShell: `.venv\Scripts\Activate.ps1`
- cmd: `.venv\Scripts\activate.bat`
- Bash: `source .venv/bin/activate`

Install dependencies and run the API:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Important:

- The backend now requires replica-set-enabled MongoDB because critical booking flows use real multi-document transactions.
- The simplest end-to-end demo path is the full Docker Compose stack.
- If you run the backend outside Docker, the MongoDB instance in `MONGODB_URI` must itself be a replica set reachable from the host machine.

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

### 4. Open the application

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/api/v1/health`

## Run with Docker

### 1. Prepare environment files

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

### 2. Build and start the stack

```bash
docker compose up --build
```

Detached mode:

```bash
docker compose up --build -d
```

### 3. Available services

- `mongodb` on `localhost:27017`
- `backend` on `localhost:8000`
- `frontend` on `localhost:5173`
- `mongodb-init-replica` runs once to initialize the single-node replica set used for transactions

### Docker Compose details

- MongoDB uses a named volume: `mongo_data`
- Frontend dependencies use a named volume: `frontend_node_modules`
- The backend source is bind-mounted into the container
- The frontend source is bind-mounted into the container
- MongoDB starts as `mongod --replSet rs0`
- A one-shot `mongodb-init-replica` container initializes the local single-node replica set
- MongoDB has a healthcheck before replica-set initialization begins
- The backend has a healthcheck before the frontend starts
- Compose overrides backend `MONGODB_URI` to `mongodb://mongodb:27017/?replicaSet=rs0&directConnection=true`
- The frontend still uses `http://localhost:8000/api/v1` because the browser calls the API from the host machine
- Polling-based file watching is enabled for Docker Desktop compatibility

### Stop the stack

```bash
docker compose down
```

To remove the MongoDB volume and reset all stored data:

```bash
docker compose down -v
```

## Testing

The repository currently has **backend automated tests** and **no frontend automated test suite yet**.

### Run the backend test suite

```bash
cd backend
pytest
```

Pytest is configured through `pyproject.toml` and includes coverage by default:

- `--cov=app`
- `--cov-report=term-missing`
- `--cov-report=xml`

### Run only integration tests

```bash
cd backend
pytest app/tests/integration -o addopts=
```

If you are using the Docker Compose MongoDB replica set, run the integration suite from the backend container so `mongodb:27017` remains reachable inside the same Docker network:

```bash
docker compose up -d mongodb mongodb-init-replica
docker compose run --rm -e TEST_MONGODB_URI=mongodb://mongodb:27017/?replicaSet=rs0\&directConnection=true backend pytest app/tests/integration -o addopts=
```

PowerShell:

```powershell
docker compose up -d mongodb mongodb-init-replica
docker compose run --rm -e 'TEST_MONGODB_URI=mongodb://mongodb:27017/?replicaSet=rs0&directConnection=true' backend pytest app/tests/integration -o addopts=
```

The transaction-heavy verification command used for the booking consistency flows is:

```powershell
docker compose run --rm -e 'TEST_MONGODB_URI=mongodb://mongodb:27017/?replicaSet=rs0&directConnection=true' backend pytest app/tests/integration/test_orders_api.py app/tests/integration/test_tickets_api.py app/tests/integration/test_sessions_api.py -o addopts=
```

For the strongest booking-consistency verification, run the retry-helper unit tests locally and the booking-focused integration suite against the Docker replica set:

```powershell
cd backend
pytest app/tests/test_transactions.py -q
cd ..
docker compose up -d mongodb mongodb-init-replica
docker compose run --rm -e 'TEST_MONGODB_URI=mongodb://mongodb:27017/?replicaSet=rs0&directConnection=true' backend pytest app/tests/integration/test_access_control_api.py app/tests/integration/test_schedule_api.py app/tests/integration/test_orders_api.py app/tests/integration/test_tickets_api.py app/tests/integration/test_sessions_api.py -o addopts=
```

### Frontend verification

There is no frontend test runner configured in `package.json` yet. The current lightweight verification command is:

```bash
cd frontend
npm run build
```

### What the backend tests cover

- authentication and access control
- admin registration rules
- movie CRUD and visibility behavior
- schedule filtering, sorting, and validation
- session overlap and edit/cancel restrictions
- order-based multi-ticket purchase, full-order cancellation, and partial ticket cancellation
- session-cancellation cascade into dependent ticket and order state
- transactional commit/rollback behavior for critical booking flows
- retry handling for transient transaction failures
- concurrent purchase protection for the same seat
- overlapping multi-seat order conflict handling
- cancelled-seat reuse and seat-counter invariants
- pagination, password hashing, validators, and indexes

### Integration test database behavior

- Integration tests use a dedicated MongoDB database.
- The default test DB name is `cinema_showcase_test`.
- Integration tests require MongoDB replica set support because they exercise transactional booking flows.
- The suite drops the test database before and after execution.
- The tests refuse to run against the development DB name `cinema_showcase`.
- If MongoDB is unavailable, integration tests are skipped rather than faking a database.

## Admin Access

Admin access is determined **during registration** by the backend setting `ADMIN_EMAILS`.

### How to create an admin account

1. Copy `backend/.env.example` to `backend/.env`.
2. Set `ADMIN_EMAILS` to include the email address that should become an admin.
3. Start or restart the backend.
4. Register a new account from the frontend using that exact email.
5. Log in.
6. Open `/admin` or use the `Admin` button in the header.

### Important admin-role behavior

- The client cannot self-assign the admin role.
- Admin role is assigned server-side only when the registering email matches `ADMIN_EMAILS`.
- Existing users are **not** upgraded automatically if you add their email later.
- If an email was already registered as a normal user, use a new email or reset/remove that user first.
- For a full Docker demo reset, `docker compose down -v` clears the MongoDB volume.

## API and Swagger

### API entry points

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
- Health endpoint: `http://localhost:8000/api/v1/health`

### Main API groups

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/movies`
- `GET /api/v1/movies/{movie_id}`
- `GET /api/v1/schedule`
- `GET /api/v1/schedule/{session_id}`
- `GET /api/v1/sessions/{session_id}/seats`
- `POST /api/v1/orders/purchase`
- `PATCH /api/v1/orders/{order_id}/cancel`
- `POST /api/v1/tickets/purchase`
- `GET /api/v1/tickets/me`
- `PATCH /api/v1/tickets/{ticket_id}/cancel`
- `GET /api/v1/users/me`
- `GET /api/v1/users/me/orders`
- `GET /api/v1/users/me/orders/{order_id}`
- `PATCH /api/v1/users/me`
- `DELETE /api/v1/users/me`
- `GET /api/v1/admin/*`

## Deployment Notes

The repository ships a **local demo/development deployment** through Docker Compose.

That setup is well-suited for coursework, presentations, and local verification, but it is not yet a production deployment package. In the current repository:

- the frontend container runs the Vite development server, not a static production build;
- the MongoDB container is intentionally configured as a **single-node replica set** so the backend can use real transactions while keeping the setup lightweight;
- the deployment is centered around a single backend instance for local/demo use;
- there is no reverse proxy, CI/CD pipeline, or cloud deployment manifest in the repo;
- secrets are environment-based and intended for local setup.

## Current Limitations and Future Work

### Current limitations

- The project is intentionally designed around a **single hall**. Multi-hall scheduling is out of scope for the current domain model.
- Ticket purchase is an **application-level reservation flow**. There is no payment gateway integration.
- One order is intentionally limited to **one session only**. Multi-session baskets are out of scope for the current coursework model.
- Frontend automated tests are not configured yet.
- The booking workflow now depends on MongoDB transactions, unique indexes, and conditional updates rather than on an in-memory per-session lock.
- Poster handling is URL-based; there is no built-in media upload pipeline.
- The repository does not include seed/demo data scripts yet.

### Good next improvements

- Add frontend tests for route flows, auth, and booking interactions.
- Introduce seeded demo content for faster presentations and coursework demos.
- Extend the current transaction/retry model toward multi-instance deployments and richer operational observability.
- Add a production frontend build + reverse proxy deployment path.
- Add an explicit admin bootstrap or seed command instead of relying only on `ADMIN_EMAILS` registration.
