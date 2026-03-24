# Cinema Showcase

Cinema Showcase is an academic monorepo for a one-hall cinema schedule and ticketing system. The project keeps the backend and frontend separated while sharing one MongoDB-backed domain.

Core entities:

- `Movie`
- `Session`
- `User`
- `Ticket`

The project intentionally keeps the one-hall cinema model. There is no separate `Hall` collection; hall size is defined by backend configuration.

## Technology stack

- Backend: FastAPI, Pydantic v2, Motor, PyMongo
- Frontend: React, Vite, TypeScript
- Database: MongoDB
- Infrastructure: Docker, Docker Compose

## Repository structure

```text
cinema-showcase/
  backend/
    app/
    .dockerignore
    .env.example
    Dockerfile
    requirements.txt
  frontend/
    public/
    src/
    .dockerignore
    .env.example
    Dockerfile
    package.json
    package-lock.json
  docker-compose.yml
  README.md
```

## Dockerized services

Docker Compose starts three services:

- `mongodb`: MongoDB 7 with a persistent named volume `mongo_data`
- `backend`: FastAPI application on port `8000`
- `frontend`: Vite development server on port `5173`

The backend connects to MongoDB through the Docker service name `mongodb`. The frontend keeps using `VITE_API_BASE_URL=http://localhost:8000/api/v1` because API requests are sent by the browser on the host machine, not from inside the container network.

## Environment variables

Create real `.env` files from the examples before building containers.

PowerShell:

```powershell
Copy-Item backend\.env.example backend\.env -Force
Copy-Item frontend\.env.example frontend\.env -Force
```

Bash:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

### Backend variables

`backend/.env` includes:

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

For direct local backend runs, the default MongoDB URI is `mongodb://localhost:27017`.

For Docker Compose runs, `docker-compose.yml` overrides it to `mongodb://mongodb:27017`, so the same `.env` file works in both modes.

### Frontend variables

`frontend/.env` currently needs:

- `VITE_API_BASE_URL=http://localhost:8000/api/v1`

## Admin login for local development and demo

Admin access is determined during registration by the backend setting `ADMIN_EMAILS`.

Actual implementation:

- `backend/app/services/auth.py` assigns role `admin` only when the registering email is present in `settings.admin_emails`
- `backend/app/core/config.py` loads that list from `ADMIN_EMAILS`
- the default template in `backend/.env.example` already contains `ADMIN_EMAILS=["admin@example.com"]`

To create an admin account:

1. Copy `backend/.env.example` to `backend/.env` if you have not done it yet.
2. Open `backend/.env` and set `ADMIN_EMAILS` to the email or emails that should receive admin role on registration.
3. Start the backend or restart the Docker Compose stack after changing the env file.
4. Register a new user with one of those emails from the frontend registration page.
5. Log in with that account.
6. Open `http://localhost:5173/admin` or use the `Admin` action in the header.

Important behavior:

- Existing users are not auto-upgraded when you later add their email to `ADMIN_EMAILS`.
- If you already registered that email as a normal user, use a new admin email, delete that user from MongoDB, or reset the demo database.
- For Docker demo reset, use `docker compose down -v` and then start the stack again. This removes the MongoDB volume and all stored data.

## Frontend browsing flow

The public frontend now has three main browsing entry points:

- Home: `http://localhost:5173/`
  Shows only active movies that currently have at least one upcoming public session. Each card highlights the nearest session and links to movie details or the session page.
- Movies catalog: `http://localhost:5173/movies`
  Shows all stored movies, including inactive titles and movies without scheduled sessions. The page supports search by title, genre filtering, and active/inactive filtering.
- Movie details: `http://localhost:5173/movies/<movie_id>`
  Shows full movie information and all currently available upcoming sessions for that movie, if any exist.
- Schedule: `http://localhost:5173/schedule`
  Shows the public session board as a day-based chronoboard. Pick a day first, then browse sessions for that date with title search, movie filter, and free-seat sorting.

## Docker build and run

### 1. Build images

```powershell
docker compose build
```

### 2. Start the full stack

```powershell
docker compose up
```

To rebuild and start in one command:

```powershell
docker compose up --build
```

To run in detached mode:

```powershell
docker compose up --build -d
```

### 3. Open the application

After startup:

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- Backend health endpoint: `http://localhost:8000/api/v1/health`
- MongoDB host port: `localhost:27017`

## Docker Compose behavior

The Compose setup is aimed at reliable local coursework demonstration:

- MongoDB has a healthcheck before the backend is started
- Backend has a healthcheck before the frontend is started
- MongoDB data is stored in the named volume `mongo_data`
- Frontend dependencies are stored in the named volume `frontend_node_modules`
- Backend source is bind-mounted into the container for local development
- Frontend source is bind-mounted into the container for local development
- Polling-based file watching is enabled for Docker Desktop compatibility on Windows and macOS

## Stopping containers

Stop the running stack:

```powershell
docker compose down
```

Stop the stack and remove MongoDB data:

```powershell
docker compose down -v
```

Use `down -v` only when you intentionally want to reset the database.

## Local non-Docker startup

If you want to run the project without Docker:

Backend:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

MongoDB:

- run MongoDB separately on `localhost:27017`
- keep `MONGODB_URI=mongodb://localhost:27017` in `backend/.env`

## Validation notes

The Docker setup is designed so that these checks should succeed in a normal local Docker Desktop environment:

- `docker compose build`
- `docker compose up`
- backend startup after MongoDB becomes healthy
- frontend startup after backend becomes healthy
- backend connection to MongoDB through `mongodb:27017`
- frontend requests to backend through `http://localhost:8000/api/v1`

## Limitations

- The frontend container runs the Vite development server, not a production Nginx build. This is intentional for local coursework demonstration and faster iteration.
- Live reload depends on bind mounts and polling, so file watching can be slower than a fully native run.
- Docker Desktop or another compatible Docker engine must be running before using `docker compose`.

## Useful commands

```powershell
docker compose logs -f
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f mongodb
docker compose ps
```

## Testing

Backend tests can still be run outside Docker:

```powershell
cd backend
pytest
pytest app/tests/integration -o addopts=
```

The integration suite uses a dedicated MongoDB test database and does not need any change to the one-hall cinema domain model.
