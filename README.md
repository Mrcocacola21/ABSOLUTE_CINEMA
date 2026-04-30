# Cinema Showcase

> A full-stack one-hall cinema web application with a FastAPI backend, React frontend, MongoDB persistence, transactional seat booking, PDF order receipts, staff QR check-in, attendance reporting, and an admin chronoboard for movie and session planning.

Cinema Showcase is a repository for a single-screen cinema system. It combines public browsing, authenticated booking, and administrator planning inside one codebase. The project is intentionally narrow in scope: there is one physical hall, one timeline of screenings, one shared seat map per session, and a small but coherent domain model built around movies, sessions, tickets, orders, and users.

This README documents the repository as it exists now. It is written to be useful both as project documentation for review/coursework/demo purposes and as a practical guide for running, understanding, and verifying the system.

## Table of Contents

- [1. Project Title](#1-project-title)
- [2. Project Overview](#2-project-overview)
- [3. Key Features](#3-key-features)
- [4. Technology Stack](#4-technology-stack)
- [5. Architecture Overview](#5-architecture-overview)
- [6. Backend Architecture](#6-backend-architecture)
- [7. Frontend Architecture](#7-frontend-architecture)
- [8. Core Domain Model](#8-core-domain-model)
- [9. Movie Model Details](#9-movie-model-details)
- [10. Order and Booking Model](#10-order-and-booking-model)
- [11. Transactional Consistency Layer](#11-transactional-consistency-layer)
- [12. Public User Flows](#12-public-user-flows)
- [13. Admin Flows](#13-admin-flows)
- [14. Chronoboard](#14-chronoboard)
- [15. Localization](#15-localization)
- [16. Genre Normalization](#16-genre-normalization)
- [17. Project Structure](#17-project-structure)
- [18. API Overview](#18-api-overview)
- [19. Environment Variables](#19-environment-variables)
- [20. Running Locally Without Docker](#20-running-locally-without-docker)
- [21. Running With Docker](#21-running-with-docker)
- [22. MongoDB Replica Set Setup](#22-mongodb-replica-set-setup)
- [23. Testing](#23-testing)
- [24. How to Verify Critical Booking Behavior](#24-how-to-verify-critical-booking-behavior)
- [25. Admin Access and Usage Notes](#25-admin-access-and-usage-notes)
- [26. Current Limitations](#26-current-limitations)
- [27. Future Improvements](#27-future-improvements)
- [28. Final Conclusion](#28-final-conclusion)

## 1. Project Title

### Cinema Showcase

Cinema Showcase is a one-hall cinema management and booking application. It provides:

- A public interface for browsing movies and upcoming sessions.
- An authenticated customer flow for purchasing multiple seats, reviewing order details, downloading receipt PDFs, and managing booked tickets.
- An admin interface for maintaining the movie catalog, planning the screening calendar, tracking attendance, validating order QR codes, and managing sessions through a dedicated chronoboard view.

The repository is structured as a monorepo with:

- `backend/` for the FastAPI application.
- `frontend/` for the React application.
- `docker-compose.yml` and `docker/` for local containerized setup.

## 2. Project Overview

Cinema Showcase models the operations of a small cinema with a single screening hall. Instead of solving a multiplex scheduling problem, it focuses on the simpler but still realistic case where every session shares the same room and therefore competes for the same timeline and the same seat capacity.

From a business perspective, the application solves a set of common cinema workflows:

- Present a movie catalog to visitors.
- Publish a schedule of upcoming screenings.
- Allow registered users to inspect a session, view seat availability, and book one or more seats.
- Store bookings in a way that supports grouped purchases, receipt generation, check-in state, and later cancellation logic.
- Give administrators tools to create films, plan and duplicate sessions, cancel screenings, inspect attendance and booking activity, and validate customer order QR codes.

The one-hall model matters because it influences both the user experience and the backend rules:

- Only one session can occupy a time slot at a time.
- Session overlap is forbidden across the entire cinema schedule.
- The seat map is fixed for every screening and comes from backend configuration rather than a separate hall entity.
- Planning can be represented as one schedule lane, which makes the chronoboard practical and understandable.

The system serves several categories of users:

- Public visitors can browse movies, open movie pages, inspect upcoming sessions, and view seat availability.
- Registered users can log in, purchase one or more seats for a session, review their order history, open order details, download PDF receipts, cancel individual tickets, and manage their own profile.
- Administrators can manage the movie catalog, plan or edit sessions, cancel or delete sessions under the allowed rules, inspect tickets and user accounts, validate/check in order QR codes, and use the chronoboard to organize the one-hall schedule.

The repository is clearly aimed at academic/demo usage rather than a production cinema deployment. That is reflected in the local Docker setup, the single-node MongoDB replica set, the absence of external payment processing, and the deliberate focus on correctness of booking flows rather than on broader operational concerns.

## 3. Key Features

The application already contains a meaningful set of implemented features. The most important areas are described below in detail.

### Public movie browsing

The frontend exposes a public-facing movie catalog and a homepage that highlight what the cinema is currently showing and what is coming next. Movie entries include localized title and description fields, duration, optional poster references, optional age rating, normalized genres, and the current movie lifecycle status.

The catalog is not limited to currently active films in the UI. While the public backend endpoint defaults to active-only responses unless `include_inactive=true` is supplied, the frontend intentionally requests inactive-inclusive movie data so that it can present:

- active movies that already have future sessions,
- planned movies that are prepared for future scheduling,
- deactivated titles that still exist in the catalog for reference.

Because the seeded catalog is now substantially larger, the homepage spotlight sections and the full movie catalog also use client-side pagination to keep browsing manageable without turning the demo into an infinite-scroll UI.

### Public schedule browsing

The public schedule is available through both API and UI. The backend exposes upcoming scheduled sessions only through a paginated API, and the frontend renders that data in two complementary ways:

- a visual one-day chronoboard-style view for timeline browsing,
- a list view with additional client-side filtering, sorting, and pagination.

This gives users two practical ways to find screenings: by scanning a day layout or by using list-oriented controls such as date direction, title search, and occupancy-oriented sorting.

### Movie details

Each movie has a dedicated details page. The page loads the selected movie together with that movie's upcoming sessions, displays localized descriptive content, and surfaces summary information such as genres, duration, age rating, status, and the upcoming session window.

This page is important because it connects the catalog and the schedule: it acts as the place where a user can understand a film and then jump directly into a concrete upcoming session.

### Session details

Each upcoming screening has its own session details page. The session view provides session timing, movie information, ticket price, seat counters, and the hall seat map. This is the main entry point into the booking flow.

The backend session details API and seat availability API are intentionally separate:

- session details focus on movie and screening metadata,
- session seats focus on row/seat occupancy in the hall.

### Seat map

The application supports a seat map for the one hall. The hall dimensions are configured on the backend through `HALL_ROWS_COUNT` and `HALL_SEATS_PER_ROW`, and the default repository configuration yields an 8 x 12 hall, which is 96 seats in total.

Seat availability is not purely cosmetic. It is tied to the actual ticket and session state in the database and is protected by transactional booking logic, a partial unique seat index for active tickets, and session seat counters.

### Booking flow

Authenticated users can purchase seats from the session details page. The current frontend uses the order-based purchase API and allows multiple seats to be selected in a single operation. That booking request produces one order and multiple ticket records underneath it.

This matters because a real booking attempt often involves a group rather than a single seat, and the repository has been designed around that grouped purchase model.

### Multi-ticket purchase

The order purchase workflow supports buying multiple seats for one session at once. The backend validates that:

- all requested seats are unique inside the request,
- all seats are within the configured hall bounds,
- the session still exists and is still purchasable,
- enough seats remain available,
- none of the requested seats are already purchased.

If all conditions are satisfied, the system decrements availability and creates the order and all tickets in one transaction.

### Order-based purchase model

The project does not treat every ticket purchase as an isolated event anymore. It has a first-class `Order` entity, and one order groups multiple tickets for one session. This supports a more realistic purchase history, clearer profile pages, active-ticket and ticket-history views, and cancellation logic that can work at either ticket or order level.

The repository still keeps a compatibility endpoint for single-ticket purchase at `POST /tickets/purchase`, but the modern booking flow is order-centric, and the frontend session purchase flow is already built around `POST /orders/purchase`.

### Order details, PDF receipts, and QR validation

Users can open a dedicated order details page from their profile. The details view shows the grouped order, every nested ticket, entry-validity state, and the related session metadata.

The backend can also generate a customer-facing PDF receipt for an order. The PDF includes a signed QR validation URL that points staff to the admin validation page, where the QR is checked against live order, ticket, and session state rather than treated as a static receipt.

### Partial ticket cancellation

Users can cancel one ticket from a multi-ticket order without destroying the whole order. When that happens:

- the ticket status becomes `cancelled`,
- the session available seat counter is restored,
- the parent order aggregate is recalculated,
- the order moves to `partially_cancelled` if at least one purchased ticket remains active.

This is one of the more important domain features because it demonstrates why the grouped order model exists.

### Full-order cancellation

The backend also supports cancelling all active tickets belonging to one order in a single action. The API endpoint is `PATCH /orders/{order_id}/cancel`.

In the current repository state, this is implemented on the backend and covered by tests. The frontend profile page exposes ticket-level cancellation but does not currently provide a dedicated "cancel full order" button. Full-order cancellation can still be exercised through Swagger UI, Postman, or any other authenticated API client.

### Staff check-in

Administrators can validate a customer's order QR code and mark all currently valid unchecked tickets in the order as checked in. After check-in, those tickets keep their historical purchase data but receive `checked_in_at` timestamps and are no longer valid for a second entry scan.

### Session cancellation cascade

Admins can cancel a future session. Session cancellation does not just flip the session status. It also triggers a cascade over dependent bookings:

- the session becomes `cancelled`,
- active tickets tied to that session become `cancelled`,
- seat availability is restored,
- affected order aggregates are refreshed so grouped orders reflect the new state.

This behavior is especially important because it keeps user-visible booking history and administrative session state aligned after a screening is withdrawn.

### Admin movie management

Administrators can:

- create movies,
- edit movie data,
- deactivate movies,
- return deactivated movies to `planned`,
- delete movies only when they have not been used by sessions.

Movie management includes localized title and description editing and genre selection through canonical genre codes rather than raw text.

### Admin session management

Administrators can:

- create sessions,
- update eligible sessions,
- batch-create sessions on multiple dates,
- cancel future sessions,
- delete sessions when deletion rules allow it.

The backend enforces the hall-wide no-overlap rule, future-only scheduling rules, business-hour constraints, and edit/delete restrictions tied to ticket existence and sold seats.

### Admin chronoboard

The admin UI includes a chronoboard designed specifically for the one-hall planning problem. It provides a schedule lane, planning shelf, inspector, and draft workflow so the admin can stage new sessions visually before persisting them.

This is not a decorative feature. It directly supports schedule planning, repeated-date creation, and editing/cancellation workflows from the same planning context.

### Admin attendance and booking reporting

The admin dashboard includes reporting screens for attendance, booking activity, and user accounts. Attendance summaries distinguish active sold tickets, checked-in tickets, unchecked active tickets, cancelled tickets, derived available seats, and fill rate.

Admins can open one session's attendance details to inspect the current seat map, active occupied tickets, cancelled ticket audit rows, buyer context, and order status. The frontend can export that session report as a PDF with summary metrics, a seat usage legend for available/not-used/used/cancelled seats, and a buyer/ticket table.

The booking activity register is filterable by movie, session, order status, ticket state, and date mode, with multi-term search and sorting by latest purchase, oldest purchase, highest value, or largest ticket count.

### Localized movie content

Movie `title` and `description` fields are stored as localized objects with Ukrainian and English values. The frontend can switch languages dynamically, and the backend schemas and validators treat those fields as first-class localized content rather than incidental translations.

Those localized movie fields are also validated by expected language. In practice, `title.uk` and `description.uk` reject clearly English or Latin-only content, while `title.en` and `description.en` reject Cyrillic input without breaking punctuation, numbers, or normal movie-title formatting.

### Normalized genres

Genres are stored as canonical codes rather than arbitrary strings. The backend normalizes known labels and aliases to canonical codes, and the frontend translates those codes into localized labels when rendering forms and views.

This reduces duplicate values such as `"Sci-Fi"`, `"science fiction"`, `"sci fi"`, or localized equivalents being stored as unrelated strings.

### Practical validation tightening

The current repository now applies a stricter but still demo-friendly validation layer in the main authoring and booking flows. In practice, that means:

- movie titles and descriptions are trimmed, required in both locales, and limited to presentation-friendly lengths,
- localized movie fields reject clearly wrong-language content while still allowing punctuation, numerals, and short technical fragments such as `IMAX`,
- localized movie payloads accept only the supported `uk` and `en` keys instead of silently dropping unexpected language codes,
- movie durations, age ratings, poster references, and genre lists are checked more intentionally,
- movie and session create/update payloads reject unexpected fields, and the generated OpenAPI schemas expose that strict shape through `additionalProperties: false`,
- session prices must be positive, realistic, and currency-shaped,
- session slots must be long enough for the movie but cannot drift far beyond the runtime,
- seat coordinates are validated against the fixed one-hall layout with clearer error messages,
- ticket and nested order-ticket states are checked for consistent cancellation metadata,
- profile updates normalize names/emails and reject no-op or same-password changes,
- the React forms provide early UX validation for the same practical limits while the backend remains the source of truth.

### Demo seed data

The backend also includes an explicit demo seeding command that loads a deterministic presentation dataset. The current seed builds a 30-title anime-oriented catalog together with 20 sessions, 5 demo users, 9 grouped orders, and 20 tickets. It includes:

- localized movies in `uk` and `en`,
- a mix of `active`, `planned`, and `deactivated` titles,
- upcoming, completed, and cancelled sessions,
- demo users with login credentials,
- sample grouped orders and tickets so attendance, profile, and reporting views look populated,
- external poster URLs for the seeded movie documents by default,
- optional local SVG poster assets under `frontend/public/demo-posters/`, which are still supported because `poster_url` accepts either absolute HTTP(S) URLs or root-relative asset paths.

### Transactional consistency layer

The backend uses MongoDB transactions for critical seat- and order-changing workflows. That transaction layer is specifically designed for booking correctness:

- it requires replica set mode,
- it retries transient transaction failures,
- it retries uncertain commit results,
- it no longer relies on in-memory locking for correctness.

The result is a system where concurrent purchase and cancellation flows are guarded by database-backed consistency mechanisms rather than by process-local assumptions.

## 4. Technology Stack

Cinema Showcase is implemented with a conventional but solid web stack. The choices match the goals of the repository: clear API boundaries, explicit schema validation, practical frontend ergonomics, and transactional MongoDB behavior.

### Backend stack

| Technology | Current usage in the repository |
| --- | --- |
| Python 3.12+ | Main backend runtime (`pyproject.toml` requires `>=3.12`) |
| FastAPI | HTTP API framework |
| Uvicorn | ASGI server for local and Docker development |
| Pydantic / Pydantic Settings | Request/response schemas and environment-based settings |
| Motor | Async MongoDB driver used by the application layer |
| PyMongo | Transaction options, write concerns, read concerns, and lower-level MongoDB integration |
| python-jose | JWT token creation and validation |
| passlib + bcrypt | Password hashing |
| python-multipart | OAuth2 password form handling for login |
| email-validator | Email validation support in schemas |
| qrcode + Pillow | QR code image generation for order validation receipts |
| ReportLab | PDF receipt generation for customer orders |

### Frontend stack

| Technology | Current usage in the repository |
| --- | --- |
| React 18 | UI rendering |
| TypeScript | Static typing across the frontend |
| Vite | Development server and build tool |
| React Router 7 | Route handling and protected route logic |
| Axios | API client and auth token injection |
| i18next + react-i18next | UI localization and language switching |
| Plain CSS in app styles | Styling and layout, rather than a utility CSS framework |

### Database and persistence

| Technology | Current usage in the repository |
| --- | --- |
| MongoDB 7 | Primary database |
| Single-node replica set | Required for transaction support even in local/demo usage |
| Collection validators | Database-level schema constraints |
| MongoDB indexes | Lookup optimization and booking integrity constraints |

### Testing stack

| Technology | Current usage in the repository |
| --- | --- |
| pytest | Backend test runner |
| pytest-asyncio | Async test support |
| httpx ASGITransport | API integration testing without external HTTP deployment |
| pytest-cov | Coverage reporting configured in backend test settings |

### Docker and local infrastructure

| Technology | Current usage in the repository |
| --- | --- |
| Docker Compose | Starts MongoDB, replica-set init, backend, and frontend together |
| `mongo:7` image | Local database container |
| Replica-set init script | Initializes `rs0` automatically inside the Docker environment |
| Development server containers | Uvicorn reload mode and Vite dev server inside containers |

### Localization and normalization tooling

| Area | Current implementation |
| --- | --- |
| UI localization | `i18next` resources for `uk` and `en` |
| Localized domain fields | `LocalizedText` schemas and frontend localization helpers |
| Genre normalization | Backend canonical registry plus frontend label resolver |

### Transaction and replica-set-related tooling

The repository does not merely connect to MongoDB. It explicitly configures transaction support:

- The backend startup verifies that MongoDB is running in replica-set mode.
- Transaction execution uses MongoDB sessions plus snapshot/majority semantics.
- Docker Compose includes a dedicated `mongodb-init-replica` service so development setup actually matches backend expectations.

## 5. Architecture Overview

At a high level, the repository follows a straightforward split:

- the backend owns domain rules, persistence, validation, authorization, and transactional workflows,
- the frontend owns route composition, view state, rendering, client-side schedule browsing helpers, and localized presentation,
- MongoDB stores the core entities and enforces part of the domain integrity with validators and indexes.

### Backend architecture layers

The backend is not built as one flat file or one large router. Its responsibilities are separated into layers:

- API routers define HTTP endpoints and map requests to services.
- Services hold use-case logic for public reads, authentication, profile operations, and admin operations.
- Commands encapsulate complex state-changing workflows such as grouped purchase or cascading cancellation.
- Repositories isolate collection-level MongoDB access.
- Schemas define typed contracts for requests, responses, and domain DTOs.
- Database support modules create validators, indexes, and transaction helpers.

### Frontend structure

The frontend is organized around:

- route-level pages,
- reusable widgets,
- shared helpers and presentation utilities,
- an explicit API client layer,
- a feature-level auth context,
- localized UI resources.

The public and admin experiences are separated in routing and page composition. Public users interact mostly with `HomePage`, `MoviesPage`, `MovieDetailsPage`, `SchedulePage`, and `SessionDetailsPage`. Administrators work from `AdminDashboardPage`, which brings together movie/session planning and reporting views.

### Database role

MongoDB is not just a document store in this project. It carries multiple responsibilities:

- storing all domain entities,
- enforcing schema constraints through validators,
- enforcing seat uniqueness among active tickets,
- supporting multi-document transactions,
- holding denormalized availability and aggregate fields that are updated transactionally.

### Where business logic lives

Business rules are mostly implemented in backend services and commands. Examples:

- movie status lifecycle rules live in `MovieStatusManager`,
- public schedule assembly lives in `ScheduleService`,
- purchase and cancellation workflows live in command classes,
- admin session rules live in `AdminService`.

The frontend also contains non-trivial client-side logic, but that logic is mostly about presentation and browsing behavior rather than authoritative business state. For example, schedule grouping, search, and sorting helpers live on the frontend, but the actual booking correctness is enforced by the backend.

### Where transactional logic lives

The transaction runner lives in `backend/app/db/transactions.py`, while transaction-aware workflows live in command modules such as:

- `order_purchase.py`
- `ticket_cancellation.py`
- `order_cancellation.py`
- `session_cancellation.py`

These commands use MongoDB sessions and are designed to run atomically across multiple collections.

### Where localization lives

Localization is split between backend and frontend:

- the backend defines localized field schemas and normalizes localized movie content,
- the frontend stores UI translations in `frontend/src/i18n/resources.ts`,
- shared frontend helpers resolve the best localized movie text to display.

### Where genre normalization lives

Genre normalization is centralized in backend core logic and mirrored in frontend shared utilities:

- the backend canonical genre registry lives in `backend/app/core/genres.py`,
- the frontend label resolver and catalog live in `frontend/src/shared/genres.ts`.

### Public and admin flow separation

The separation is clear in both API and UI:

- public API groups cover auth, movies, schedule, tickets, orders, and users,
- admin API groups live under `/admin`,
- public frontend pages are accessible without admin privileges,
- the `/admin` route is protected and requires an authenticated admin role.

## 6. Backend Architecture

The backend application lives in `backend/app/`. It is intentionally modular. The main backend areas and their responsibilities are described below.

### Main backend modules

| Path | Responsibility |
| --- | --- |
| `app/main.py` | FastAPI application assembly, startup/shutdown, middleware, router registration |
| `app/api/routers/` | Public and admin HTTP endpoint definitions |
| `app/api/dependencies/` | Auth, pagination, and service dependency wiring |
| `app/services/` | Use-case orchestration for auth, users, movies, schedule, tickets, orders, and admin operations |
| `app/commands/` | Transaction-oriented workflows for purchase, cancellation, session cascading, and aggregate refresh |
| `app/repositories/` | MongoDB collection access and persistence queries |
| `app/schemas/` | Pydantic request/response and DTO models |
| `app/db/` | Connection management, validators, indexes, transaction runner, collection names |
| `app/core/` | Settings, constants, exceptions, logging, genre registry, response contracts |
| `app/security/` | Password hashing, JWT helpers, and signed order validation tokens |
| `app/factories/` | Response and schedule DTO builders |
| `app/builders/` | Attendance report construction and order PDF rendering |
| `app/strategies/` | Schedule sorting strategies |
| `app/utils/` | Pagination, identifier conversion, order aggregate helpers |
| `app/tests/` | Unit and integration tests |

### API routers

The router layer is split by concern rather than by HTTP verb:

- `auth.py` handles registration and login.
- `movies.py` handles public movie browsing.
- `schedule.py` handles public schedule listing and session details.
- `sessions.py` handles public session seat availability.
- `orders.py` handles grouped purchase and full-order cancellation.
- `tickets.py` handles compatibility single-ticket purchase, current-user tickets, and ticket cancellation.
- `users.py` handles current-user profile, grouped order access, and order PDF downloads.
- `admin.py` handles administrative catalog, schedule, ticket, user, reporting, order validation, and check-in endpoints.
- `health.py` provides a health check endpoint used by Docker healthchecks.

Routers are intentionally thin. They receive validated payloads, inject the appropriate service, and return standardized API response envelopes.

### Services

Service classes own the application-level use cases:

- `AuthService` handles account creation and login.
- `UserService` handles profile updates, deactivation, and admin-side user listing.
- `MovieService` handles public movie catalog reads and visibility filtering.
- `MovieStatusManager` handles automatic synchronization of movie statuses based on future sessions.
- `ScheduleService` builds public schedule and seat map responses.
- `TicketService` handles ticket reads, compatibility purchase, and ticket cancellation.
- `OrderService` handles grouped purchase, grouped order listing/details, PDF receipt generation, QR validation, check-in, and full-order cancellation.
- `AdminService` coordinates admin-facing CRUD, planning, session updates, cancellation, deletion, and attendance reporting.

Services are where routing concerns stop and application concerns begin. They do not usually talk directly to HTTP primitives. Instead, they work with repositories, schemas, and command objects.

### Commands

The command layer is central to the most important state transitions:

- `order_purchase.py` performs grouped booking.
- `ticket_purchase.py` adapts legacy single-ticket purchase to the order flow.
- `ticket_cancellation.py` cancels one ticket and refreshes parent order state.
- `order_cancellation.py` cancels all active tickets in an order.
- `session_cancellation.py` cancels a session and cascades ticket/order consequences.
- `order_aggregate_refresh.py` recalculates stored order state from ticket documents.

These commands are valuable because they keep multi-step workflows explicit and isolated. Without them, booking and cancellation logic would sprawl across services and repositories in a way that would be harder to test and reason about.

### Repositories

Repository classes isolate MongoDB interactions and collection-specific query logic:

- `UserRepository` handles account persistence and email lookups.
- `MovieRepository` handles movie reads, writes, lifecycle-related queries, and status updates.
- `SessionRepository` handles public schedule queries, overlap detection, counter updates, session status changes, and edit/delete helpers.
- `TicketRepository` handles seat-level persistence, ticket listing, active-seat conflict checks, and bulk updates.
- `OrderRepository` handles grouped booking storage and current-user order retrieval.

The repository layer keeps collection queries in one place, which is especially useful for transaction-aware code where multiple collections need to be updated consistently.

### Schemas

The schema layer provides typed contracts for both inputs and outputs:

- auth schemas for tokens and login payloads,
- movie schemas for create/update/read and localized field validation,
- session schemas for schedule items, details, seats, create/update, and batch planning,
- order schemas for grouped purchase requests and grouped order responses,
- ticket schemas for ticket read/list/purchase contracts,
- user schemas for account creation, updates, and reads,
- localization schemas for localized text handling,
- common schemas for pagination, response metadata, and shared structures.

Because this is a FastAPI application, these schemas are also part of the generated OpenAPI documentation.

### Database layer

The database support modules do more than open a client connection:

- `database.py` manages MongoDB connection lifecycle and startup checks.
- `transactions.py` runs retry-aware MongoDB transactions.
- `validators.py` creates or updates collection validators.
- `indexes.py` creates indexes and repairs the legacy seat uniqueness index shape when needed.
- `collections.py` centralizes collection names.

On startup, the backend connects to MongoDB, checks replica-set availability, ensures validators, and ensures indexes. This makes the local environment reproducible and reduces configuration drift between runs.

### Validators and constants

`app/core/` and `app/db/validators.py` work together to codify domain rules:

- lifecycle value enums for movies, sessions, tickets, orders, and roles,
- hall and schedule configuration defaults,
- supported genre codes,
- standardized exceptions and API error responses,
- collection-level validation for localized fields, status enums, seat counters, and cancellation metadata.

This combination means some incorrect states are blocked twice: once in application logic and again at the database layer.

### Tests

The backend test suite covers:

- security and schema behavior,
- transaction retry logic,
- validator and index bootstrap,
- management-service rules,
- public API and admin API integration behavior,
- booking concurrency and rollback scenarios.

Testing is covered in detail later in this document, but from an architectural perspective the important point is that transactional booking logic is not merely asserted informally. It is exercised by dedicated tests.

### Request flow in practice

For a typical state-changing request such as grouped seat purchase, the flow is:

1. The router validates the incoming payload.
2. The service checks the user context and delegates to the command.
3. The command starts a MongoDB transaction through the retry-aware transaction runner.
4. Repositories read and update the relevant collections.
5. Validators and indexes provide additional protection at the database level.
6. The command returns normalized DTO data.
7. The router wraps the data in the standard API response envelope.

This layered flow is one of the repository's stronger design points.

## 7. Frontend Architecture

The frontend lives in `frontend/src/` and is organized as a React application with a practical separation between app-level setup, routing, feature context, API utilities, reusable widgets, and shared helper modules.

### Main frontend modules

| Path | Responsibility |
| --- | --- |
| `src/app/` | App shell, providers, global styles |
| `src/router/` | Route definitions and route guards |
| `src/features/auth/` | Auth context, token persistence, role state |
| `src/api/` | Axios client and API wrappers |
| `src/pages/` | Route-level page components |
| `src/widgets/` | Reusable UI blocks and admin/public view sections |
| `src/entities/` | Small entity-oriented presentational components |
| `src/shared/` | Localization helpers, genre helpers, schedule utilities, presentation helpers, storage utilities, shared UI state components |
| `src/i18n/` | Translation resources and i18n initialization |
| `src/types/` | API and domain TypeScript types |
| `src/hooks/` | Page-level helper hooks such as schedule query parameter handling |

### App setup

The app entry is built from:

- `src/main.tsx`
- `src/app/App.tsx`
- `src/app/providers.tsx`

The providers setup includes routing, auth context, and i18n initialization so the rest of the application can consume authentication state and localized UI strings consistently.

### Routing

The current route set includes:

- `/`
- `/movies`
- `/movies/:movieId`
- `/schedule`
- `/schedule/:sessionId`
- `/login`
- `/register`
- `/profile`
- `/admin`

Protected routing is handled through a dedicated route guard. Unauthenticated users are redirected away from protected pages, and the admin page additionally requires the admin role.

### API layer

The frontend API layer is explicit rather than ad hoc:

- `client.ts` creates the Axios instance and injects the bearer token.
- `auth.ts` wraps registration and login requests.
- `schedule.ts` wraps public movie, schedule, session, and seat-map requests.
- `orders.ts` wraps grouped booking.
- `tickets.ts` wraps ticket listing and ticket cancellation.
- `users.ts` wraps profile and order-history operations.
- `admin.ts` wraps admin-only CRUD and reporting requests.

On unauthorized responses, the API client clears stored auth state so the UI does not continue to behave as if the session were valid.

### Pages

The page layer is the clearest way to understand the frontend surface:

- `HomePage.tsx` builds the landing page using movies plus upcoming schedule data.
- `MoviesPage.tsx` shows the movie catalog with client-side filters by query, genre, and status.
- `MovieDetailsPage.tsx` shows one movie and its upcoming sessions.
- `SchedulePage.tsx` presents public schedule browsing in both board and list form.
- `SessionDetailsPage.tsx` shows one session, its seat map, and the booking panel.
- `LoginPage.tsx` and `RegisterPage.tsx` handle authentication.
- `ProfilePage.tsx` shows profile info, active usable tickets, full ticket history, and ticket-level cancellation.
- `AdminDashboardPage.tsx` hosts the admin interfaces.

### Widgets

Widgets carry most of the page-level UI composition:

- `widgets/movies/` contains catalog and homepage movie cards/banners.
- `widgets/schedule/` contains the public schedule board, list, and toolbar controls.
- `widgets/session/SeatMap.tsx` renders seat availability.
- `widgets/tickets/PurchaseTicketCard.tsx` handles seat selection and purchase submission.
- `widgets/layout/AppLayout.tsx` provides the main app shell.
- `widgets/admin/` contains admin panels for planning and reporting.

### Admin UI

The admin UI is centered around:

- `AdminScheduleManagement.tsx`
- `AttendancePanel.tsx`
- `widgets/admin/chronoboard/`

The schedule management area is the most substantial admin interface. It combines a planning shelf, a timeline, an inspector, and session actions such as duplicate, edit, cancel, and delete.

The attendance panel is broader than its name alone suggests. It includes tabs for:

- attendance insights with active, checked-in, unchecked, cancelled, and available-seat metrics,
- booking activity with movie/session/order-status/ticket-state/date filters, multi-term search, and value/count sorting,
- account visibility.

### Chronoboard-related components

The chronoboard implementation is split into clearly named pieces:

- `ChronoboardHeader.tsx`
- `ChronoboardTimeline.tsx`
- `ChronoboardInspector.tsx`
- `PlanningShelf.tsx`
- `MovieCatalogPanel.tsx`
- `useChronoboardState.ts`
- `types.ts`
- `utils.ts`

That structure mirrors the behavior of the feature: one module for shared state, one for the board, one for the inspector, one for the shelf, and utility/type modules for planning math and data shaping.

### Shared utilities

The shared frontend layer contains a large amount of the repository's UI intelligence:

- `localization.ts` resolves localized text with fallbacks.
- `genres.ts` maps canonical genre codes to localized labels.
- `movieStatus.ts` defines status helpers and schedule-ready checks.
- `scheduleBrowse.ts` powers client-side schedule and catalog filtering/sorting.
- `scheduleTimeline.ts` powers public timeline grouping and day labels.
- `presentation.ts` formats dates, times, and prices.
- `storage.ts` wraps localStorage keys.
- `apiErrors.ts` extracts user-facing error text from API failures.

### Profile and booking views

The authenticated user experience is split between:

- `SessionDetailsPage` for making bookings,
- `ProfilePage` for reviewing profile data, active usable tickets, full grouped order history, and ticket-level cancellation,
- `OrderDetailsPage` for inspecting one grouped order, downloading the PDF receipt, and seeing entry-validity state.

The profile and order details pages are worth calling out because they reflect the backend's grouped order model. The profile separates currently usable tickets from the full historical list, orders are shown with nested tickets, ticket-level cancellation is available directly, and the order detail view exposes the PDF receipt generated for staff QR validation. However, the full-order cancellation endpoint currently remains an API feature rather than a dedicated profile-page control.

## 8. Core Domain Model

The repository centers on five main entities: `Movie`, `Session`, `User`, `Ticket`, and `Order`. They are related but intentionally not overcomplicated.

### Entity relationships at a glance

- One `Movie` can have many `Session` records.
- One `Session` belongs to one `Movie`.
- One `User` can have many `Order` records.
- One `Order` belongs to one `User` and one `Session`.
- One `Order` can contain many `Ticket` records.
- One `Ticket` belongs to one `Session`, one `User`, and usually one `Order`.

There is no separate `Hall` entity in the current repository. The hall is implicit and fixed by backend settings.

### Movie

The `Movie` entity represents a film available to the cinema catalog and schedule.

Important fields include:

| Field | Purpose |
| --- | --- |
| `title` | Localized title object |
| `description` | Localized description object |
| `duration_minutes` | Runtime used in planning validation |
| `poster_url` | Optional absolute image URL or root-relative asset path |
| `age_rating` | Optional age suitability label |
| `genres` | Canonical genre codes |
| `status` | `planned`, `active`, or `deactivated` |

Relationships and lifecycle:

- A movie may exist before it has any sessions.
- A movie becomes operationally significant for the public schedule when future sessions exist.
- Status transitions are influenced both by admin actions and by future-session availability.

### Session

The `Session` entity represents one scheduled screening in the cinema hall.

Important fields include:

| Field | Purpose |
| --- | --- |
| `movie_id` | Link to the movie being shown |
| `start_time` | Session start timestamp |
| `end_time` | Session end timestamp |
| `price` | Ticket price for the session |
| `status` | `scheduled`, `cancelled`, or `completed` |
| `total_seats` | Hall capacity for the session |
| `available_seats` | Denormalized counter of remaining seats |

Relationships and lifecycle:

- A session belongs to one movie.
- Tickets are always purchased against a session.
- A session can be edited only under stricter rules than a movie.
- A session can become completed automatically when time passes and requests trigger synchronization.

### User

The `User` entity represents an account that can authenticate with the system.

Important fields include:

| Field | Purpose |
| --- | --- |
| `name` | Display name |
| `email` | Unique login identifier |
| `role` | `user` or `admin` |
| `is_active` | Soft account state |
| `created_at` / `updated_at` | Audit timestamps |

Relationships and lifecycle:

- A user can buy tickets and own orders.
- A user can update profile data and deactivate their account.
- Admin status is assigned at registration time if the email matches `ADMIN_EMAILS`.

### Ticket

The `Ticket` entity represents one purchased seat for one session.

Important fields include:

| Field | Purpose |
| --- | --- |
| `order_id` | Parent grouped order reference |
| `user_id` | Owning user |
| `session_id` | Session being attended |
| `seat_row` / `seat_number` | Seat coordinates |
| `price` | Ticket price at purchase time |
| `status` | `purchased` or `cancelled` |
| `purchased_at` | Purchase timestamp |
| `cancelled_at` | Cancellation timestamp when applicable |
| `checked_in_at` | Staff check-in timestamp when the ticket has been accepted for entry |

Relationships and lifecycle:

- A ticket belongs to one session and one user.
- In current application flows, tickets are usually created under an order.
- Ticket status and check-in state drive occupancy, cancellation behavior, entry validation, and order aggregate recalculation.

### Order

The `Order` entity groups tickets bought together for one session.

Important fields include:

| Field | Purpose |
| --- | --- |
| `user_id` | Buyer |
| `session_id` | Session for the grouped booking |
| `status` | `completed`, `partially_cancelled`, or `cancelled` |
| `total_price` | Sum of prices of all tickets in the order |
| `tickets_count` | Total number of tickets in the order |
| `created_at` / `updated_at` | Audit timestamps |

Relationships and lifecycle:

- One order belongs to one user and one session.
- An order owns multiple tickets for that same session.
- Order status is derived from the statuses of its tickets.

Important nuance about stored order aggregates:

- `tickets_count` reflects how many tickets belong to the order in total.
- `total_price` reflects the sum of all tickets in that order, not only currently active ones.
- Current-user order responses also provide `active_tickets_count`, `cancelled_tickets_count`, `checked_in_tickets_count`, and `unchecked_active_tickets_count` so the frontend can distinguish the current state from the historical total and entry-validity state.

## 9. Movie Model Details

The movie model deserves its own section because several business rules converge there: public visibility, lifecycle state, localization, and genre normalization.

### Movie statuses

The repository supports three movie statuses:

- `planned`
- `active`
- `deactivated`

#### `planned`

`planned` means the movie exists in the catalog but does not currently have future scheduled sessions. This is the natural status for a new title that has been added by an administrator but not yet placed into the timetable.

Planned movies are useful for:

- preparing catalog data before scheduling,
- showing "coming soon" content in the frontend,
- keeping the planning shelf populated with schedule-ready titles that are not permanently disabled.

#### `active`

`active` means the movie currently has at least one future scheduled session. In other words, `active` is tied to what is actually on the upcoming timetable, not merely to whether the movie is generally enabled.

Administrators do not freely toggle a movie into `active` as a manual display switch. The status is derived from future scheduled session presence through `MovieStatusManager`.

#### `deactivated`

`deactivated` means the movie remains stored in the database but is not available as a schedule-ready active title. It may have been manually deactivated or automatically demoted from `active` after future scheduled sessions disappeared.

Deactivated status is useful because it preserves history and references without implying the film is currently part of the active lineup.

### Automatic status refresh

Movie status synchronization is request-driven rather than background-scheduled. The current backend refreshes movie statuses when relevant endpoints are called. That synchronization does at least two things:

- it marks elapsed sessions as `completed`,
- it updates movie statuses based on whether future scheduled sessions still exist.

The practical consequences are:

- a movie with future scheduled sessions becomes `active`,
- a formerly `active` movie with no future scheduled sessions becomes `deactivated`,
- a `planned` movie stays `planned` until future scheduled sessions are created.

This is accurate for current repository behavior, but it also means status changes are triggered by application activity, not by a separate scheduler process.

### Localized `title`

Movie `title` is stored as a localized object with Ukrainian and English values. The backend normalizes legacy flat strings into the localized structure when possible, and validators expect a localized object format for current documents.

This design is important because the title is not merely translated in the UI. It is treated as real localized content at the data-model level.

### Localized `description`

Movie `description` follows the same pattern as `title`. The admin UI explicitly captures both Ukrainian and English descriptions, the backend stores them as localized fields, and the frontend resolves the best value based on the current language plus fallback logic.

### Normalized `genres`

Movie `genres` are stored as canonical codes rather than free-form strings. The backend accepts several known forms as input and normalizes them into the canonical stored values. The frontend then converts those stored codes into localized user-facing labels.

This means the database remains clean and consistent while the UI remains language-aware.

### Genre codes and translated labels

The stored values are codes such as canonical genre identifiers, not the human-readable labels themselves. Human-readable labels are resolved dynamically:

- in backend validation and normalization logic,
- in frontend shared genre helpers for Ukrainian and English display.

This avoids duplication and keeps storage language-neutral.

### Movie visibility across pages

Movie visibility differs slightly depending on which layer and page is involved.

At the API level:

- `GET /movies` returns only active movies by default.
- `GET /movies/{movie_id}` also requires active status by default.
- Both endpoints accept `include_inactive=true`.

At the frontend level:

- the homepage loads movies with `includeInactive: true`,
- the movies catalog page loads movies with `includeInactive: true`,
- the movie details page also requests inactive-inclusive movie access.

This is why the UI can show planned and deactivated entries even though the default public API behavior is active-only.

### How statuses affect public and admin behavior

#### Public behavior

- `active` movies are considered part of the current public lineup and can naturally appear with future schedule data.
- `planned` movies can appear in catalog-style pages and in the homepage "coming soon" behavior, even though they do not yet have upcoming sessions.
- `deactivated` movies still exist and can still be surfaced by the inactive-inclusive frontend catalog, but they are not treated as currently showing titles.

#### Admin behavior

- Admins can create movies in non-active lifecycle states.
- Admins can deactivate eligible movies.
- Admins can return deactivated movies to `planned`.
- The planning shelf only treats non-deactivated movies as schedule-ready, which means planned and active movies can be selected there, while deactivated ones are excluded.

## 10. Order and Booking Model

The order model is one of the repository's defining design decisions. It is worth describing carefully because it changes how booking, history, and cancellation are represented.

### Why `Order` exists

Without `Order`, every purchased seat would be an isolated ticket and any multi-seat booking would have to be reconstructed indirectly. That would make grouped history, group cancellation, and clear user-facing purchase records more awkward.

`Order` solves that by acting as the parent purchase object. It groups tickets that were purchased together for one session in one transaction.

### One order relates to one session

The repository's order design is deliberately simple:

- one order belongs to exactly one session,
- one order may contain one or many tickets,
- all tickets in that order refer to the same session.

This is a good fit for cinema behavior because one checkout action usually concerns seats for one screening, not an arbitrary basket across unrelated sessions.

### Multiple tickets belong to an order

When a user selects several seats for the same screening and completes purchase:

- one order document is created,
- multiple ticket documents are created,
- each ticket points back to the order,
- the session available seat counter is reduced by the number of seats bought.

The frontend profile page then shows the grouped order with its nested tickets instead of presenting unrelated ticket records with no grouping context.

### Why this is better than one-purchase-one-ticket

The grouped order model improves the system in several ways:

- It matches how users think about a booking: one purchase may contain multiple seats.
- It makes order history easier to read in the profile view.
- It allows one API operation to cancel all active seats in a grouped purchase.
- It supports partial cancellation while still preserving the order record.
- It gives the backend a natural place to store aggregate status and total price information.

### Partial cancellation

Partial cancellation is implemented at ticket level. If an order contains three purchased tickets and the user cancels one of them:

- one ticket transitions from `purchased` to `cancelled`,
- the session seat counter is incremented by one,
- the order aggregate is recomputed from its tickets,
- the order becomes `partially_cancelled` because some tickets remain active and some do not.

This behavior is both visible to users and directly covered by backend tests.

### Full-order cancellation

Full-order cancellation works at order level. When an authenticated owner or an admin cancels an order:

- all still-purchased tickets in that order are cancelled,
- only those active tickets contribute to seat restoration,
- the order aggregate is refreshed and ends up in `cancelled` state if no active tickets remain.

Because the repository keeps historical ticket records instead of deleting them, order cancellation is a state transition, not a destructive delete.

### Order entry validation and check-in

Order details include customer-facing entry metadata:

- `valid_for_entry`,
- `entry_status_code`,
- `entry_status_message`,
- `validation_token`,
- `validation_url`.

The validation token is a signed JWT-style payload whose subject is the order ID and whose token type is dedicated to order validation. Staff-facing validation decodes the token, reloads the live order, session, movie, and tickets, and then classifies the order as valid, cancelled, expired, already used, or invalid.

Admin check-in marks all active unchecked tickets in the order with `checked_in_at`. Checked-in tickets remain historical purchased tickets, but they are no longer cancellable or valid for repeat entry.

### How seat availability is synchronized

Seat availability is represented in more than one way:

- each session stores a denormalized `available_seats` counter,
- each active purchased ticket represents one occupied seat,
- the seat map endpoint derives occupancy from ticket documents,
- a partial unique index prevents two active purchased tickets from claiming the same seat in the same session.

This combination matters. The counter gives efficient availability summaries and quick checks, while the ticket documents and unique index provide authoritative seat occupancy at seat level.

### Compatibility single-ticket endpoint

The repository still includes `POST /tickets/purchase` for compatibility and simpler clients. However, this endpoint is implemented as a wrapper around the grouped order purchase workflow. In practice, the modern booking design is order-first even when only one seat is bought.

## 11. Transactional Consistency Layer

This section is especially important because the correctness of seat booking is one of the most meaningful technical qualities in the repository.

### Why transactions are needed

Booking is not a single-document operation. A successful grouped purchase must update several pieces of state together:

- the session's remaining seat counter,
- the new order document,
- all newly created ticket documents.

Likewise, cancellation workflows may touch:

- tickets,
- orders,
- sessions.

Without transactions, a failure in the middle of one of these workflows could leave the database in a contradictory state. For example:

- seats might be decremented without tickets being created,
- tickets might be cancelled without order aggregates being refreshed,
- a session might be marked cancelled without dependent tickets being updated.

Transactions allow the repository to treat each of these workflows as one all-or-nothing unit.

### Why MongoDB replica set is required

MongoDB transactions require replica-set mode, even for local development. A standalone `mongod` instance does not support the multi-document transaction behavior that this backend depends on.

That is why:

- the default backend `MONGODB_URI` includes `?replicaSet=rs0&directConnection=true`,
- backend startup explicitly checks that the connected MongoDB instance reports a replica-set name,
- Docker Compose includes a dedicated replica-set initialization container.

The system is intentionally strict here. If MongoDB is not in replica-set mode, the backend raises a database exception on startup rather than silently running with broken booking guarantees.

### What flows use transactions

The critical transactional workflows in the current repository include:

- grouped order purchase,
- compatibility single-ticket purchase,
- individual ticket cancellation,
- full-order cancellation,
- session cancellation cascade,
- session deletion paths that depend on safe state transitions.

The most important among these are grouped purchase and the cancellation flows, because they mutate multiple collections and counters together.

### Retry-aware transaction handling

The repository does not just start a transaction once and hope for the best. It wraps transaction execution in retry-aware logic located in `backend/app/db/transactions.py`.

Conceptually, the runner does the following:

1. Start a client session.
2. Open a MongoDB transaction with explicit concerns and preferences.
3. Run the callback that performs the business operation.
4. Attempt to commit.
5. Retry intelligently if MongoDB reports a transient transaction problem or an uncertain commit outcome.

The current implementation uses bounded retries rather than infinite retries. That is the right tradeoff for a demo/coursework system: it improves robustness without pretending to be a full distributed transaction management framework.

### What `TransientTransactionError` means conceptually

`TransientTransactionError` means MongoDB considers the transaction to have failed in a way that may succeed if retried from the beginning. Typical reasons can include temporary write conflicts or transient topology-related conditions.

Conceptually, the important idea is:

- the transaction body may not have committed,
- it is valid to rerun the whole business operation inside a fresh transaction,
- the application must therefore write transaction callbacks in a way that is safe to retry.

The repository follows that model. When MongoDB labels an error as transient, the transaction runner retries the whole operation rather than pretending the partial attempt succeeded.

### What `UnknownTransactionCommitResult` means conceptually

`UnknownTransactionCommitResult` is different. It means the application cannot be sure whether the commit completed successfully. The operation might already be committed, or it might not be.

Conceptually, this is not the same as rerunning the entire callback immediately. If the commit already succeeded, re-running the callback could duplicate effects or hit integrity constraints incorrectly.

That is why the correct response is:

- retry the commit itself when possible,
- do not blindly rerun the whole transaction body just because commit confirmation is uncertain.

The repository's transaction runner follows this distinction. That is an important sign that the transaction support is not superficial.

### Why correctness no longer depends on in-memory session locks

An in-memory lock can only protect one process. It breaks down when:

- the application is restarted,
- multiple worker processes exist,
- another service or script writes to the same database,
- race conditions occur across process boundaries.

The current repository's correctness does not fundamentally rely on such locks. Instead, it relies on database-backed guarantees:

- MongoDB transactions,
- conditional seat-counter updates,
- unique active-seat indexing,
- validators that reject invalid persisted states.

This is a stronger and more realistic integrity model than a process-local lock strategy.

### Additional correctness mechanisms beyond transactions

Transactions are not the only protective layer. The repository also uses:

- a partial unique index on `(session_id, seat_row, seat_number)` for tickets whose status is `purchased`,
- conditional `available_seats` decrement/increment queries,
- collection validators that prevent impossible counter ranges and inconsistent cancellation metadata,
- request-level validation for seat bounds and duplicate seat coordinates.

These defenses work together. Even if one layer misses something, another layer may still reject an invalid state transition.

### What guarantees the system now provides

Within the current repository scope, the system provides meaningful guarantees for the one-hall booking domain:

- Two active tickets cannot occupy the same seat for the same session.
- Multi-seat purchase either completes consistently or rolls back.
- Partial ticket cancellation refreshes parent order state and restores availability.
- Full-order cancellation cancels all active seats in the order consistently.
- Session cancellation propagates to dependent tickets and orders.
- Seat availability counters are not updated independently of ticket/order changes.

These guarantees are particularly strong for a local/demo application because they are based on the database's transaction semantics rather than purely on frontend discipline or optimistic assumptions.

### Seat map consistency behavior

The session seat map endpoint derives availability from active ticket occupancy and compares that with the stored session `available_seats` counter. If the values do not match, the backend logs a warning and returns the derived availability value in the seat response.

This is useful because it means the seat map view is anchored to active ticket state rather than trusting a possibly stale counter blindly.

However, it is important to state the current limitation precisely:

- the current read path detects mismatch,
- it does not automatically repair the stored session document during that read,
- there is no separate background reconciliation worker in the repository.

### Limitations that still remain

Even with transactions, the repository still has practical limits:

- The local setup uses a single-node replica set, not a real fault-tolerant production cluster.
- Transaction retries are bounded, not unbounded.
- There is no external payment or refund subsystem to coordinate with booking state.
- Movie/session lifecycle synchronization is request-driven rather than background-scheduled.
- There is no automated background seat-counter repair process.
- The model is intentionally limited to one hall.

These limitations do not invalidate the correctness work that is present. They simply define its intended scope.

## 12. Public User Flows

The public and authenticated user experience can be described as a sequence of practical flows.

### Browse movies

Users can open the home page or the full catalog page to browse available films. The catalog page offers client-side filtering by:

- search query,
- genre,
- movie status.

Because the frontend loads inactive-inclusive movie data, users can discover not only currently active titles but also planned and deactivated catalog entries.

### Browse the schedule

The schedule page loads upcoming sessions and offers two complementary views:

- a visual public chronoboard organized by day,
- a list view with additional filtering and ordering options.

This gives users a broader picture of what is showing and when, especially in a one-hall setup where the timeline itself is highly informative.

### Open movie details

A user can open a movie page to see:

- localized title and description,
- genres,
- duration and optional age rating,
- lifecycle status,
- the movie's upcoming session window.

From there, the user can jump into the next session or return to the catalog.

### Open session details

A user can open an individual session page to inspect:

- the exact screening time,
- the linked movie information,
- ticket price,
- remaining seat summary,
- seat map and booking controls.

This page is the bridge between browsing and purchase.

### View seat map

The seat map displays seat-by-seat availability for the one hall. Occupied seats are determined from active purchased tickets. The seat grid uses the configured hall dimensions, so it always matches backend seat validation rules.

### Select seats

On the session page, an authenticated user can select multiple seats before submitting a purchase. The frontend groups those seat selections into one order purchase request.

Seat selection itself is only the start of the process. The backend still re-validates all selected seats at purchase time because client-side state alone cannot guarantee availability under concurrency.

### Purchase tickets

When the user submits a purchase:

- the frontend sends a grouped purchase request,
- the backend validates session state, seat bounds, duplicates, and availability,
- the transaction runner executes the booking atomically,
- the user receives grouped order data on success.

This flow intentionally creates an order plus nested tickets rather than unrelated ticket rows.

### View own orders and tickets

The profile page loads grouped current-user orders from `/users/me/orders`. This is the main place where a user can inspect purchase history. The grouped view includes:

- movie and session metadata,
- order status,
- nested ticket rows,
- counts of active, cancelled, checked-in, and unchecked active tickets.

The profile UI separates the default active-ticket view from the complete ticket history. The active tab shows only tickets that are still usable for entry, while the history tab keeps cancelled, checked-in, and past-session ticket records visible for audit and receipt lookup.

From the profile page, a user can open a dedicated order detail view at `/me/orders/{orderId}`. That page shows the full grouped receipt, ticket-level entry validity, usable/used ticket counts, checked-in counts, session details, and a PDF download action.

### Download order PDF

The order PDF is generated on demand by the backend through `/users/me/orders/{order_id}/pdf`. It contains the grouped receipt data and a QR code whose URL points to the admin order-validation page.

The QR code is not the authority by itself. It carries a signed validation token, and the admin validation endpoint checks the current order, ticket, and session state when staff scan or paste it.

### Cancel one ticket

The profile page currently supports cancelling individual tickets. This is the frontend-exposed form of partial cancellation.

After ticket cancellation:

- one seat is freed,
- the order may become `partially_cancelled`,
- remaining tickets in the same order remain intact.

### Cancel full order

The backend supports cancelling a full order, but the current frontend does not expose a dedicated full-order cancellation control. In practice, the flow exists today at API level rather than as a visible UI action.

This distinction is important for technical accuracy:

- full-order cancellation is implemented,
- it is tested,
- it is not currently surfaced by a dedicated frontend button.

## 13. Admin Flows

The admin interface covers both catalog maintenance and schedule operations.

### Create movie

Admins can create a movie with:

- Ukrainian and English title,
- Ukrainian and English description,
- duration,
- poster URL or asset path,
- optional age rating,
- normalized genre codes,
- lifecycle status consistent with admin rules.

New movies are usually created in a pre-scheduling lifecycle state rather than as automatically active items.

### Update movie

Admins can update movie metadata and localized content. This allows the catalog to be corrected or enriched over time without recreating movie records.

### Deactivate movie

Admins can deactivate a movie while preserving its historical references. Deactivation is a soft lifecycle action, not a delete.

The backend guards this carefully. A movie with future scheduled sessions cannot simply be deactivated if that would conflict with the operational schedule state.

### Return deactivated movie to planned

The current repository supports moving a deactivated movie back to `planned`. This is both a backend capability and part of the admin UI logic.

That is useful when a title should return to the pool of schedule-ready movies without being immediately considered active.

### Create sessions

Admins can create individual sessions or batch-create similar sessions across multiple dates. Session creation checks:

- future time only,
- allowed cinema operating window,
- movie duration fit,
- hall-wide overlap conflicts,
- valid price and time data.

### Edit sessions

Admins can edit future scheduled sessions, but only while the stricter editability rules still hold. In particular, the backend requires the session to remain:

- scheduled,
- in the future,
- fully unsold (`available_seats == total_seats`).

That means sold sessions are not silently reshaped under existing customers.

### Cancel sessions

Admins can cancel a future session. This triggers the session-cancellation cascade described earlier, ensuring dependent tickets and orders are updated consistently.

### Delete sessions

Admins can delete a session only when it is truly safe to do so. The current rules are stricter than a simple "no active tickets" check:

- if any ticket documents exist for that session, including historical/cancelled ones, deletion is blocked,
- in those cases, cancellation is the correct operation instead of deletion.

This is a conservative data-retention choice and makes historical references safer.

### Use the chronoboard

The chronoboard is the main admin planning surface. It allows the administrator to:

- choose or drag a movie from the planning shelf,
- place a draft session into a slot on the daily lane,
- inspect and edit the draft in the inspector,
- duplicate a pattern across multiple dates,
- select existing sessions and manage them from the same context.

### Reporting and attendance

The admin dashboard includes reporting views for:

- session attendance summaries with active sold, checked-in, unchecked active, cancelled, available-seat, and fill-rate metrics,
- one-session attendance details with the derived seat map, active occupied tickets, cancelled ticket audit rows, buyer context, and order status,
- PDF attendance exports that include summary metrics, seat usage states, and a buyer/ticket table,
- grouped booking/order activity with nested ticket rows, multi-term search, and filters for movie, session, order status, ticket state, and date,
- user account overview.

This makes the admin area not only a planner but also a monitoring surface.

### Validate order QR and check in

Administrators can open `/admin/order-validation`, paste or scan a customer PDF QR payload, and validate the signed order token. The validation result shows:

- whether the token is trusted,
- whether the order is currently valid for entry,
- movie and session context,
- active, cancelled, checked-in, and remaining ticket counts,
- each ticket's seat and entry-validity state.

When the order is valid for entry, the admin can check it in. This stamps every active unchecked ticket in the order with `checked_in_at`, after which the same QR validates as already used.

### Planning and scheduling workflows

The repository's planning workflow is intentionally visual. Instead of filling only raw forms, the admin can:

1. choose a movie from the planning shelf,
2. click or drag onto the timeline,
3. stage a draft,
4. review or refine timing and pricing in the inspector,
5. save one session or create a batch across selected dates.

This is a strong fit for the one-hall domain because every schedule decision competes for the same single lane.

## 14. Chronoboard

The chronoboard is one of the most distinctive parts of the project and deserves a dedicated section.

### What the chronoboard is

The chronoboard is the admin-facing planning interface for the one-hall cinema schedule. It is effectively a visual planning board for the daily screening lane.

Instead of forcing the admin to think only in raw timestamps and forms, the chronoboard allows schedule decisions to be made visually against a timeline.

### What problem it solves

In a one-hall cinema, every screening competes for the same physical space and therefore the same timeline. The key planning problem is not "which hall?" but "where in the single lane can this screening fit?"

The chronoboard solves that by making conflicts, gaps, and placement more visible. It reduces the chance of planning blindly and fits the repository's single-lane business model better than a generic table-only admin UI.

### Main parts of the chronoboard

The implemented chronoboard consists of several cooperating pieces.

#### Planning shelf

The planning shelf presents schedule-ready movies. In the current UI, this means movies whose status is not `deactivated`, so both `planned` and `active` titles can appear there.

The shelf is searchable and supports selection/dragging, which makes it the natural entry point for drafting new sessions.

#### Timeline

The timeline represents one day in the one-hall schedule. Current behavior includes:

- a visible planning range from 09:00 to 24:00,
- 30-minute slot granularity,
- one lane only, matching the one-hall model,
- visual draft placement,
- existing session selection,
- drag interaction for moving a visible draft block.

The timeline is not just read-only. It is used to create or reposition draft intent before the admin commits anything to the backend.

#### Inspector

The inspector is the detail panel for whatever the admin is currently working with.

It supports several modes:

- draft creation,
- edit existing session,
- duplicate existing session to dates,
- inspect session details with action buttons.

From the inspector, the admin can adjust movie, timing, and price, or trigger save/cancel/delete/duplicate actions as appropriate.

### How scheduling from drafts works

The current chronoboard stages drafts locally first. Clicking or dragging onto the board does not immediately create a real backend session. Instead:

1. a draft is created in frontend state,
2. the draft is shown on the board,
3. the inspector allows refinement,
4. persistence happens only when the inspector form is submitted.

This separation is helpful because it lets the UI support visual planning without prematurely writing incomplete sessions to the database.

### Existing-session workflows

When an existing session is selected from the board, the admin can perform actions such as:

- duplicate the session pattern to selected dates,
- open edit mode,
- cancel the session,
- delete the session if allowed.

This makes the board a lifecycle management surface, not just a creation wizard.

### Duplicate and batch planning behavior

The current implementation supports multi-date planning. An admin can use the inspector to apply the same session pattern across multiple selected dates.

Important current behavior:

- the backend validates each requested date separately,
- partial success is allowed,
- rejected dates are reported back rather than causing silent failure,
- the UI keeps the unresolved selections visible so the admin can adjust and retry.

### Frontend vs backend responsibility

The chronoboard performs useful preliminary checks on the frontend, including overlap and time-window feedback. However, the backend remains authoritative. Final validation still happens server-side when the session is created or updated.

This is the correct architecture because frontend validation improves usability, while backend validation protects actual data integrity.

### Current limitations of the chronoboard

The chronoboard is strong for the one-hall use case, but it has clear current boundaries:

- it is single-lane and single-hall only,
- it does not implement multi-hall planning,
- it does not support drag-resize editing of session duration blocks,
- it does not optimize gaps automatically,
- it works from the loaded dataset rather than from a more advanced live planning engine,
- it does not provide dedicated order-management tools inside the planning view.

## 15. Localization

Localization is implemented at both UI and domain-data levels.

### Current UI localization approach

The frontend uses `i18next` and `react-i18next` with two languages:

- Ukrainian (`uk`)
- English (`en`)

The current language is persisted in localStorage using the `cinema_showcase_language` key. On startup, the frontend reads that persisted value and defaults to Ukrainian if no value exists.

### Ukrainian and English support

Translation resources for the UI live in `frontend/src/i18n/resources.ts`. This file contains the strings used across public pages, profile pages, admin panels, schedule controls, chronoboard text, and feedback messages.

The header includes a language switcher, so users can change UI language during normal use.

### Localized movie fields

Localization is not limited to interface chrome. Movie data itself is localized:

- `title` is localized,
- `description` is localized,
- backend movie create/update validation checks the expected language for each localized field.

The admin movie forms explicitly ask for Ukrainian and English values, which makes localized content part of standard data entry rather than an afterthought.

The current backend rule is intentionally pragmatic rather than ML-based language detection. It is designed to reject clearly misplaced text such as plain English titles in `uk` fields and plain Ukrainian text in `en` fields, while still accepting punctuation, spaces, numerals, and short inline technical tokens that commonly appear in movie metadata.

### Fallback behavior

Movie field resolution follows a practical fallback order:

- use the currently requested/preferred language if available,
- otherwise fall back to Ukrainian,
- otherwise fall back to English.

The frontend implements this in shared localization helpers, and the backend localized text model follows the same conceptual approach.

UI resource fallback is configured separately through `i18next`, where English is the fallback language for translation resources.

### Where translation resources live

The main translation resource file is:

- `frontend/src/i18n/resources.ts`

The i18n initialization is wired through the app setup so page and widget components can call `useTranslation()` directly.

### How localized genre labels work

Genres are stored as canonical codes, not as translated labels. When the UI needs to display them, it resolves the label from the code using the current language.

That means the same movie document can produce:

- English genre labels when the UI is in English,
- Ukrainian genre labels when the UI is in Ukrainian,

without changing the underlying stored movie data.

## 16. Genre Normalization

Genre normalization is a deliberate data-quality feature in this repository.

### Why raw genre strings were a problem

If the system allowed arbitrary raw strings to be stored as genres, the data would quickly fragment. Examples of the same conceptual genre could be stored as many unrelated values due to:

- spelling variation,
- capitalization differences,
- abbreviation,
- language difference,
- synonyms.

That makes filtering, grouping, translation, and consistency much harder.

### Why canonical codes are used

The repository solves this by storing canonical genre codes. Canonical storage provides several benefits:

- one stable value per conceptual genre,
- easier filtering and sorting,
- easier translation into UI labels,
- safer future evolution of the catalog.

### How genre labels are resolved

Genre labels are not stored redundantly in each movie document. Instead:

- the backend keeps a canonical registry of supported genres and known aliases,
- the frontend keeps a matching label catalog for rendering,
- the active UI language determines which user-facing label is shown.

### How admin forms work with genre codes

The admin movie form works with canonical genre codes. Administrators choose from the supported set instead of typing arbitrary raw text. This improves data quality at entry time.

### How legacy labels and synonyms are normalized

The backend normalizer accepts more than just canonical codes. It can recognize known labels and aliases and map them to the canonical stored form. This is especially useful for:

- legacy values,
- human-entered English labels,
- human-entered Ukrainian labels,
- common synonyms such as shortened or variant spellings.

The result is a repository that can be reasonably tolerant on input while remaining strict in storage.

### Current scope of normalization

Genre normalization is strong for the known supported set, but it is still a bounded registry. It is not an open-ended NLP classification system. Unsupported free-form values are not meant to silently become new canonical genres.

## 17. Project Structure

The repository is a monorepo. The simplified source-oriented structure below omits generated/local artifacts such as `frontend/node_modules`, `frontend/dist`, `backend/.venv`, `backend/.pytest_cache`, `__pycache__`, and coverage outputs.

```text
.
├── backend/
│   ├── app/
│   │   ├── adapters/
│   │   ├── api/
│   │   │   ├── dependencies/
│   │   │   └── routers/
│   │   ├── builders/
│   │   ├── commands/
│   │   ├── core/
│   │   ├── db/
│   │   ├── factories/
│   │   ├── middleware/
│   │   ├── models/
│   │   ├── observers/
│   │   ├── repositories/
│   │   ├── schemas/
│   │   ├── security/
│   │   ├── services/
│   │   ├── static/
│   │   ├── strategies/
│   │   ├── templates/
│   │   ├── tests/
│   │   │   └── integration/
│   │   ├── utils/
│   │   └── main.py
│   ├── .env.example
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── requirements.txt
├── docker/
│   └── mongodb/
│       └── init-replica.sh
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── app/
│   │   ├── entities/
│   │   ├── features/
│   │   │   └── auth/
│   │   ├── hooks/
│   │   ├── i18n/
│   │   ├── pages/
│   │   ├── router/
│   │   ├── shared/
│   │   │   └── ui/
│   │   ├── types/
│   │   ├── widgets/
│   │   │   ├── admin/
│   │   │   │   └── chronoboard/
│   │   │   ├── layout/
│   │   │   ├── movies/
│   │   │   ├── schedule/
│   │   │   ├── session/
│   │   │   └── tickets/
│   │   └── main.tsx
│   ├── .env.example
│   ├── Dockerfile
│   ├── index.html
│   ├── package-lock.json
│   ├── package.json
│   └── tsconfig*.json
├── docker-compose.yml
└── README.md
```

### Major directories explained

#### `backend/`

This contains the full FastAPI application, including routing, business logic, persistence, transaction support, and tests.

#### `frontend/`

This contains the React/Vite SPA, including public browsing pages, profile pages, the admin dashboard, localization resources, and the chronoboard implementation.

#### `docker/`

This currently contains MongoDB-specific local infrastructure helpers, most importantly the replica-set initialization script required by the backend transaction model.

#### `docker-compose.yml`

This is the main local orchestration entry point. It starts MongoDB, initializes the replica set, and then starts the backend and frontend development servers with health checks and bind mounts.

## 18. API Overview

The backend is mounted under the `API_V1_PREFIX`, which is `/api/v1` by default. API docs are available through:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

Responses use a standard envelope with fields such as `success`, `message`, `data`, and optional `meta`.

The generated OpenAPI document is also curated rather than purely default-generated: it includes repository contact metadata, explicit tag descriptions, reusable error-response contracts, and Swagger UI settings that keep authorization and request timing visible during manual verification.

### Auth

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/auth/register` | Create a new user account |
| `POST /api/v1/auth/login` | Authenticate with email/password and receive a JWT |

Important notes:

- Login uses an OAuth2 password form style payload.
- Swagger UI's `Authorize` button uses a dedicated hidden `POST /api/v1/auth/token` exchange, while the application itself still logs in through `POST /api/v1/auth/login`.
- Admin role assignment happens during registration if the email is listed in `ADMIN_EMAILS`.
- Registration payloads are strict. Unexpected extra fields such as client-supplied `role` are rejected with request validation errors rather than being silently ignored.
- The JWT is used only to identify the account. Protected requests still reload the current user from MongoDB, so deleted or inactive accounts are rejected even if the token was issued earlier.
- Expired, malformed, or structurally invalid access tokens return standardized `401` authentication errors.

### Movies

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/movies` | Public movie catalog |
| `GET /api/v1/movies/{movie_id}` | Public movie details |

Important notes:

- Both endpoints support `include_inactive=true`.
- Without that flag, public movie access is limited to active movies.

### Schedule and sessions

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/schedule` | List upcoming scheduled sessions |
| `GET /api/v1/schedule/{session_id}` | Detailed data for one session |
| `GET /api/v1/sessions/{session_id}/seats` | Seat map and availability for one session |

Important notes:

- Public schedule returns upcoming `scheduled` sessions only.
- Public query support on the backend currently centers on `limit`/`offset` pagination, `sort_by`/`sort_order`, and optional `movie_id` filtering.
- Schedule list responses include `meta.pagination` with total-count and current-page information.
- Several richer UI filters on the frontend are client-side helpers applied after fetching schedule data.

### Tickets

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/tickets/purchase` | Compatibility single-ticket purchase flow |
| `GET /api/v1/tickets/me` | List current user's tickets |
| `PATCH /api/v1/tickets/{ticket_id}/cancel` | Cancel one ticket |

Important notes:

- The compatibility purchase endpoint delegates to the grouped order purchase logic underneath.
- Ticket cancellation can be performed by the ticket owner or by an admin.

### Orders

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/orders/purchase` | Purchase multiple seats for one session as one order |
| `PATCH /api/v1/orders/{order_id}/cancel` | Cancel all active tickets in one order |

Important notes:

- This is the preferred booking API for the current frontend session purchase flow.
- Successful purchase responses use the enriched order detail shape, including entry-validation metadata and nested ticket validity flags.
- There is no separate admin-only order router; admins may still cancel orders via the regular endpoint because backend authorization allows it.

### Users and profile

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/users/me` | Current authenticated user |
| `GET /api/v1/users/me/orders` | Grouped order history |
| `GET /api/v1/users/me/orders/{order_id}` | One grouped order detail |
| `GET /api/v1/users/me/orders/{order_id}/pdf` | Download a PDF receipt with a staff validation QR code |
| `PATCH /api/v1/users/me` | Update current user profile |
| `DELETE /api/v1/users/me` | Deactivate current user account |

Important notes:

- The frontend `/profile` page is backed by `/api/v1/users/me` and the related current-user order/ticket endpoints. There is no separate backend `/profile` API route.
- `GET /api/v1/users/me` is the backend session-restoration endpoint. It resolves the bearer token, reloads the user from the database, and returns the safe current-user DTO.
- Profile updates allow `name`, `email`, and `password`. Changing `email` or `password` requires `current_password`.
- Profile update payloads are strict. Unexpected privilege-bearing fields such as `role` or `is_active` are rejected with request validation errors.
- Account deactivation is a soft deactivation implemented through `is_active=false`. After deactivation, existing protected requests and fresh logins are both rejected.

### Admin

| Endpoint group | Representative endpoints | Purpose |
| --- | --- | --- |
| Admin movies | `GET/POST/PATCH/DELETE /api/v1/admin/movies...`, `PATCH /api/v1/admin/movies/{movie_id}/deactivate` | Catalog management |
| Admin sessions | `GET/POST/PATCH/DELETE /api/v1/admin/sessions...`, `POST /api/v1/admin/sessions/batch`, `PATCH /api/v1/admin/sessions/{session_id}/cancel` | Session planning and lifecycle management |
| Admin tickets | `GET /api/v1/admin/tickets` | Ticket overview |
| Admin users | `GET /api/v1/admin/users` | User overview |
| Admin reporting | `GET /api/v1/admin/attendance`, `GET /api/v1/admin/attendance/sessions/{session_id}` | Attendance/report summary and one-session details |
| Admin order validation | `GET /api/v1/admin/orders/validate/{token}`, `POST /api/v1/admin/orders/{order_id}/check-in` | Validate signed order QR tokens and confirm entry |

Important notes:

- Admin attendance responses count cancelled tickets separately from active occupancy, so cancelled seats are available again but still visible in reporting/audit detail.
- The admin ticket and booking views expose grouped order context, buyer context, and check-in state without returning password data or raw secrets.

### Health

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/health` | Basic health endpoint used by local checks and Docker |

## 19. Environment Variables

The repository uses environment variables on both backend and frontend. The most important ones are documented here.

### Backend environment variables

The backend example file is `backend/.env.example`.

Create a local `backend/.env` by copying that example file. The real `.env` file is for local/runtime use only, is gitignored, and should never be committed.

| Variable | Example/default | Purpose |
| --- | --- | --- |
| `PROJECT_NAME` | `Cinema Showcase API` | Display name for the backend application |
| `PROJECT_VERSION` | `.env.example` shows `0.1.0` | Version string used by the API |
| `ENVIRONMENT` | `development` | Runtime environment label |
| `DEBUG` | `true` | Debug-oriented behavior toggle |
| `API_V1_PREFIX` | `/api/v1` | Global API prefix |
| `BACKEND_CORS_ORIGINS` | `["http://localhost:5173","http://127.0.0.1:5173"]` | Allowed frontend origins |
| `FRONTEND_BASE_URL` | `http://localhost:5173` | Base frontend URL encoded into order validation QR links |
| `MONGODB_URI` | `mongodb://localhost:27017/?replicaSet=rs0&directConnection=true` | MongoDB connection string |
| `MONGODB_DB_NAME` | `cinema_showcase` | Main application database name |
| `JWT_SECRET_KEY` | `change-this-secret` | JWT signing secret |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Access token lifetime |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `CINEMA_TIMEZONE` | `Europe/Kyiv` | Local cinema timezone for scheduling rules |
| `HALL_ROWS_COUNT` | `8` | Number of seat rows in the hall |
| `HALL_SEATS_PER_ROW` | `12` | Seats per row in the hall |
| `FIRST_SESSION_HOUR` | `9` | Earliest allowed local session hour |
| `LAST_SESSION_START_HOUR` | `22` | Latest allowed local session start hour |
| `ADMIN_EMAILS` | `["admin@example.com"]` | Emails that become admin users at registration time |

Important note about `PROJECT_VERSION`:

- the backend code currently defaults `project_version` to `0.2.0`,
- the example `.env` file still shows `0.1.0`.

If version consistency matters in your setup, set `PROJECT_VERSION` explicitly in `backend/.env`.

### Frontend environment variables

The frontend example file is `frontend/.env.example`.

Create a local `frontend/.env` by copying that example file. The real `.env` file is also gitignored and should stay out of version control.

| Variable | Example/default | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | Base URL used by the frontend Axios client |

### MongoDB and replica-set-related variables

The backend connection string is the main replica-set-related application setting, but the local Docker initialization script also uses a few environment variables:

| Variable | Current usage |
| --- | --- |
| `MONGODB_URI` | Backend connection string that must include replica-set parameters |
| `MONGO_HOST` | Used by `docker/mongodb/init-replica.sh`, defaults to `mongodb:27017` in the init container |
| `REPLICA_SET_NAME` | Used by the init script, defaults to `rs0` |
| `REPLICA_MEMBER_HOST` | Used by the init script for the member host entry |

### Test-related environment variables

Integration tests use their own MongoDB settings, typically supplied via environment variables:

| Variable | Purpose |
| --- | --- |
| `TEST_MONGODB_URI` | MongoDB connection string for integration tests |
| `TEST_MONGODB_DB_NAME` | Test database name; defaults to a dedicated test DB and explicitly rejects the main application DB name |

These test variables are especially important for replica-set-backed integration runs because the test suite depends on transaction support as well.

## 20. Running Locally Without Docker

Running without Docker is supported, but it is a secondary path compared to the provided Docker Compose setup. The main reason is that MongoDB must already be running in replica-set mode for the backend to start successfully.

### Prerequisites

You need:

- Python 3.12 or newer
- Node.js and npm
- MongoDB installed locally
- MongoDB initialized as a replica set, even for one node

### Step 1: Start MongoDB in replica-set mode

If you are starting MongoDB manually, a minimal local example looks like this:

```bash
mongod --dbpath <path-to-db> --bind_ip 127.0.0.1 --replSet rs0
```

Then initialize the replica set once:

```bash
mongosh --eval "rs.initiate({_id:'rs0',members:[{_id:0,host:'127.0.0.1:27017'}]})"
```

After initialization, verify it is writable:

```bash
mongosh --eval "db.hello().isWritablePrimary"
```

The backend expects a connection string like:

```text
mongodb://localhost:27017/?replicaSet=rs0&directConnection=true
```

### Step 2: Configure and run the backend

From the `backend/` directory:

```powershell
cd backend
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

POSIX shell equivalent:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Important backend notes:

- Update `JWT_SECRET_KEY` in `.env` before real use.
- Make sure `MONGODB_URI` points to your replica-set-enabled MongoDB instance.
- If MongoDB is not a replica set, startup will fail intentionally.
- Keep `backend/.env` local only and do not commit it.

### Step 3: Configure and run the frontend

From the `frontend/` directory:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

POSIX shell equivalent:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Keep `frontend/.env` local only and do not commit it.

### Step 4: Open the application

When both services are running successfully, the default local URLs are:

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000/api/v1`
- Swagger UI: `http://localhost:8000/docs`

### Optional: Seed demo data

From the `backend/` directory, run:

```powershell
python -m app.seeds.demo_seed --reset
```

If you only want to refresh the deterministic demo records without clearing the whole domain dataset first, run:

```powershell
python -m app.seeds.demo_seed
```

What the seed command does:

- inserts a mostly anime-oriented localized movie catalog,
- creates deterministic sessions for schedule and chronoboard demos,
- creates demo users plus an admin account,
- adds a controlled set of orders and tickets for attendance/profile views.

Seeded demo credentials after running the command:

- `admin`: `admin@cinema-showcase.dev` / `CinemaDemo123!`
- `user`: `chihiro@cinema-showcase.dev` / `CinemaDemo123!`
- `user`: `taki@cinema-showcase.dev` / `CinemaDemo123!`
- `user`: `suzu@cinema-showcase.dev` / `CinemaDemo123!`
- `user`: `ashitaka@cinema-showcase.dev` / `CinemaDemo123!`

### Caveats for non-Docker local runs

- This path is more manual because MongoDB replica-set initialization is your responsibility.
- The backend hard-requires replica-set mode.
- No helper script in the repository fully automates non-Docker local MongoDB setup.
- If you want the quickest reliable setup, Docker Compose is easier.

## 21. Running With Docker

The repository includes a complete Docker Compose setup for local development. This is the primary recommended way to run the stack because it also automates the MongoDB replica-set requirement.

### What Docker Compose starts

The current `docker-compose.yml` defines four services:

| Service | Role |
| --- | --- |
| `mongodb` | Main MongoDB database container |
| `mongodb-init-replica` | One-shot container that initializes the single-node replica set |
| `backend` | FastAPI development server container |
| `frontend` | Vite development server container |

### How Compose is structured

#### `mongodb`

The MongoDB service:

- uses the `mongo:7` image,
- starts `mongod --bind_ip_all --replSet rs0`,
- exposes port `27017`,
- stores data in the named volume `mongo_data`,
- includes a ping-based healthcheck.

#### `mongodb-init-replica`

This is a one-time helper container that:

- waits for MongoDB to respond,
- checks whether the replica set already exists,
- runs `rs.initiate(...)` if necessary,
- waits until MongoDB reports itself writable as primary.

This service is essential because the backend depends on transactions and therefore on replica-set mode.

#### `backend`

The backend service:

- builds from `./backend`,
- loads variables from `./backend/.env`,
- overrides `MONGODB_URI` so the container talks to `mongodb` inside the Compose network,
- mounts `./backend:/app` for live development,
- runs `uvicorn app.main:app --reload`,
- exposes port `8000`,
- waits for MongoDB health and successful replica initialization before starting,
- provides a healthcheck against `/api/v1/health`.

#### `frontend`

The frontend service:

- builds from `./frontend`,
- loads variables from `./frontend/.env`,
- mounts the source directory for live development,
- stores container-side `node_modules` in a named volume,
- runs the Vite development server,
- exposes port `5173`,
- waits for the backend healthcheck before starting.

### Initial setup before `docker compose up`

Create real `.env` files from the examples:

```powershell
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env
```

POSIX shell equivalent:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Those generated `.env` files are intended for local configuration only and should not be committed.

Adjust at least:

- `backend/.env` -> `JWT_SECRET_KEY`
- `backend/.env` -> `ADMIN_EMAILS` if you want to create an admin account immediately

### Start the stack

```bash
docker compose up --build
```

If you prefer detached mode:

```bash
docker compose up --build -d
```

### What happens during startup

The startup sequence is roughly:

1. `mongodb` starts and becomes healthy.
2. `mongodb-init-replica` initializes or confirms `rs0`.
3. `backend` starts, confirms replica-set mode, ensures validators and indexes, and becomes healthy.
4. `frontend` starts after the backend healthcheck passes.

### What to expect when it works

Once everything is healthy, you should be able to open:

- `http://localhost:5173` for the frontend
- `http://localhost:8000/docs` for the API documentation

The backend should respond successfully from:

```text
http://localhost:8000/api/v1/health
```

### Optional: Seed demo data inside Docker

After the stack is healthy, seed the presentation dataset with:

```bash
docker compose exec backend python -m app.seeds.demo_seed --reset
```

To refresh only the deterministic demo records without wiping every domain collection first:

```bash
docker compose exec backend python -m app.seeds.demo_seed
```

### Stop the stack

```bash
docker compose down
```

To also remove named volumes:

```bash
docker compose down -v
```

Be careful with `-v` because it removes the MongoDB data volume and therefore clears the local database state.

### Healthchecks

Healthchecks are meaningful in this setup:

- MongoDB healthcheck confirms the server responds to a ping.
- Backend healthcheck confirms the FastAPI app is serving `/api/v1/health`.
- Service dependencies use these health checks so startup order reflects actual readiness rather than just process launch.

### Important scope note

The Compose setup is a development/demo environment. It runs:

- a reloading backend development server,
- a Vite development server,
- a single-node MongoDB replica set.

It is not a production deployment profile with reverse proxying, TLS termination, or hardened container orchestration.

## 22. MongoDB Replica Set Setup

MongoDB replica-set mode is central enough to deserve its own section.

### Why replica set mode is used even locally

The backend uses multi-document transactions. MongoDB only supports these in replica-set or sharded-cluster configurations. Even a local demo environment therefore needs replica-set mode if the project is to behave like the code expects.

This is why the repository does not treat replica-set setup as optional infrastructure polish. It is a direct prerequisite for core booking behavior.

### How the single-node replica set works here

The local Docker setup uses one MongoDB node and initializes it as replica set `rs0`. This gives the application the MongoDB feature set it needs for transactions without requiring a multi-node cluster for everyday development.

Conceptually, that means:

- there is only one actual database node,
- MongoDB still exposes the replica-set semantics needed by transactions,
- the application can open sessions and run transactional commands.

### Why this is enough for development and demo usage

For local development and coursework/demo review, a single-node replica set is a practical compromise:

- it is much easier to run than a real cluster,
- it still enables the required transaction features,
- it keeps the environment close enough to the assumptions of the backend code.

### Why it is not the same as a production cluster

A single-node replica set is not equivalent to a production deployment. It does not provide:

- real node redundancy,
- failover resilience,
- cluster-level operational characteristics.

So while it is enough to validate transactional correctness in this repository, it should not be mistaken for a production-grade high-availability data topology.

## 23. Testing

The repository includes a real backend test suite. Testing is one of the stronger areas of the codebase, especially around booking and transactional behavior.

### What kinds of tests exist

Current automated tests are backend-focused and fall into two broad categories:

- unit-style tests for helpers, validators, strategies, and transaction logic,
- integration tests for API behavior and booking workflows against MongoDB.

There is currently no equivalent automated frontend test suite in the repository.

### Backend unit-style test coverage

The following backend test files exist in `backend/app/tests/`:

| Test file | Main focus |
| --- | --- |
| `test_jwt.py` | JWT claim generation and expiry handling |
| `test_demo_seed.py` | Demo dataset shape, seeded credentials, and schema-level validation of seeded records |
| `test_indexes.py` | Index bootstrap and legacy seat-index replacement behavior |
| `test_management_services.py` | Management service rules, movie normalization, lifecycle constraints, profile update guardrails |
| `test_movie_localization_validation.py` | Language-aware validation for localized movie titles and descriptions |
| `test_openapi.py` | OpenAPI metadata, Swagger auth flow, and documented error-contract regression coverage |
| `test_order_validation_pdf.py` | Signed order validation tokens and PDF receipt generation |
| `test_pagination.py` | Pagination helper behavior |
| `test_schedule_strategy.py` | Schedule sorting strategy logic |
| `test_security.py` | Password hashing and security helpers |
| `test_session_schema.py` | Session schema validation rules |
| `test_transactions.py` | Transaction retry and commit-retry behavior |
| `test_validators.py` | Collection validator bootstrap |

These tests matter because they exercise the supporting mechanics that transactional booking depends on.

### Backend integration test coverage

The integration suite lives in `backend/app/tests/integration/`:

| Test file | Main focus |
| --- | --- |
| `test_access_control_api.py` | Protected-route access control, admin requirements, invalid/expired/malformed tokens, inactive or deleted users, anonymous booking rejection |
| `test_admin_registration_api.py` | Admin role assignment through `ADMIN_EMAILS` and rejection of client-supplied role fields |
| `test_auth_users_api.py` | Registration, login, `/users/me`, password changes, strict profile updates, and account deactivation behavior |
| `test_demo_seed.py` | Explicit demo seed command behavior and seeded collection insertion |
| `test_movies_api.py` | Public/admin movie behavior, lifecycle transitions, deactivation/reactivation rules, include-inactive access |
| `test_order_details_api.py` | Current-user order details, PDF download, admin QR validation, and check-in behavior |
| `test_orders_api.py` | Multi-ticket grouped purchase, race/conflict handling, rollback, retry behavior, partial and full cancellation |
| `test_schedule_api.py` | Public schedule listing, details, seat map, time-based completion synchronization |
| `test_sessions_api.py` | Session create/update/delete/cancel rules, overlap rejection, batch planning behavior, cascade rollback |
| `test_tickets_api.py` | Ticket purchase, cancellation, concurrency, seat conflicts, bounds validation, sold-out behavior |

### Transaction-related and booking-consistency testing

The repository does not only test the happy path. The suite includes coverage for situations such as:

- duplicate seat requests,
- already-occupied seats,
- hall-bound violations,
- sold-out sessions,
- overlapping purchase races,
- rollback on insert/update failure,
- retry handling for transient transaction failures,
- cascade correctness when session cancellation fails or succeeds.

This is exactly the sort of coverage that matters for a booking-oriented system.

### Replica-set-backed integration test path

Integration tests depend on MongoDB replica-set support. The test configuration:

- expects a dedicated test database,
- defaults to a replica-set MongoDB URI,
- rejects the main production/development DB name for safety,
- skips when the required database conditions are unavailable.

This means the integration suite is aligned with the same transactional assumptions as the running application.

### Exact commands to run tests

#### Run all backend tests locally

```bash
cd backend
pytest
```

Because the backend test configuration includes coverage options in `pyproject.toml`, this command runs with the configured pytest addopts.

#### Run only the backend integration suite locally

```bash
cd backend
pytest app/tests/integration -o addopts=
```

The `-o addopts=` form is useful when you want a simpler run without the default coverage configuration layered on top.

#### Run focused transaction tests locally

```bash
cd backend
pytest app/tests/test_transactions.py -q
```

#### Bring up only MongoDB services with Docker and run integration tests in the backend container

```bash
docker compose up -d mongodb mongodb-init-replica
docker compose run --rm -e "TEST_MONGODB_URI=mongodb://mongodb:27017/?replicaSet=rs0&directConnection=true" backend pytest app/tests/integration -o addopts=
```

#### Run a focused integration subset for access control, schedule, orders, tickets, and sessions in Docker

```bash
docker compose run --rm -e "TEST_MONGODB_URI=mongodb://mongodb:27017/?replicaSet=rs0&directConnection=true" backend pytest app/tests/integration/test_access_control_api.py app/tests/integration/test_schedule_api.py app/tests/integration/test_orders_api.py app/tests/integration/test_tickets_api.py app/tests/integration/test_sessions_api.py -o addopts=
```

### Validation audit verification

After the validation and Swagger-readiness audit, the following checks were run successfully:

```bash
docker compose run --rm -e "TEST_MONGODB_URI=mongodb://mongodb:27017/?replicaSet=rs0&directConnection=true" backend pytest -o addopts=
npm run build
docker compose run --rm backend python -c "from app.main import app; schema=app.openapi(); names=['MovieCreate','MovieUpdate','SessionCreate','SessionUpdate','SessionBatchCreate','LocalizedText','LocalizedTextUpdate']; print({name: schema['components']['schemas'][name].get('additionalProperties') for name in names})"
git diff --check
```

Observed results:

- backend test suite: passed,
- frontend production build: passed, with the existing Vite large chunk warning,
- OpenAPI strict write schemas: all checked schemas reported `additionalProperties: false`,
- diff whitespace check: no whitespace errors, only Git line-ending conversion warnings on Windows.

### What the tests verify in practical terms

At a practical system level, the tests verify that:

- authentication and role checks work,
- public browsing endpoints shape data correctly,
- movie lifecycle and visibility rules behave as expected,
- session overlap and planning rules are enforced,
- grouped bookings are created atomically,
- concurrent seat conflicts are rejected safely,
- partial ticket cancellation updates order and session state correctly,
- full-order cancellation works,
- order PDFs are generated with signed QR validation payloads,
- admin QR validation distinguishes valid, cancelled, expired, already-used, invalid, and missing-order cases,
- admin check-in stamps tickets and blocks repeat entry/cancellation,
- session cancellation cascades through tickets and orders,
- validators and indexes required for consistency are bootstrapped correctly.

### What is not currently covered by automated tests

The important omissions are:

- there is no frontend automated test suite in the current repository,
- there is no end-to-end browser automation suite,
- manual verification is still important for UI behaviors such as language switching and chronoboard interaction.

## 24. How to Verify Critical Booking Behavior

If you want to manually verify the most important behaviors in a running environment, the checklist below is the most practical path.

### 1. Verify multi-ticket purchase

1. Start the stack and create/login as a normal user.
2. Ensure at least one future scheduled session exists.
3. Open that session page from the schedule.
4. Select multiple free seats.
5. Purchase them in one action.
6. Confirm that:
   - the purchase succeeds once,
   - the profile page shows one grouped order with multiple nested tickets,
   - session availability is reduced by the correct number of seats,
   - those seats now appear occupied in the seat map.

### 2. Verify order PDF and staff QR check-in

1. Open a purchased order from the profile page through its details action.
2. Download the order PDF and confirm it opens as a receipt with the order's ticket data.
3. Log in as an admin and open `/admin/order-validation`.
4. Paste the QR validation URL or signed token from the order detail/PDF flow.
5. Confirm that:
   - the validation result reports the order as valid for entry,
   - movie, session, order, ticket, and seat data are shown,
   - checking in the order marks all active unchecked tickets as checked in,
   - validating the same QR again reports it as already used.

### 3. Verify partial ticket cancellation

1. Use an order containing at least two purchased tickets.
2. Open the profile page.
3. Cancel exactly one ticket.
4. Confirm that:
   - the cancelled ticket changes state,
   - the order remains present,
   - the order status becomes `partially_cancelled`,
   - exactly one seat is restored to availability,
   - other tickets in the same order remain active.

### 4. Verify full-order cancellation

This flow is currently best tested through Swagger UI or another API client because the frontend does not expose a dedicated full-order cancellation button.

1. Purchase a multi-ticket order.
2. Find the order ID via `/api/v1/users/me/orders` or the profile page network data.
3. Call `PATCH /api/v1/orders/{order_id}/cancel` with the authenticated user's token.
4. Confirm that:
   - all active tickets in that order become cancelled,
   - the order status becomes `cancelled`,
   - all affected seats become available again.

### 5. Verify session-cancellation cascade

1. Buy one or more tickets for a future session.
2. Log in as an admin.
3. Open the admin dashboard and select that session in the chronoboard or session management area.
4. Cancel the session.
5. Confirm that:
   - the session status becomes `cancelled`,
   - dependent tickets are no longer active,
   - grouped orders tied to the session reflect cancellation state,
   - the seat map no longer shows those seats as occupied.

### 6. Verify admin planning flows

1. Create a new movie in the admin area with both localized title and description fields.
2. Use the chronoboard planning shelf to select that movie.
3. Place a draft on a free slot of a future day.
4. Save the draft as a real session.
5. Confirm that:
   - the session appears on the admin board,
   - the same session appears in the public schedule,
   - overlap rules block conflicting placements,
   - duplicate-to-dates behavior reports partial success or rejection clearly when conflicts exist.

### 7. Verify localization behavior

1. Open the frontend and switch between Ukrainian and English.
2. Confirm that:
   - UI labels change,
   - movie titles/descriptions render in the expected localized form,
   - genre labels switch language,
   - the app continues to function normally after switching.

### 8. Verify movie lifecycle behavior

1. Create a new movie without sessions and confirm it is `planned`.
2. Schedule a future session for it and confirm it becomes `active`.
3. Remove its future-session situation through cancellation/completion context and confirm the lifecycle updates on subsequent relevant requests.
4. Deactivate the movie from the admin UI when allowed and confirm it leaves the schedule-ready pool.

## 25. Admin Access and Usage Notes

By default, admin access is still controlled by email-based role assignment during registration. Separately, the explicit demo seed command can create a ready-to-use demo admin account and several demo users for presentation runs.

### How admin access works

When a user registers, the backend lowercases the submitted email and checks whether it appears in `ADMIN_EMAILS`. If it does, the created account gets role `admin`; otherwise it gets role `user`.

Client-side role submission is not trusted. Registration accepts only the supported account fields and rejects unexpected extras such as `role`.

### How to create an admin account

1. Set `ADMIN_EMAILS` in `backend/.env` to include the email you want to use.
2. Start the backend.
3. Register a new account with that email.
4. Log in normally through the standard login page.

Important nuance:

- existing normal users are not automatically upgraded later just because you changed `ADMIN_EMAILS`,
- admin status is applied when the account is created,
- if you need a different account to be admin, register it after the environment is configured.

### Seeded demo credentials

If you run `python -m app.seeds.demo_seed --reset` or the equivalent Docker command, the repository will also create these accounts:

- `admin`: `admin@cinema-showcase.dev` / `CinemaDemo123!`
- `user`: `chihiro@cinema-showcase.dev` / `CinemaDemo123!`
- `user`: `taki@cinema-showcase.dev` / `CinemaDemo123!`
- `user`: `suzu@cinema-showcase.dev` / `CinemaDemo123!`
- `user`: `ashitaka@cinema-showcase.dev` / `CinemaDemo123!`

The seed command logs the seeded account emails/roles, but it intentionally does not echo the shared password to the application log.

Those accounts exist only after the explicit seed command is run. They are not created automatically on normal startup.

### How to reach the admin area

The admin dashboard route is:

```text
/admin
```

The frontend route guard checks:

- authentication,
- current resolved user role.

If the user is not an admin, access is blocked.

### What an admin can do currently

Within the current repository scope, admins can:

- create, edit, deactivate, and delete movies under the existing rules,
- create, batch-create, edit, cancel, and delete sessions under the existing rules,
- use the chronoboard for schedule planning,
- inspect tickets and users,
- view attendance/reporting data,
- validate customer order QR codes and check in valid orders,
- cancel tickets or orders through authorized backend flows.

## 26. Current Limitations

The project is substantial, but it is important to document its current limitations honestly.

### Single-node replica set only

The local infrastructure uses one MongoDB node configured as a replica set. This is enough for transactions in development, but it does not provide production-grade high availability.

### No external payment gateway

"Purchase" in the current repository means internal booking completion and state persistence. There is no external payment provider, payment authorization flow, or refund processor.

### No dedicated refund subsystem

Cancellation restores booking state and seat availability, but there is no separate financial refund lifecycle, accounting ledger, or payout reconciliation model.

### Frontend automated tests are currently absent

The repository includes meaningful backend tests, but it does not currently include:

- React component tests,
- frontend integration tests,
- end-to-end browser automation.

### Full-order cancellation is not surfaced by a dedicated frontend action

The backend supports full-order cancellation, but the current profile UI exposes ticket-level cancellation only. Full-order cancellation therefore exists today mainly as an API capability.

### No dedicated admin order-management UI

Admins can inspect grouped booking activity in reporting views with rich filters and can validate/check in a specific order through the QR workflow, but there is no dedicated standalone admin order-management panel comparable to the movie/session management surfaces.

### One-hall domain only

The entire architecture assumes one hall:

- one schedule lane,
- one shared capacity model,
- one set of seat dimensions from settings,
- one overlap domain.

This is appropriate for the stated project scenario, but it is an intentional simplification.

### Request-driven lifecycle synchronization

Session completion and movie lifecycle refresh are triggered during relevant requests, not by a separate background scheduler. As a result, some state changes become visible when the application is exercised, not on an independent clock tick.

### No background reconciliation worker for seat counters

The seat map endpoint can detect counter mismatches by deriving availability from tickets, but there is no standalone repair daemon or scheduled reconciliation job in the repository.

### Local/demo deployment profile only

Docker Compose runs development servers with bind mounts and polling helpers. It is not a production deployment setup with reverse proxying, secrets management, TLS, or multi-environment deployment automation.

### No poster upload pipeline

Movies currently store `poster_url` values as either external HTTP(S) links or root-relative static asset paths. There is still no built-in media upload, storage, or transformation pipeline.

### Legacy data normalization is opportunistic rather than migration-driven

The backend can normalize legacy localized fields and genre inputs, but the repository does not currently include a dedicated migration command for bulk upgrading old movie documents ahead of time.

### Some browse behavior is intentionally demo-scale

The public schedule API is paginated and several frontend catalog/planning surfaces now paginate client-side, but the overall browse model is still intentionally small-scale. It is reasonable for a demo/curriculum repository, but it is not the same as a production-scale browsing architecture with server-driven pagination everywhere.

## 27. Future Improvements

The following improvements would be realistic extensions of the current architecture.

### Add a dedicated frontend full-order cancellation action

The backend capability already exists, so exposing it clearly in the profile UI would be a natural next step.

### Add frontend automated testing

Component tests and a small end-to-end test suite would improve confidence in:

- booking UI behavior,
- localization switching,
- chronoboard interaction,
- protected-route behavior.

### Add admin order views

A dedicated admin order list and order detail panel would complement the existing attendance booking groups and QR validation page, making grouped booking management more complete outside the admission workflow.

### Add background lifecycle and reconciliation jobs

The project could be extended with:

- scheduled movie/session lifecycle synchronization,
- explicit seat-counter reconciliation utilities,
- repair/report jobs for operational consistency checks.

### Add production deployment profile

The current Docker setup is development-oriented. A production-ready extension could add:

- separate production Dockerfiles,
- a reverse proxy,
- environment-specific configuration,
- more explicit secret handling.

### Add role-management utilities

Right now admin assignment outside the demo seed flow is still registration-time email based. A dedicated admin promotion flow would make role management more flexible for future environments.

### Extend chronoboard ergonomics

The existing chronoboard is useful already, but it could reasonably evolve with features such as:

- drag-resize session blocks,
- richer visual conflict indicators,
- gap suggestions,
- broader planning analytics.

These would be enhancements to an existing strong feature, not a rethinking of the project.

## 28. Final Conclusion

Cinema Showcase already demonstrates a complete and technically meaningful one-hall cinema application:

- a FastAPI backend with explicit schemas, modular services, repositories, commands, and transaction support,
- a React frontend with public, authenticated, and admin experiences,
- a MongoDB data model that uses validators, indexes, and replica-set-backed transactions,
- real booking flows built around orders, tickets, seat maps, and cancellation behavior,
- customer order receipts with signed QR validation and staff check-in,
- an admin planning surface tailored to the one-hall scheduling problem.

Within its intended scope, the project is more than a simple CRUD demo. It shows careful thinking about lifecycle modeling, localization, catalog normalization, booking consistency, and operator workflows. At the same time, it remains honest about its current boundaries: one hall, development-focused infrastructure, no external payments, and limited frontend automation.

For coursework, demo review, or technical discussion, the repository currently provides a clear example of how to build a focused domain application with practical transactional correctness and a well-separated full-stack architecture.
