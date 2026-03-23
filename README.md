# Cinema Showcase

Cinema Showcase is an academic monorepo for a one-hall cinema schedule and ticketing system. It keeps the project split into a FastAPI backend and a React frontend so the API, data model, and UI can evolve independently while staying aligned to one shared domain model.

This version is intentionally centered on only four core entities:

- `Movie`
- `Session`
- `User`
- `Ticket`

There is no `Hall` entity in MongoDB and no cinema settings collection. Hall dimensions come from application config.

## Technology stack

- Backend: FastAPI, Pydantic v2, Pydantic Settings, Motor, PyMongo, passlib with bcrypt, python-jose, pytest
- Frontend: React, TypeScript, Vite, React Router, axios, react-i18next
- Database: MongoDB
- Infrastructure: Docker, Docker Compose

## Repository structure

```text
cinema-showcase/
  backend/
    app/
      adapters/
      api/
      builders/
      commands/
      core/
      db/
      factories/
      middleware/
      models/
      observers/
      repositories/
      schemas/
      security/
      services/
      strategies/
      tests/
      utils/
      main.py
    .env.example
    Dockerfile
    pyproject.toml
    requirements.txt
  frontend/
    public/
    src/
      api/
      app/
      entities/
      features/
      hooks/
      i18n/
      pages/
      router/
      shared/
      types/
      widgets/
      main.tsx
    .env.example
    Dockerfile
    package.json
    tsconfig.json
    vite.config.ts
  docker-compose.yml
  .gitignore
  README.md
```

## Domain model

### Movie

- `id`
- `title`
- `description`
- `duration_minutes`
- `poster_url`
- `age_rating`
- `genres`
- `is_active`
- `created_at`
- `updated_at`

Movies store reusable film information that admins manage before placing films into the schedule.

### Session

- `id`
- `movie_id`
- `start_time`
- `end_time`
- `price`
- `status`
- `total_seats`
- `available_seats`
- `created_at`
- `updated_at`

Sessions represent screenings in the single cinema hall. They do not embed hall data. `total_seats` comes from config, while `available_seats` is stored as an optimization for schedule reads.

### User

- `id`
- `name`
- `email`
- `password_hash`
- `role`
- `is_active`
- `created_at`
- `updated_at`

Emails are unique. Roles are string-based and use `user` / `admin`.

### Ticket

- `id`
- `user_id`
- `session_id`
- `seat_row`
- `seat_number`
- `price`
- `status`
- `purchased_at`

Tickets are the source of truth for occupied seats. The unique MongoDB index on `(session_id, seat_row, seat_number)` prevents double booking.

## Backend architecture

The backend keeps a layered structure:

- API layer: route definitions, dependencies, FastAPI wiring
- Service layer: business orchestration
- Repository layer: MongoDB access through Motor
- Schemas/models: request, response, and document typing

Patterns retained because they still fit the project:

- Front Controller: `app/main.py`
- Strategy: schedule sorting
- Command: ticket purchase and session cancellation
- Factory: response shaping and schedule DTO creation
- Builder: attendance report assembly
- Observer: event publishing for ticket/session actions
- Adapter: Mongo `_id` normalization

## Backend API

Public routes:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/health`
- `GET /api/v1/movies`
- `GET /api/v1/movies/{movie_id}`
- `GET /api/v1/schedule`
- `GET /api/v1/schedule/{session_id}`
- `GET /api/v1/sessions/{session_id}/seats`

Authenticated user routes:

- `POST /api/v1/tickets/purchase`
- `GET /api/v1/tickets/me`
- `PATCH /api/v1/tickets/{ticket_id}/cancel`
- `GET /api/v1/users/me`
- `PATCH /api/v1/users/me`
- `DELETE /api/v1/users/me`

Admin routes:

- `GET /api/v1/admin/movies`
- `GET /api/v1/admin/movies/{movie_id}`
- `POST /api/v1/admin/movies`
- `PATCH /api/v1/admin/movies/{movie_id}`
- `PATCH /api/v1/admin/movies/{movie_id}/deactivate`
- `DELETE /api/v1/admin/movies/{movie_id}`
- `GET /api/v1/admin/sessions`
- `GET /api/v1/admin/sessions/{session_id}`
- `POST /api/v1/admin/sessions`
- `PATCH /api/v1/admin/sessions/{session_id}`
- `PATCH /api/v1/admin/sessions/{session_id}/cancel`
- `DELETE /api/v1/admin/sessions/{session_id}`
- `GET /api/v1/admin/tickets`
- `GET /api/v1/admin/users`
- `GET /api/v1/admin/attendance`

The API uses a standardized success/error envelope and exposes Swagger UI at `http://localhost:8000/docs`.

## Implemented backend rules

Already implemented:

- unique email validation
- JWT registration/login flow
- role-based access for `user` and `admin`
- current user profile update and self-deactivation
- public schedule browsing with pagination
- schedule filtering by movie
- schedule sorting by start time, movie title, and available seats
- public movie list + read-one for active movies
- full admin movie CRUD with safe delete/deactivate behavior
- full admin session CRUD with cancel/edit/delete behavior
- seat availability derived from active tickets
- authenticated ticket purchase, list, and cancellation
- admin ticket and user lists
- unique seat per session
- session overlap validation for the one-hall cinema
- session start time validation between `09:00` and `22:00`
- validation that `end_time > start_time`
- validation that a session slot is at least as long as the linked movie duration
- prevention of ticket purchase for cancelled, completed, or past sessions
- seat coordinate validation against configured hall dimensions
- automatic session transition to `completed` once `end_time` has passed
- `available_seats` restoration on valid ticket cancellation

Still intentionally simple:

- no MongoDB transaction around ticket purchase yet
- no refresh tokens or password reset flow
- admin bootstrap is controlled through `ADMIN_EMAILS`

Management rules documented in code and README:

- Movie deletion: hard delete is allowed only if the movie has never been used in any session. If at least one session references the movie, admins must deactivate it instead so schedule and ticket history keep a valid movie record.
- Session deletion: hard delete is allowed only if the session has no stored tickets at all. If tickets exist, admins should cancel the session instead so historical ticket data is preserved.
- Ticket cancellation: cancelled tickets stay stored with `status = cancelled`, restore one `available_seat`, and are allowed only before the session start time. The unique seat index now applies only to active purchased tickets, so a cancelled seat can be bought again.
- User deletion/deactivation: self-service account removal is implemented as soft deactivation (`is_active = false`) instead of hard delete so ticket ownership and audit history remain intact.

## MongoDB collections and indexes

Collections:

- `users`
- `movies`
- `sessions`
- `tickets`

Indexes created on startup:

- `users.email` unique
- `users.role`
- `movies.title`
- `movies.is_active`
- `sessions.movie_id`
- `sessions.start_time`
- `sessions.status`
- `tickets.user_id`
- `tickets.session_id`
- `tickets(session_id, seat_row, seat_number)` unique for active purchased tickets only

## Frontend

The frontend is a React + Vite SPA with these pages:

- home
- schedule
- session details
- login
- register
- profile
- admin dashboard

Implemented frontend behavior:

- login and registration
- protected profile/admin routing
- schedule sorting/filtering synced with URL query params
- separate movie list for schedule filtering
- session details with fixed-size seat map
- ticket purchase request flow with client-side purchasable-state feedback
- profile edit form and self-deactivation
- current user ticket list with cancellation
- admin movie create/read/update/delete/deactivate
- admin session create/read/update/cancel/delete
- admin ticket and user overview panels
- attendance overview

The admin dashboard is intentionally aligned with a timeline/chronoboard direction: movies are managed first, then scheduled into time slots. Drag-and-drop is not implemented yet, but the data model and forms are prepared for that workflow.

## Environment variables

Copy the example files before running:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Backend variables in `backend/.env`:

- `PROJECT_NAME`
- `PROJECT_VERSION`
- `ENVIRONMENT`
- `DEBUG`
- `API_V1_PREFIX`
- `BACKEND_CORS_ORIGINS`
- `MONGODB_URI`
- `MONGODB_DB_NAME`
- `JWT_SECRET_KEY`
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `LOG_LEVEL`
- `CINEMA_TIMEZONE`
- `HALL_ROWS_COUNT`
- `HALL_SEATS_PER_ROW`
- `FIRST_SESSION_HOUR`
- `LAST_SESSION_START_HOUR`
- `ADMIN_EMAILS`

Frontend variables in `frontend/.env`:

- `VITE_API_BASE_URL`, usually `http://localhost:8000/api/v1`

## Local startup

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

MongoDB:

Run MongoDB separately and point `MONGODB_URI` to it.

## Docker Compose startup

```bash
copy backend\.env.example backend\.env
copy frontend\.env.example frontend\.env
docker compose up --build
```

Services:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- MongoDB: `mongodb://localhost:27017`

## Useful commands

Backend:

```bash
cd backend
uvicorn app.main:app --reload
pytest
```

Frontend:

```bash
cd frontend
npm install
npm run dev
npm run build
```

## Testing

Starter backend unit tests currently cover:

- password hashing
- pagination metadata
- schedule sorting strategy selection

Coverage reporting is configured in `backend/pyproject.toml`.

## Notes for further development

- Ticket purchase should later use MongoDB transactions for stronger consistency.
- The admin session board can later be upgraded into a drag-and-drop timeline editor without changing the session model.
- Frontend automated tests and richer error handling are still minimal.
