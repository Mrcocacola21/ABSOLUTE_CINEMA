# Contributing

Cinema Showcase is a public coursework/portfolio project. Contributions are welcome when they stay focused, preserve the existing architecture, and avoid unrelated cleanup.

## Setup

1. Create environment files from the examples:

```powershell
copy backend\.env.example backend\.env
copy frontend\.env.example frontend\.env
```

2. Start the development stack with Docker Compose:

```powershell
docker compose up --build
```

3. For local frontend work:

```powershell
cd frontend
npm ci
npm test
npm run build
```

4. For backend tests with MongoDB transactions, prefer the Docker-backed replica set:

```powershell
docker compose up -d mongodb mongodb-init-replica backend
docker compose exec -T -e TEST_MONGODB_URI="mongodb://mongodb:27017/?replicaSet=rs0&directConnection=true" -e TEST_MONGODB_DB_NAME="cinema_showcase_test" backend pytest app/tests -q
```

## Branches

Use short, descriptive branch names:

- `feature/<topic>`
- `fix/<topic>`
- `docs/<topic>`
- `chore/<topic>`

## Code Style

- Follow the existing backend layering: routers stay thin, services coordinate work, repositories isolate database access, and high-risk writes stay transactional.
- Keep frontend changes consistent with the current React, TypeScript, CSS, and widget/page structure.
- Avoid broad refactors unless they are required for the change being made.
- Do not change API contracts without updating the backend, frontend, tests, and README examples together.

## Tests And Checks

Before opening a pull request, run the checks that match your change:

- Backend behavior: `pytest app/tests -q` or the Docker-backed command above.
- Frontend behavior: `npm test` and `npm run build` from `frontend/`.
- Documentation-only changes: review rendered Markdown and verify links.

## Pull Requests

Keep pull requests small and easy to review. Include:

- what changed;
- why it changed;
- what commands were run;
- screenshots or short screen recordings for visible UI changes.

Avoid mixing unrelated formatting, dependency, feature, and documentation changes in one pull request.

## License

By contributing, you agree that your contributions are licensed under the MIT License used by this repository.
