"""Deterministic demo dataset used by the explicit seeding command."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from bson import ObjectId

from app.core.config import get_settings
from app.core.constants import MovieStatuses, Roles, SessionStatuses, TicketStatuses
from app.schemas.movie import MovieRead
from app.schemas.order import OrderRead
from app.schemas.session import SessionRead
from app.schemas.ticket import TicketRead
from app.schemas.user import UserRead
from app.security.hashing import password_hasher
from app.utils.order_aggregates import build_order_aggregate_snapshot

DEMO_SEED_VERSION = "cinema-demo-v1"
DEMO_SHARED_PASSWORD = "CinemaDemo123!"
DEMO_ADMIN_EMAIL = "admin@cinema-showcase.dev"


@dataclass(frozen=True, slots=True)
class DemoUserTemplate:
    slug: str
    object_id: str
    name: str
    email: str
    role: str = Roles.USER


@dataclass(frozen=True, slots=True)
class DemoMovieTemplate:
    slug: str
    object_id: str
    title: dict[str, str]
    description: dict[str, str]
    duration_minutes: int
    poster_path: str
    age_rating: str
    genres: tuple[str, ...]
    status: str


@dataclass(frozen=True, slots=True)
class DemoSessionTemplate:
    slug: str
    object_id: str
    movie_slug: str
    day_offset: int
    start_hour: int
    start_minute: int
    buffer_minutes: int
    price: float
    status: str


@dataclass(frozen=True, slots=True)
class DemoOrderTicketTemplate:
    object_id: str
    seat_row: int
    seat_number: int
    status: str = TicketStatuses.PURCHASED
    cancel_after_hours: int = 12


@dataclass(frozen=True, slots=True)
class DemoOrderTemplate:
    slug: str
    object_id: str
    user_slug: str
    session_slug: str
    purchase_days_before: int
    tickets: tuple[DemoOrderTicketTemplate, ...]


@dataclass(frozen=True, slots=True)
class DemoSeedData:
    """MongoDB-ready demo dataset."""

    users: list[dict[str, object]]
    movies: list[dict[str, object]]
    sessions: list[dict[str, object]]
    orders: list[dict[str, object]]
    tickets: list[dict[str, object]]

    @property
    def collection_counts(self) -> dict[str, int]:
        return {
            "users": len(self.users),
            "movies": len(self.movies),
            "sessions": len(self.sessions),
            "orders": len(self.orders),
            "tickets": len(self.tickets),
        }


DEMO_USERS: tuple[DemoUserTemplate, ...] = (
    DemoUserTemplate(
        slug="admin",
        object_id="680000000000000000000001",
        name="Cinema Demo Admin",
        email=DEMO_ADMIN_EMAIL,
        role=Roles.ADMIN,
    ),
    DemoUserTemplate(
        slug="chihiro",
        object_id="680000000000000000000002",
        name="Chihiro Ogino",
        email="chihiro@cinema-showcase.dev",
    ),
    DemoUserTemplate(
        slug="taki",
        object_id="680000000000000000000003",
        name="Taki Tachibana",
        email="taki@cinema-showcase.dev",
    ),
    DemoUserTemplate(
        slug="suzu",
        object_id="680000000000000000000004",
        name="Suzu Naito",
        email="suzu@cinema-showcase.dev",
    ),
    DemoUserTemplate(
        slug="ashitaka",
        object_id="680000000000000000000005",
        name="Ashitaka Emishi",
        email="ashitaka@cinema-showcase.dev",
    ),
)

DEMO_MOVIES: tuple[DemoMovieTemplate, ...] = (
    DemoMovieTemplate(
        slug="spirited-away",
        object_id="680000000000000000000101",
        title={"uk": "Віднесені привидами", "en": "Spirited Away"},
        description={
            "uk": "Фантазійна пригода про дівчину, яка потрапляє до чарівного світу духів і шукає дорогу додому.",
            "en": "A fantasy adventure about a girl who enters a world of spirits and fights her way back home.",
        },
        duration_minutes=125,
        poster_path="/demo-posters/spirited-away.svg",
        age_rating="PG",
        genres=("animation", "fantasy", "adventure", "family"),
        status=MovieStatuses.ACTIVE,
    ),
    DemoMovieTemplate(
        slug="your-name",
        object_id="680000000000000000000102",
        title={"uk": "Твоє ім'я", "en": "Your Name"},
        description={
            "uk": "Романтична історія про двох підлітків, чиї життя дивним чином переплітаються крізь час і відстань.",
            "en": "A romantic body-swap story where two teenagers become linked across time and distance.",
        },
        duration_minutes=112,
        poster_path="/demo-posters/your-name.svg",
        age_rating="12+",
        genres=("animation", "drama", "romance", "fantasy"),
        status=MovieStatuses.ACTIVE,
    ),
    DemoMovieTemplate(
        slug="princess-mononoke",
        object_id="680000000000000000000103",
        title={"uk": "Принцеса Мононоке", "en": "Princess Mononoke"},
        description={
            "uk": "Епічне фентезі про конфлікт між природою, людьми та проклятим воїном, який шукає рівновагу.",
            "en": "An epic fantasy about the clash between nature, industry, and a warrior searching for balance.",
        },
        duration_minutes=134,
        poster_path="/demo-posters/princess-mononoke.svg",
        age_rating="16+",
        genres=("animation", "fantasy", "adventure", "action"),
        status=MovieStatuses.ACTIVE,
    ),
    DemoMovieTemplate(
        slug="suzume",
        object_id="680000000000000000000104",
        title={"uk": "Судзуме", "en": "Suzume"},
        description={
            "uk": "Сучасня дорожня історія, у якій дівчина зачиняє двері, що відкривають шлях до катастроф.",
            "en": "A contemporary road-trip story where a teenager closes mysterious doors linked to disasters.",
        },
        duration_minutes=122,
        poster_path="/demo-posters/suzume.svg",
        age_rating="12+",
        genres=("animation", "adventure", "fantasy", "drama"),
        status=MovieStatuses.ACTIVE,
    ),
    DemoMovieTemplate(
        slug="weathering-with-you",
        object_id="680000000000000000000105",
        title={"uk": "Дитя погоди", "en": "Weathering with You"},
        description={
            "uk": "Меланхолійна історія кохання під дощовим небом Токіо, де погода реагує на людські почуття.",
            "en": "A rain-soaked romance set in Tokyo, where the weather itself answers human emotion.",
        },
        duration_minutes=114,
        poster_path="/demo-posters/weathering-with-you.svg",
        age_rating="12+",
        genres=("animation", "drama", "romance", "fantasy"),
        status=MovieStatuses.ACTIVE,
    ),
    DemoMovieTemplate(
        slug="boy-and-the-heron",
        object_id="680000000000000000000106",
        title={"uk": "Хлопчик і чапля", "en": "The Boy and the Heron"},
        description={
            "uk": "Лірична пригода про втрату, дорослішання та дивний світ, що ховається за межами звичайної реальності.",
            "en": "A lyrical adventure about grief, growing up, and the strange world hidden behind ordinary reality.",
        },
        duration_minutes=124,
        poster_path="/demo-posters/boy-and-the-heron.svg",
        age_rating="12+",
        genres=("animation", "fantasy", "adventure", "drama"),
        status=MovieStatuses.ACTIVE,
    ),
    DemoMovieTemplate(
        slug="a-silent-voice",
        object_id="680000000000000000000107",
        title={"uk": "Форма голосу", "en": "A Silent Voice"},
        description={
            "uk": "Чутлива драма про провину, вибачення та спробу знову навчитися чути інших людей.",
            "en": "A tender drama about guilt, apology, and learning how to truly hear other people again.",
        },
        duration_minutes=130,
        poster_path="/demo-posters/a-silent-voice.svg",
        age_rating="12+",
        genres=("animation", "drama", "romance"),
        status=MovieStatuses.PLANNED,
    ),
    DemoMovieTemplate(
        slug="paprika",
        object_id="680000000000000000000108",
        title={"uk": "Паприка", "en": "Paprika"},
        description={
            "uk": "Яскравий психоделічний трилер, у якому сни прориваються в реальний світ і руйнують межі між ними.",
            "en": "A vivid psychedelic thriller where dreams break into reality and erase the line between them.",
        },
        duration_minutes=90,
        poster_path="/demo-posters/paprika.svg",
        age_rating="16+",
        genres=("animation", "science_fiction", "thriller", "mystery"),
        status=MovieStatuses.PLANNED,
    ),
    DemoMovieTemplate(
        slug="ghost-in-the-shell",
        object_id="680000000000000000000109",
        title={"uk": "Привид у броні", "en": "Ghost in the Shell"},
        description={
            "uk": "Кіберпанк-детектив про ідентичність, штучний інтелект і ціну злиття людини з машиною.",
            "en": "A cyberpunk detective story about identity, artificial intelligence, and the cost of merging with machines.",
        },
        duration_minutes=83,
        poster_path="/demo-posters/ghost-in-the-shell.svg",
        age_rating="16+",
        genres=("animation", "science_fiction", "action", "detective"),
        status=MovieStatuses.DEACTIVATED,
    ),
    DemoMovieTemplate(
        slug="perfect-blue",
        object_id="68000000000000000000010a",
        title={"uk": "Ідеальна синь", "en": "Perfect Blue"},
        description={
            "uk": "Психологічний трилер про попідолку, чия реальність починає тріщати під тиском слави та страху.",
            "en": "A psychological thriller about a pop idol whose reality fractures under fame and fear.",
        },
        duration_minutes=81,
        poster_path="/demo-posters/perfect-blue.svg",
        age_rating="18+",
        genres=("animation", "thriller", "mystery", "drama"),
        status=MovieStatuses.DEACTIVATED,
    ),
)

DEMO_SESSIONS: tuple[DemoSessionTemplate, ...] = (
    DemoSessionTemplate(
        slug="ghost-retro",
        object_id="680000000000000000000201",
        movie_slug="ghost-in-the-shell",
        day_offset=-4,
        start_hour=18,
        start_minute=30,
        buffer_minutes=12,
        price=210.0,
        status=SessionStatuses.COMPLETED,
    ),
    DemoSessionTemplate(
        slug="perfect-retro",
        object_id="680000000000000000000202",
        movie_slug="perfect-blue",
        day_offset=-2,
        start_hour=20,
        start_minute=0,
        buffer_minutes=11,
        price=220.0,
        status=SessionStatuses.COMPLETED,
    ),
    DemoSessionTemplate(
        slug="spirited-retro",
        object_id="680000000000000000000203",
        movie_slug="spirited-away",
        day_offset=-1,
        start_hour=16,
        start_minute=0,
        buffer_minutes=15,
        price=230.0,
        status=SessionStatuses.COMPLETED,
    ),
    DemoSessionTemplate(
        slug="suzume-d1-morning",
        object_id="680000000000000000000204",
        movie_slug="suzume",
        day_offset=1,
        start_hour=10,
        start_minute=0,
        buffer_minutes=15,
        price=220.0,
        status=SessionStatuses.SCHEDULED,
    ),
    DemoSessionTemplate(
        slug="your-name-d1-afternoon",
        object_id="680000000000000000000205",
        movie_slug="your-name",
        day_offset=1,
        start_hour=13,
        start_minute=0,
        buffer_minutes=18,
        price=235.0,
        status=SessionStatuses.SCHEDULED,
    ),
    DemoSessionTemplate(
        slug="mononoke-d1-evening",
        object_id="680000000000000000000206",
        movie_slug="princess-mononoke",
        day_offset=1,
        start_hour=17,
        start_minute=0,
        buffer_minutes=16,
        price=250.0,
        status=SessionStatuses.SCHEDULED,
    ),
    DemoSessionTemplate(
        slug="spirited-d2-morning",
        object_id="680000000000000000000207",
        movie_slug="spirited-away",
        day_offset=2,
        start_hour=11,
        start_minute=0,
        buffer_minutes=15,
        price=230.0,
        status=SessionStatuses.SCHEDULED,
    ),
    DemoSessionTemplate(
        slug="weather-d2-afternoon",
        object_id="680000000000000000000208",
        movie_slug="weathering-with-you",
        day_offset=2,
        start_hour=14,
        start_minute=15,
        buffer_minutes=16,
        price=225.0,
        status=SessionStatuses.SCHEDULED,
    ),
    DemoSessionTemplate(
        slug="heron-d2-evening",
        object_id="680000000000000000000209",
        movie_slug="boy-and-the-heron",
        day_offset=2,
        start_hour=18,
        start_minute=0,
        buffer_minutes=16,
        price=245.0,
        status=SessionStatuses.SCHEDULED,
    ),
    DemoSessionTemplate(
        slug="your-name-d3-morning",
        object_id="68000000000000000000020a",
        movie_slug="your-name",
        day_offset=3,
        start_hour=10,
        start_minute=30,
        buffer_minutes=18,
        price=240.0,
        status=SessionStatuses.SCHEDULED,
    ),
    DemoSessionTemplate(
        slug="suzume-d3-afternoon",
        object_id="68000000000000000000020b",
        movie_slug="suzume",
        day_offset=3,
        start_hour=13,
        start_minute=30,
        buffer_minutes=15,
        price=220.0,
        status=SessionStatuses.SCHEDULED,
    ),
    DemoSessionTemplate(
        slug="spirited-d3-evening",
        object_id="68000000000000000000020c",
        movie_slug="spirited-away",
        day_offset=3,
        start_hour=17,
        start_minute=30,
        buffer_minutes=15,
        price=235.0,
        status=SessionStatuses.SCHEDULED,
    ),
    DemoSessionTemplate(
        slug="weather-d4-morning",
        object_id="68000000000000000000020d",
        movie_slug="weathering-with-you",
        day_offset=4,
        start_hour=12,
        start_minute=0,
        buffer_minutes=16,
        price=225.0,
        status=SessionStatuses.SCHEDULED,
    ),
    DemoSessionTemplate(
        slug="mononoke-d4-afternoon",
        object_id="68000000000000000000020e",
        movie_slug="princess-mononoke",
        day_offset=4,
        start_hour=15,
        start_minute=0,
        buffer_minutes=16,
        price=255.0,
        status=SessionStatuses.SCHEDULED,
    ),
    DemoSessionTemplate(
        slug="heron-d4-evening",
        object_id="68000000000000000000020f",
        movie_slug="boy-and-the-heron",
        day_offset=4,
        start_hour=18,
        start_minute=30,
        buffer_minutes=16,
        price=245.0,
        status=SessionStatuses.SCHEDULED,
    ),
    DemoSessionTemplate(
        slug="suzume-d5-morning",
        object_id="680000000000000000000210",
        movie_slug="suzume",
        day_offset=5,
        start_hour=10,
        start_minute=0,
        buffer_minutes=15,
        price=220.0,
        status=SessionStatuses.SCHEDULED,
    ),
    DemoSessionTemplate(
        slug="your-name-d5-afternoon",
        object_id="680000000000000000000211",
        movie_slug="your-name",
        day_offset=5,
        start_hour=13,
        start_minute=0,
        buffer_minutes=18,
        price=235.0,
        status=SessionStatuses.SCHEDULED,
    ),
    DemoSessionTemplate(
        slug="ghost-d5-late-cancelled",
        object_id="680000000000000000000212",
        movie_slug="ghost-in-the-shell",
        day_offset=5,
        start_hour=20,
        start_minute=30,
        buffer_minutes=12,
        price=215.0,
        status=SessionStatuses.CANCELLED,
    ),
    DemoSessionTemplate(
        slug="spirited-d6-morning",
        object_id="680000000000000000000213",
        movie_slug="spirited-away",
        day_offset=6,
        start_hour=11,
        start_minute=0,
        buffer_minutes=15,
        price=230.0,
        status=SessionStatuses.SCHEDULED,
    ),
    DemoSessionTemplate(
        slug="weather-d6-afternoon",
        object_id="680000000000000000000214",
        movie_slug="weathering-with-you",
        day_offset=6,
        start_hour=14,
        start_minute=30,
        buffer_minutes=16,
        price=225.0,
        status=SessionStatuses.SCHEDULED,
    ),
)

DEMO_ORDERS: tuple[DemoOrderTemplate, ...] = (
    DemoOrderTemplate(
        slug="spirited-retro-order",
        object_id="680000000000000000000301",
        user_slug="chihiro",
        session_slug="spirited-retro",
        purchase_days_before=4,
        tickets=(
            DemoOrderTicketTemplate("680000000000000000000401", 2, 5),
            DemoOrderTicketTemplate("680000000000000000000402", 2, 6),
            DemoOrderTicketTemplate("680000000000000000000403", 2, 7),
        ),
    ),
    DemoOrderTemplate(
        slug="perfect-retro-order",
        object_id="680000000000000000000302",
        user_slug="suzu",
        session_slug="perfect-retro",
        purchase_days_before=3,
        tickets=(
            DemoOrderTicketTemplate("680000000000000000000404", 4, 4),
            DemoOrderTicketTemplate("680000000000000000000405", 4, 5),
        ),
    ),
    DemoOrderTemplate(
        slug="ghost-retro-order",
        object_id="680000000000000000000303",
        user_slug="admin",
        session_slug="ghost-retro",
        purchase_days_before=6,
        tickets=(
            DemoOrderTicketTemplate("680000000000000000000406", 1, 10),
            DemoOrderTicketTemplate("680000000000000000000407", 1, 11),
        ),
    ),
    DemoOrderTemplate(
        slug="suzume-future-order",
        object_id="680000000000000000000304",
        user_slug="taki",
        session_slug="suzume-d1-morning",
        purchase_days_before=3,
        tickets=(
            DemoOrderTicketTemplate("680000000000000000000408", 1, 1),
            DemoOrderTicketTemplate("680000000000000000000409", 1, 2),
        ),
    ),
    DemoOrderTemplate(
        slug="mononoke-partial-order",
        object_id="680000000000000000000305",
        user_slug="ashitaka",
        session_slug="mononoke-d1-evening",
        purchase_days_before=3,
        tickets=(
            DemoOrderTicketTemplate("68000000000000000000040a", 5, 5),
            DemoOrderTicketTemplate("68000000000000000000040b", 5, 6),
            DemoOrderTicketTemplate(
                "68000000000000000000040c",
                5,
                7,
                status=TicketStatuses.CANCELLED,
                cancel_after_hours=20,
            ),
        ),
    ),
    DemoOrderTemplate(
        slug="weather-future-order",
        object_id="680000000000000000000306",
        user_slug="suzu",
        session_slug="weather-d2-afternoon",
        purchase_days_before=4,
        tickets=(
            DemoOrderTicketTemplate("68000000000000000000040d", 3, 8),
            DemoOrderTicketTemplate("68000000000000000000040e", 3, 9),
        ),
    ),
    DemoOrderTemplate(
        slug="cancelled-session-order",
        object_id="680000000000000000000307",
        user_slug="chihiro",
        session_slug="ghost-d5-late-cancelled",
        purchase_days_before=7,
        tickets=(
            DemoOrderTicketTemplate(
                "68000000000000000000040f",
                6,
                1,
                status=TicketStatuses.CANCELLED,
                cancel_after_hours=24,
            ),
            DemoOrderTicketTemplate(
                "680000000000000000000410",
                6,
                2,
                status=TicketStatuses.CANCELLED,
                cancel_after_hours=24,
            ),
        ),
    ),
    DemoOrderTemplate(
        slug="cancelled-upcoming-order",
        object_id="680000000000000000000308",
        user_slug="taki",
        session_slug="your-name-d5-afternoon",
        purchase_days_before=6,
        tickets=(
            DemoOrderTicketTemplate(
                "680000000000000000000411",
                7,
                3,
                status=TicketStatuses.CANCELLED,
                cancel_after_hours=18,
            ),
        ),
    ),
    DemoOrderTemplate(
        slug="heron-future-order",
        object_id="680000000000000000000309",
        user_slug="ashitaka",
        session_slug="heron-d4-evening",
        purchase_days_before=5,
        tickets=(
            DemoOrderTicketTemplate("680000000000000000000412", 8, 10),
            DemoOrderTicketTemplate("680000000000000000000413", 8, 11),
            DemoOrderTicketTemplate("680000000000000000000414", 8, 12),
        ),
    ),
)


def build_demo_seed_data(reference_now: datetime | None = None) -> DemoSeedData:
    """Build validated demo documents relative to the current cinema timezone."""
    settings = get_settings()
    reference_utc = (reference_now or datetime.now(tz=timezone.utc)).astimezone(timezone.utc)
    cinema_timezone = ZoneInfo(settings.cinema_timezone)
    reference_local = reference_utc.astimezone(cinema_timezone)

    users = _build_users(reference_utc)
    movies = _build_movies(reference_utc)
    movie_map = {template.slug: movie for template, movie in zip(DEMO_MOVIES, movies, strict=True)}
    sessions = _build_sessions(
        reference_local=reference_local,
        reference_utc=reference_utc,
        movie_map=movie_map,
    )
    session_map = {
        template.slug: session
        for template, session in zip(DEMO_SESSIONS, sessions, strict=True)
    }
    user_map = {template.slug: user for template, user in zip(DEMO_USERS, users, strict=True)}
    orders, tickets = _build_orders_and_tickets(
        reference_utc=reference_utc,
        session_map=session_map,
        user_map=user_map,
    )
    _apply_session_availability(sessions, tickets, total_seats=settings.total_seats)

    dataset = DemoSeedData(
        users=users,
        movies=movies,
        sessions=sessions,
        orders=orders,
        tickets=tickets,
    )
    validate_demo_seed_data(dataset, reference_now=reference_utc)
    return dataset


def validate_demo_seed_data(dataset: DemoSeedData, *, reference_now: datetime) -> None:
    """Validate the generated demo data against application schemas and domain invariants."""
    settings = get_settings()
    movies = [_as_movie_read(document) for document in dataset.movies]
    sessions = [_as_session_read(document) for document in dataset.sessions]
    orders = [_as_order_read(document) for document in dataset.orders]
    tickets = [_as_ticket_read(document) for document in dataset.tickets]
    users = [_as_user_read(document) for document in dataset.users]

    movie_by_id = {movie.id: movie for movie in movies}
    session_by_id = {session.id: session for session in sessions}
    order_by_id = {order.id: order for order in orders}
    user_by_id = {user.id: user for user in users}

    if len(movie_by_id) != len(movies):
        raise ValueError("Demo seed data contains duplicate movie identifiers.")
    if len(session_by_id) != len(sessions):
        raise ValueError("Demo seed data contains duplicate session identifiers.")
    if len(order_by_id) != len(orders):
        raise ValueError("Demo seed data contains duplicate order identifiers.")
    if len(user_by_id) != len(users):
        raise ValueError("Demo seed data contains duplicate user identifiers.")

    _validate_status_distribution(movies)
    _validate_future_movie_statuses(movies=movies, sessions=sessions, reference_now=reference_now)
    _validate_session_overlaps(sessions)
    _validate_tickets(
        tickets=tickets,
        session_by_id=session_by_id,
        order_by_id=order_by_id,
        user_by_id=user_by_id,
        rows_count=settings.hall_rows_count,
        seats_per_row=settings.hall_seats_per_row,
    )
    _validate_orders(orders=orders, tickets=tickets)
    _validate_session_availability(
        sessions=sessions,
        tickets=tickets,
        total_seats=settings.total_seats,
    )


def demo_seed_object_ids() -> dict[str, list[ObjectId]]:
    """Return all deterministic object identifiers used by the demo dataset."""
    return {
        "users": [_object_id(template.object_id) for template in DEMO_USERS],
        "movies": [_object_id(template.object_id) for template in DEMO_MOVIES],
        "sessions": [_object_id(template.object_id) for template in DEMO_SESSIONS],
        "orders": [_object_id(template.object_id) for template in DEMO_ORDERS],
        "tickets": [
            _object_id(ticket.object_id)
            for template in DEMO_ORDERS
            for ticket in template.tickets
        ],
    }


def demo_credentials() -> list[dict[str, str]]:
    """Return the documented demo login credentials."""
    return [
        {
            "role": template.role,
            "email": template.email,
            "password": DEMO_SHARED_PASSWORD,
            "name": template.name,
        }
        for template in DEMO_USERS
    ]


def _build_users(reference_utc: datetime) -> list[dict[str, object]]:
    users: list[dict[str, object]] = []
    for index, template in enumerate(DEMO_USERS):
        users.append(
            {
                "_id": _object_id(template.object_id),
                "name": template.name,
                "email": template.email,
                "password_hash": password_hasher.hash_password(DEMO_SHARED_PASSWORD),
                "role": template.role,
                "is_active": True,
                "created_at": reference_utc - timedelta(days=90 - index * 7),
                "updated_at": None,
            }
        )
    return users


def _build_movies(reference_utc: datetime) -> list[dict[str, object]]:
    movies: list[dict[str, object]] = []
    for index, template in enumerate(DEMO_MOVIES):
        movies.append(
            {
                "_id": _object_id(template.object_id),
                "title": template.title,
                "description": template.description,
                "duration_minutes": template.duration_minutes,
                "poster_url": template.poster_path,
                "age_rating": template.age_rating,
                "genres": list(template.genres),
                "status": template.status,
                "created_at": reference_utc - timedelta(days=60 - index * 3),
                "updated_at": None,
            }
        )
    return movies


def _build_sessions(
    *,
    reference_local: datetime,
    reference_utc: datetime,
    movie_map: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    settings = get_settings()
    cinema_timezone = ZoneInfo(settings.cinema_timezone)
    sessions: list[dict[str, object]] = []

    for template in DEMO_SESSIONS:
        movie = movie_map[template.movie_slug]
        start_time = _build_local_datetime(
            reference_local=reference_local,
            day_offset=template.day_offset,
            hour=template.start_hour,
            minute=template.start_minute,
            tz=cinema_timezone,
        )
        runtime_minutes = int(movie["duration_minutes"])
        end_time = start_time + timedelta(minutes=runtime_minutes + template.buffer_minutes)
        updated_at = None
        if template.status == SessionStatuses.COMPLETED:
            updated_at = end_time
        elif template.status == SessionStatuses.CANCELLED:
            updated_at = min(reference_utc - timedelta(hours=2), start_time - timedelta(hours=6))

        sessions.append(
            {
                "_id": _object_id(template.object_id),
                "movie_id": str(movie["_id"]),
                "start_time": start_time,
                "end_time": end_time,
                "price": template.price,
                "status": template.status,
                "total_seats": settings.total_seats,
                "available_seats": settings.total_seats,
                "created_at": min(reference_utc - timedelta(days=14), start_time - timedelta(days=7)),
                "updated_at": updated_at,
            }
        )
    return sessions


def _build_orders_and_tickets(
    *,
    reference_utc: datetime,
    session_map: dict[str, dict[str, object]],
    user_map: dict[str, dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    orders: list[dict[str, object]] = []
    tickets: list[dict[str, object]] = []

    for template in DEMO_ORDERS:
        session = session_map[template.session_slug]
        user = user_map[template.user_slug]
        purchased_at = _build_purchase_time(
            reference_utc=reference_utc,
            session_start=session["start_time"],
            purchase_days_before=template.purchase_days_before,
        )

        order_tickets: list[dict[str, object]] = []
        for ticket_index, ticket_template in enumerate(template.tickets):
            ticket_purchased_at = purchased_at + timedelta(minutes=ticket_index * 7)
            cancelled_at = None
            updated_at = None
            if ticket_template.status == TicketStatuses.CANCELLED:
                cancelled_at = _build_cancelled_at(
                    purchased_at=ticket_purchased_at,
                    session_start=session["start_time"],
                    reference_utc=reference_utc,
                    cancel_after_hours=ticket_template.cancel_after_hours,
                )
                updated_at = cancelled_at

            order_tickets.append(
                {
                    "_id": _object_id(ticket_template.object_id),
                    "order_id": template.object_id,
                    "user_id": str(user["_id"]),
                    "session_id": str(session["_id"]),
                    "seat_row": ticket_template.seat_row,
                    "seat_number": ticket_template.seat_number,
                    "price": float(session["price"]),
                    "status": ticket_template.status,
                    "purchased_at": ticket_purchased_at,
                    "updated_at": updated_at,
                    "cancelled_at": cancelled_at,
                }
            )

        aggregate = build_order_aggregate_snapshot(order_tickets)
        updated_at = max(
            (
                ticket["updated_at"]
                for ticket in order_tickets
                if ticket.get("updated_at") is not None
            ),
            default=None,
        )
        orders.append(
            {
                "_id": _object_id(template.object_id),
                "user_id": str(user["_id"]),
                "session_id": str(session["_id"]),
                "status": aggregate.status,
                "total_price": aggregate.total_price,
                "tickets_count": aggregate.tickets_count,
                "created_at": purchased_at,
                "updated_at": updated_at,
            }
        )
        tickets.extend(order_tickets)

    return orders, tickets


def _apply_session_availability(
    sessions: list[dict[str, object]],
    tickets: list[dict[str, object]],
    *,
    total_seats: int,
) -> None:
    purchased_counts: dict[str, int] = defaultdict(int)
    for ticket in tickets:
        if ticket["status"] == TicketStatuses.PURCHASED:
            purchased_counts[str(ticket["session_id"])] += 1

    for session in sessions:
        session["available_seats"] = total_seats - purchased_counts.get(str(session["_id"]), 0)


def _build_local_datetime(
    *,
    reference_local: datetime,
    day_offset: int,
    hour: int,
    minute: int,
    tz: ZoneInfo,
) -> datetime:
    target_date = reference_local.date() + timedelta(days=day_offset)
    return datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        hour,
        minute,
        tzinfo=tz,
    ).astimezone(timezone.utc)


def _build_purchase_time(
    *,
    reference_utc: datetime,
    session_start: datetime,
    purchase_days_before: int,
) -> datetime:
    candidate = session_start - timedelta(days=purchase_days_before, hours=3)
    latest_past_time = reference_utc - timedelta(hours=6)
    if candidate > latest_past_time:
        return latest_past_time
    return candidate


def _build_cancelled_at(
    *,
    purchased_at: datetime,
    session_start: datetime,
    reference_utc: datetime,
    cancel_after_hours: int,
) -> datetime:
    candidate = purchased_at + timedelta(hours=cancel_after_hours)
    latest_possible = min(
        reference_utc - timedelta(minutes=30),
        session_start - timedelta(hours=6),
    )
    if candidate > latest_possible:
        candidate = latest_possible
    if candidate <= purchased_at:
        candidate = purchased_at + timedelta(minutes=30)
    return candidate


def _validate_status_distribution(movies: list[MovieRead]) -> None:
    statuses = {movie.status for movie in movies}
    required_statuses = {
        MovieStatuses.ACTIVE,
        MovieStatuses.PLANNED,
        MovieStatuses.DEACTIVATED,
    }
    if not required_statuses.issubset(statuses):
        raise ValueError("Demo seed data must include active, planned, and deactivated movies.")


def _validate_future_movie_statuses(
    *,
    movies: list[MovieRead],
    sessions: list[SessionRead],
    reference_now: datetime,
) -> None:
    future_scheduled_movie_ids = {
        session.movie_id
        for session in sessions
        if session.status == SessionStatuses.SCHEDULED and session.start_time > reference_now
    }
    active_movie_ids = {movie.id for movie in movies if movie.status == MovieStatuses.ACTIVE}
    if future_scheduled_movie_ids != active_movie_ids:
        raise ValueError("Active demo movies must exactly match movies with future scheduled sessions.")


def _validate_session_overlaps(sessions: list[SessionRead]) -> None:
    relevant_sessions = sorted(
        (
            session
            for session in sessions
            if session.status != SessionStatuses.CANCELLED
        ),
        key=lambda session: session.start_time,
    )
    for previous, current in zip(relevant_sessions, relevant_sessions[1:], strict=False):
        if previous.end_time > current.start_time:
            raise ValueError(
                f"Demo sessions overlap: {previous.id} ends after {current.id} starts."
            )


def _validate_tickets(
    *,
    tickets: list[TicketRead],
    session_by_id: dict[str, SessionRead],
    order_by_id: dict[str, OrderRead],
    user_by_id: dict[str, UserRead],
    rows_count: int,
    seats_per_row: int,
) -> None:
    purchased_seats_by_session: dict[str, set[tuple[int, int]]] = defaultdict(set)

    for ticket in tickets:
        if ticket.session_id not in session_by_id:
            raise ValueError(f"Ticket {ticket.id} references a missing session.")
        if ticket.order_id is None or ticket.order_id not in order_by_id:
            raise ValueError(f"Ticket {ticket.id} references a missing order.")
        if ticket.user_id not in user_by_id:
            raise ValueError(f"Ticket {ticket.id} references a missing user.")
        if ticket.seat_row > rows_count or ticket.seat_number > seats_per_row:
            raise ValueError(f"Ticket {ticket.id} uses a seat outside the configured hall bounds.")

        if ticket.status == TicketStatuses.PURCHASED:
            seat = (ticket.seat_row, ticket.seat_number)
            occupied = purchased_seats_by_session[ticket.session_id]
            if seat in occupied:
                raise ValueError(
                    f"Demo tickets contain a duplicate purchased seat for session {ticket.session_id}."
                )
            occupied.add(seat)


def _validate_orders(*, orders: list[OrderRead], tickets: list[TicketRead]) -> None:
    tickets_by_order: dict[str, list[dict[str, object]]] = defaultdict(list)
    for ticket in tickets:
        if ticket.order_id is None:
            raise ValueError(f"Demo ticket {ticket.id} is missing order_id.")
        tickets_by_order[ticket.order_id].append(ticket.model_dump(mode="python"))

    for order in orders:
        aggregate = build_order_aggregate_snapshot(tickets_by_order[order.id])
        if order.status != aggregate.status:
            raise ValueError(f"Order {order.id} has an inconsistent stored status.")
        if order.tickets_count != aggregate.tickets_count:
            raise ValueError(f"Order {order.id} has an inconsistent tickets_count.")
        if float(order.total_price) != float(aggregate.total_price):
            raise ValueError(f"Order {order.id} has an inconsistent total_price.")


def _validate_session_availability(
    *,
    sessions: list[SessionRead],
    tickets: list[TicketRead],
    total_seats: int,
) -> None:
    purchased_counts: dict[str, int] = defaultdict(int)
    for ticket in tickets:
        if ticket.status == TicketStatuses.PURCHASED:
            purchased_counts[ticket.session_id] += 1

    for session in sessions:
        expected_available = total_seats - purchased_counts.get(session.id, 0)
        if session.available_seats != expected_available:
            raise ValueError(f"Session {session.id} has an inconsistent available seat counter.")


def _as_movie_read(document: dict[str, object]) -> MovieRead:
    return MovieRead.model_validate(_to_read_document(document))


def _as_session_read(document: dict[str, object]) -> SessionRead:
    return SessionRead.model_validate(_to_read_document(document))


def _as_order_read(document: dict[str, object]) -> OrderRead:
    return OrderRead.model_validate(_to_read_document(document))


def _as_ticket_read(document: dict[str, object]) -> TicketRead:
    return TicketRead.model_validate(_to_read_document(document))


def _as_user_read(document: dict[str, object]) -> UserRead:
    read_document = _to_read_document(document)
    read_document.pop("password_hash", None)
    return UserRead.model_validate(read_document)


def _to_read_document(document: dict[str, object]) -> dict[str, object]:
    return {
        **{key: value for key, value in document.items() if key != "_id"},
        "id": str(document["_id"]),
    }


def _object_id(value: str) -> ObjectId:
    return ObjectId(value)
