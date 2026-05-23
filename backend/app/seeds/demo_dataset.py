"""Deterministic demo dataset used by the explicit seeding command."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from bson import ObjectId

from app.core.config import get_settings
from app.core.constants import (
    MovieStatuses,
    OrderStatuses,
    PaymentAttemptStatuses,
    PaymentStatuses,
    PaymentWebhookProcessingStatuses,
    RefundStatuses,
    Roles,
    SessionStatuses,
    TICKET_BLOCKING_STATUS_VALUES,
    TicketStatuses,
)
from app.schemas.movie import MovieRead
from app.schemas.order import OrderRead
from app.schemas.payment import (
    PaymentAttemptRead,
    PaymentAuditEventRead,
    PaymentRead,
    PaymentWebhookEventRead,
    RefundRead,
)
from app.schemas.session import SessionRead
from app.schemas.ticket import TicketRead
from app.schemas.user import UserRead
from app.security.hashing import password_hasher
from app.utils.money import amount_to_minor_units
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
    was_purchased: bool = True
    checked_in_after_minutes: int | None = None


@dataclass(frozen=True, slots=True)
class DemoOrderTemplate:
    slug: str
    object_id: str
    user_slug: str
    session_slug: str
    purchase_days_before: int
    tickets: tuple[DemoOrderTicketTemplate, ...]
    created_minutes_from_now: int | None = None
    explicit_status: str | None = None


@dataclass(frozen=True, slots=True)
class DemoRefundTemplate:
    object_id: str
    amount_minor: int
    reason: str
    requested_by: str
    created_minutes_after_payment: int


@dataclass(frozen=True, slots=True)
class DemoPaymentTemplate:
    slug: str
    object_id: str
    attempt_object_id: str
    order_slug: str
    status: str
    attempt_status: str
    created_minutes_after_order: int = 1
    updated_minutes_after_order: int | None = 4
    failure_code: str | None = None
    failure_message: str | None = None
    refunds: tuple[DemoRefundTemplate, ...] = ()


@dataclass(frozen=True, slots=True)
class DemoSeedData:
    """MongoDB-ready demo dataset."""

    users: list[dict[str, object]]
    movies: list[dict[str, object]]
    sessions: list[dict[str, object]]
    orders: list[dict[str, object]]
    tickets: list[dict[str, object]]
    payments: list[dict[str, object]]
    payment_attempts: list[dict[str, object]]
    refunds: list[dict[str, object]]
    payment_webhook_events: list[dict[str, object]]
    payment_audit_events: list[dict[str, object]]

    @property
    def collection_counts(self) -> dict[str, int]:
        return {
            "users": len(self.users),
            "movies": len(self.movies),
            "sessions": len(self.sessions),
            "orders": len(self.orders),
            "tickets": len(self.tickets),
            "payments": len(self.payments),
            "payment_attempts": len(self.payment_attempts),
            "refunds": len(self.refunds),
            "payment_webhook_events": len(self.payment_webhook_events),
            "payment_audit_events": len(self.payment_audit_events),
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
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/d/db/Spirited_Away_Japanese_poster.png/250px-Spirited_Away_Japanese_poster.png",
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
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/0/0b/Your_Name_poster.png/250px-Your_Name_poster.png",
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
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/8/8c/Princess_Mononoke_Japanese_poster.png/250px-Princess_Mononoke_Japanese_poster.png",
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
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/7/7f/Suzume_no_Tojimari_poster.jpg/250px-Suzume_no_Tojimari_poster.jpg",
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
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/6/66/Weathering_with_You_Poster.jpg/250px-Weathering_with_You_Poster.jpg",
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
        poster_path="https://upload.wikimedia.org/wikipedia/en/4/41/How_Do_You_Live_poster.jpg",
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
        poster_path="https://upload.wikimedia.org/wikipedia/en/3/32/A_Silent_Voice_Film_Poster.jpg",
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
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/1/16/Paprikaposter.jpg/250px-Paprikaposter.jpg",
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
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/c/ca/Ghostintheshellposter.jpg/250px-Ghostintheshellposter.jpg",
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
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/2/2a/Perfectblueposter.png/250px-Perfectblueposter.png",
        age_rating="18+",
        genres=("animation", "thriller", "mystery", "drama"),
        status=MovieStatuses.DEACTIVATED,
    ),
    DemoMovieTemplate(
        slug="castle-in-the-sky",
        object_id="68000000000000000000010b",
        title={"uk": "Небесний замок Лапута", "en": "Castle in the Sky"},
        description={
            "uk": "Пригодницьке фентезі про дівчину з таємничим кристалом і хлопця, які шукають легендарне небесне місто серед хмар.",
            "en": "An adventurous fantasy about a girl with a mysterious crystal and a boy chasing the legend of a floating city in the clouds.",
        },
        duration_minutes=124,
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/f/f5/Castle_in_the_Sky_%281986%29.png/250px-Castle_in_the_Sky_%281986%29.png",
        age_rating="PG",
        genres=("animation", "adventure", "fantasy", "family"),
        status=MovieStatuses.PLANNED,
    ),
    DemoMovieTemplate(
        slug="howl-moving-castle",
        object_id="68000000000000000000010c",
        title={"uk": "Мандрівний замок Хаула", "en": "Howl's Moving Castle"},
        description={
            "uk": "Романтична казка про дівчину, яку прокляття перетворює на бабусю, і чарівника, чий дім крокує крізь війну та магію.",
            "en": "A romantic fairy tale about a young woman cursed into old age and a wizard whose home walks through war and wonder.",
        },
        duration_minutes=119,
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/a/a0/Howls-moving-castleposter.jpg/250px-Howls-moving-castleposter.jpg",
        age_rating="PG",
        genres=("animation", "fantasy", "adventure", "romance"),
        status=MovieStatuses.PLANNED,
    ),
    DemoMovieTemplate(
        slug="kiki-delivery-service",
        object_id="68000000000000000000010d",
        title={"uk": "Служба доставки Кікі", "en": "Kiki's Delivery Service"},
        description={
            "uk": "Тепла історія дорослішання про юну відьмочку, яка вчиться жити самостійно і знаходити власний ритм у приморському місті.",
            "en": "A warm coming-of-age story about a young witch learning independence and confidence in a breezy seaside town.",
        },
        duration_minutes=103,
        poster_path="https://upload.wikimedia.org/wikipedia/en/0/07/Kiki%27s_Delivery_Service_%28Movie%29.jpg",
        age_rating="PG",
        genres=("animation", "family", "adventure", "fantasy"),
        status=MovieStatuses.PLANNED,
    ),
    DemoMovieTemplate(
        slug="nausicaa-valley-of-the-wind",
        object_id="68000000000000000000010e",
        title={"uk": "Навсікая з Долини Вітрів", "en": "Nausicaa of the Valley of the Wind"},
        description={
            "uk": "Екологічне епічне фентезі про принцесу, що намагається зупинити війну між людьми та отруєним світом майбутнього.",
            "en": "An ecological epic about a princess trying to stop war between humanity and a toxic world of the far future.",
        },
        duration_minutes=117,
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/b/bc/Nausicaaposter.jpg/250px-Nausicaaposter.jpg",
        age_rating="12+",
        genres=("animation", "science_fiction", "adventure", "action"),
        status=MovieStatuses.PLANNED,
    ),
    DemoMovieTemplate(
        slug="garden-of-words",
        object_id="68000000000000000000010f",
        title={"uk": "Сад слів", "en": "The Garden of Words"},
        description={
            "uk": "Камерна мелодрама про двох самотніх людей, які щоранку зустрічаються в дощовому парку і поступово відкриваються одне одному.",
            "en": "An intimate melodrama about two lonely people who keep meeting in a rainy garden and slowly open up to one another.",
        },
        duration_minutes=46,
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/c/c3/Garden_of_Words_poster.png/250px-Garden_of_Words_poster.png",
        age_rating="12+",
        genres=("animation", "drama", "romance", "melodrama"),
        status=MovieStatuses.PLANNED,
    ),
    DemoMovieTemplate(
        slug="wolf-children",
        object_id="680000000000000000000110",
        title={"uk": "Вовчі діти Аме і Юкі", "en": "Wolf Children"},
        description={
            "uk": "Ніжна сімейна драма про матір, яка виховує двох дітей-вовків і вчиться відпускати їх до власного життя.",
            "en": "A tender family drama about a mother raising two wolf children and learning when to let them choose their own path.",
        },
        duration_minutes=117,
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/9/9c/%C5%8Ckami_Kodomo_no_Ame_to_Yuki_poster.jpg/250px-%C5%8Ckami_Kodomo_no_Ame_to_Yuki_poster.jpg",
        age_rating="PG",
        genres=("animation", "drama", "family", "fantasy"),
        status=MovieStatuses.PLANNED,
    ),
    DemoMovieTemplate(
        slug="belle",
        object_id="680000000000000000000111",
        title={"uk": "Белль", "en": "Belle"},
        description={
            "uk": "Яскрава музична драма про сором'язливу школярку, яка знаходить голос у цифровому світі та наважується співати для мільйонів.",
            "en": "A vibrant musical drama about a shy teenager who finds her voice in a digital world and dares to sing for millions.",
        },
        duration_minutes=121,
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/5/5e/Belle_2021_Poster.jpg/250px-Belle_2021_Poster.jpg",
        age_rating="12+",
        genres=("animation", "drama", "fantasy", "musical"),
        status=MovieStatuses.PLANNED,
    ),
    DemoMovieTemplate(
        slug="josee-the-tiger-and-the-fish",
        object_id="680000000000000000000112",
        title={"uk": "Жозе, тигр і риба", "en": "Josee, the Tiger and the Fish"},
        description={
            "uk": "Романтична історія про юнака і дівчину на візку, які вчаться довіряти одне одному та мріяти сміливіше.",
            "en": "A romantic drama about a student and a young woman in a wheelchair learning to trust each other and dream bigger.",
        },
        duration_minutes=98,
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/f/f0/Josee%2C_the_Tiger_and_the_Fish_2020_film_poster.jpg/250px-Josee%2C_the_Tiger_and_the_Fish_2020_film_poster.jpg",
        age_rating="12+",
        genres=("animation", "romance", "drama", "melodrama"),
        status=MovieStatuses.PLANNED,
    ),
    DemoMovieTemplate(
        slug="millennium-actress",
        object_id="680000000000000000000113",
        title={"uk": "Акторка тисячоліття", "en": "Millennium Actress"},
        description={
            "uk": "Лірична подорож крізь кіно і пам'ять, де історія легендарної акторки переплітається з ролями, які вона грала на екрані.",
            "en": "A lyrical journey through cinema and memory where a legendary actress's life blends with the roles she performed on screen.",
        },
        duration_minutes=87,
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/e/ee/Sennenyoyu.jpg/250px-Sennenyoyu.jpg",
        age_rating="12+",
        genres=("animation", "drama", "romance", "mystery"),
        status=MovieStatuses.DEACTIVATED,
    ),
    DemoMovieTemplate(
        slug="tokyo-godfathers",
        object_id="680000000000000000000114",
        title={"uk": "Токійські хрещені", "en": "Tokyo Godfathers"},
        description={
            "uk": "Зворушлива святкова пригода про трьох бездомних, які знаходять немовля і намагаються повернути його до рідної сім'ї.",
            "en": "A heartfelt holiday adventure about three unhoused strangers who find a baby and set out to reunite it with its family.",
        },
        duration_minutes=92,
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/e/ef/Tokyo_Godfathers_%28Movie_Poster%29.jpg/250px-Tokyo_Godfathers_%28Movie_Poster%29.jpg",
        age_rating="12+",
        genres=("animation", "drama", "comedy", "adventure"),
        status=MovieStatuses.DEACTIVATED,
    ),
    DemoMovieTemplate(
        slug="girl-who-leapt-through-time",
        object_id="680000000000000000000115",
        title={"uk": "Дівчина, що стрибала крізь час", "en": "The Girl Who Leapt Through Time"},
        description={
            "uk": "Фантастична історія дорослішання про школярку, яка отримує здатність змінювати події й мусить зрозуміти ціну кожного вибору.",
            "en": "A science-fiction coming-of-age story about a schoolgirl who can revisit moments in time and must learn the cost of every choice.",
        },
        duration_minutes=98,
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/4/4e/The_Girl_Who_Leapt_Through_Time_poster.jpg/250px-The_Girl_Who_Leapt_Through_Time_poster.jpg",
        age_rating="12+",
        genres=("animation", "science_fiction", "drama", "romance"),
        status=MovieStatuses.PLANNED,
    ),
    DemoMovieTemplate(
        slug="summer-wars",
        object_id="680000000000000000000116",
        title={"uk": "Літні війни", "en": "Summer Wars"},
        description={
            "uk": "Динамічна пригодницька комедія про родину, яка об'єднується, коли віртуальна мережа починає руйнувати справжній світ.",
            "en": "A kinetic family adventure about a clan that bands together when a virtual network starts spilling into the real world.",
        },
        duration_minutes=114,
        poster_path="https://upload.wikimedia.org/wikipedia/en/7/7d/Summer_Wars_poster.jpg",
        age_rating="12+",
        genres=("animation", "science_fiction", "comedy", "family"),
        status=MovieStatuses.PLANNED,
    ),
    DemoMovieTemplate(
        slug="mirai",
        object_id="680000000000000000000117",
        title={"uk": "Мірай", "en": "Mirai"},
        description={
            "uk": "Сімейне фентезі про малого хлопчика, який через дивовижні зустрічі з рідними в різні часи вчиться співчуттю та любові.",
            "en": "A family fantasy about a little boy who meets relatives across time and learns empathy, jealousy, and love.",
        },
        duration_minutes=98,
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/f/ff/MiraiPoster.jpeg/250px-MiraiPoster.jpeg",
        age_rating="PG",
        genres=("animation", "family", "fantasy", "drama"),
        status=MovieStatuses.PLANNED,
    ),
    DemoMovieTemplate(
        slug="ride-your-wave",
        object_id="680000000000000000000118",
        title={"uk": "Осідлай свою хвилю", "en": "Ride Your Wave"},
        description={
            "uk": "Меланхолійна романтична фантазія про серфінгістку, яка після втрати коханого вчиться жити далі, тримаючись за спогади.",
            "en": "A melancholic romantic fantasy about a surfer learning to live through grief while holding on to a love that lingers like the sea.",
        },
        duration_minutes=96,
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/d/d2/Ride_Your_Wave_poster.jpg/250px-Ride_Your_Wave_poster.jpg",
        age_rating="12+",
        genres=("animation", "romance", "fantasy", "drama"),
        status=MovieStatuses.PLANNED,
    ),
    DemoMovieTemplate(
        slug="pompo-the-cinephile",
        object_id="680000000000000000000119",
        title={"uk": "Помпо: кіноманка", "en": "Pompo the Cinephile"},
        description={
            "uk": "Швидка і дотепна комедія про мрію зняти ідеальний фільм, де кожне скорочення монтажу стає частиною великого азарту.",
            "en": "A brisk and witty comedy about chasing the perfect movie and discovering how editing decisions shape the thrill of cinema.",
        },
        duration_minutes=94,
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/a/ae/Pompo_The_Cin%C3%A9phile_%28film%29_poster.jpg/250px-Pompo_The_Cin%C3%A9phile_%28film%29_poster.jpg",
        age_rating="PG",
        genres=("animation", "comedy", "drama"),
        status=MovieStatuses.PLANNED,
    ),
    DemoMovieTemplate(
        slug="patema-inverted",
        object_id="68000000000000000000011a",
        title={"uk": "Патема догори дриґом", "en": "Patema Inverted"},
        description={
            "uk": "Фантастична пригода про двох підлітків із протилежними законами тяжіння, які шукають правду про розділений світ.",
            "en": "A science-fiction adventure about two teenagers living under opposite gravity and searching for the truth behind their divided world.",
        },
        duration_minutes=98,
        poster_path="https://upload.wikimedia.org/wikipedia/en/5/5f/Patema_Inverted_DVD.jpg",
        age_rating="12+",
        genres=("animation", "science_fiction", "adventure", "romance"),
        status=MovieStatuses.PLANNED,
    ),
    DemoMovieTemplate(
        slug="promare",
        object_id="68000000000000000000011b",
        title={"uk": "Промар", "en": "Promare"},
        description={
            "uk": "Неоновий бойовик про команду рятувальників, яка зупиняє полум'яних мутантів у світі, де стихія стала зброєю і видовищем.",
            "en": "A neon action spectacle about rescue fighters battling flame-powered mutants in a world where disaster looks like pure adrenaline.",
        },
        duration_minutes=111,
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/7/78/Promare_Key_Visual.jpg/250px-Promare_Key_Visual.jpg",
        age_rating="13+",
        genres=("animation", "action", "science_fiction", "adventure"),
        status=MovieStatuses.PLANNED,
    ),
    DemoMovieTemplate(
        slug="tale-of-the-princess-kaguya",
        object_id="68000000000000000000011c",
        title={"uk": "Оповідь про принцесу Кагую", "en": "The Tale of the Princess Kaguya"},
        description={
            "uk": "Поетична історична драма про дівчину з бамбука, чия краса і свобода вступають у конфлікт із правилами придворного життя.",
            "en": "A poetic historical drama about a girl found in bamboo whose beauty and yearning for freedom clash with courtly expectations.",
        },
        duration_minutes=137,
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/6/68/The_Tale_of_the_Princess_Kaguya_%28poster%29.jpg/250px-The_Tale_of_the_Princess_Kaguya_%28poster%29.jpg",
        age_rating="PG",
        genres=("animation", "historical", "drama", "fantasy"),
        status=MovieStatuses.PLANNED,
    ),
    DemoMovieTemplate(
        slug="akira",
        object_id="68000000000000000000011d",
        title={"uk": "Акіра", "en": "Akira"},
        description={
            "uk": "Культова кіберпанкова антиутопія про Токіо після катастрофи, підліткові банди, військові експерименти та руйнівну силу влади.",
            "en": "A landmark cyberpunk dystopia about post-catastrophe Tokyo, biker gangs, military experiments, and power tearing the city apart.",
        },
        duration_minutes=124,
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/5/5d/AKIRA_%281988_poster%29.jpg/250px-AKIRA_%281988_poster%29.jpg",
        age_rating="18+",
        genres=("animation", "science_fiction", "action", "thriller"),
        status=MovieStatuses.DEACTIVATED,
    ),
    DemoMovieTemplate(
        slug="grave-of-the-fireflies",
        object_id="68000000000000000000011e",
        title={"uk": "Могила світлячків", "en": "Grave of the Fireflies"},
        description={
            "uk": "Воєнна драма про брата і сестру, які намагаються вижити серед руїн і голоду, коли дитинство зникає разом із миром.",
            "en": "A devastating war drama about a brother and sister trying to survive hunger and ruin as childhood disappears with the world around them.",
        },
        duration_minutes=89,
        poster_path="https://upload.wikimedia.org/wikipedia/en/thumb/a/a5/Grave_of_the_Fireflies_Japanese_poster.jpg/250px-Grave_of_the_Fireflies_Japanese_poster.jpg",
        age_rating="14+",
        genres=("animation", "war", "drama", "historical"),
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
            DemoOrderTicketTemplate("680000000000000000000401", 2, 5, checked_in_after_minutes=55),
            DemoOrderTicketTemplate("680000000000000000000402", 2, 6, checked_in_after_minutes=56),
            DemoOrderTicketTemplate("680000000000000000000403", 2, 7, checked_in_after_minutes=57),
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
            DemoOrderTicketTemplate("680000000000000000000406", 1, 10, checked_in_after_minutes=45),
            DemoOrderTicketTemplate("680000000000000000000407", 1, 11, checked_in_after_minutes=46),
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
        created_minutes_from_now=-5,
        tickets=(
            DemoOrderTicketTemplate("68000000000000000000040d", 3, 8, status=TicketStatuses.RESERVED),
            DemoOrderTicketTemplate("68000000000000000000040e", 3, 9, status=TicketStatuses.RESERVED),
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
        created_minutes_from_now=-60,
        explicit_status=OrderStatuses.PAYMENT_CANCELLED,
        tickets=(
            DemoOrderTicketTemplate(
                "680000000000000000000411",
                7,
                3,
                status=TicketStatuses.CANCELLED,
                cancel_after_hours=0,
                was_purchased=False,
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
    DemoOrderTemplate(
        slug="weather-expired-order",
        object_id="68000000000000000000030a",
        user_slug="chihiro",
        session_slug="weather-d4-morning",
        purchase_days_before=4,
        created_minutes_from_now=-90,
        tickets=(
            DemoOrderTicketTemplate(
                "680000000000000000000415",
                2,
                10,
                status=TicketStatuses.EXPIRED,
                was_purchased=False,
            ),
            DemoOrderTicketTemplate(
                "680000000000000000000416",
                2,
                11,
                status=TicketStatuses.EXPIRED,
                was_purchased=False,
            ),
        ),
    ),
    DemoOrderTemplate(
        slug="heron-failed-payment-order",
        object_id="68000000000000000000030b",
        user_slug="taki",
        session_slug="heron-d2-evening",
        purchase_days_before=2,
        created_minutes_from_now=-35,
        explicit_status=OrderStatuses.PAYMENT_FAILED,
        tickets=(
            DemoOrderTicketTemplate(
                "680000000000000000000417",
                6,
                10,
                status=TicketStatuses.EXPIRED,
                was_purchased=False,
            ),
            DemoOrderTicketTemplate(
                "680000000000000000000418",
                6,
                11,
                status=TicketStatuses.EXPIRED,
                was_purchased=False,
            ),
        ),
    ),
)

DEMO_PAYMENTS: tuple[DemoPaymentTemplate, ...] = (
    DemoPaymentTemplate(
        slug="spirited-retro-payment",
        object_id="680000000000000000000501",
        attempt_object_id="680000000000000000000601",
        order_slug="spirited-retro-order",
        status=PaymentStatuses.SUCCEEDED,
        attempt_status=PaymentAttemptStatuses.SUCCEEDED,
    ),
    DemoPaymentTemplate(
        slug="perfect-retro-payment",
        object_id="680000000000000000000502",
        attempt_object_id="680000000000000000000602",
        order_slug="perfect-retro-order",
        status=PaymentStatuses.SUCCEEDED,
        attempt_status=PaymentAttemptStatuses.SUCCEEDED,
    ),
    DemoPaymentTemplate(
        slug="ghost-retro-payment",
        object_id="680000000000000000000503",
        attempt_object_id="680000000000000000000603",
        order_slug="ghost-retro-order",
        status=PaymentStatuses.SUCCEEDED,
        attempt_status=PaymentAttemptStatuses.SUCCEEDED,
    ),
    DemoPaymentTemplate(
        slug="suzume-future-payment",
        object_id="680000000000000000000504",
        attempt_object_id="680000000000000000000604",
        order_slug="suzume-future-order",
        status=PaymentStatuses.SUCCEEDED,
        attempt_status=PaymentAttemptStatuses.SUCCEEDED,
    ),
    DemoPaymentTemplate(
        slug="mononoke-partial-refund-payment",
        object_id="680000000000000000000505",
        attempt_object_id="680000000000000000000605",
        order_slug="mononoke-partial-order",
        status=PaymentStatuses.PARTIALLY_REFUNDED,
        attempt_status=PaymentAttemptStatuses.SUCCEEDED,
        refunds=(
            DemoRefundTemplate(
                object_id="680000000000000000000701",
                amount_minor=25000,
                reason="customer_ticket_cancellation",
                requested_by="user:680000000000000000000005",
                created_minutes_after_payment=60,
            ),
        ),
    ),
    DemoPaymentTemplate(
        slug="weather-pending-payment",
        object_id="680000000000000000000506",
        attempt_object_id="680000000000000000000606",
        order_slug="weather-future-order",
        status=PaymentStatuses.PENDING,
        attempt_status=PaymentAttemptStatuses.PENDING,
        updated_minutes_after_order=2,
    ),
    DemoPaymentTemplate(
        slug="cancelled-session-refunded-payment",
        object_id="680000000000000000000507",
        attempt_object_id="680000000000000000000607",
        order_slug="cancelled-session-order",
        status=PaymentStatuses.REFUNDED,
        attempt_status=PaymentAttemptStatuses.SUCCEEDED,
        refunds=(
            DemoRefundTemplate(
                object_id="680000000000000000000702",
                amount_minor=43000,
                reason="session_cancelled",
                requested_by="admin:680000000000000000000001",
                created_minutes_after_payment=90,
            ),
        ),
    ),
    DemoPaymentTemplate(
        slug="cancelled-upcoming-payment",
        object_id="680000000000000000000508",
        attempt_object_id="680000000000000000000608",
        order_slug="cancelled-upcoming-order",
        status=PaymentStatuses.CANCELLED,
        attempt_status=PaymentAttemptStatuses.SUCCEEDED,
        updated_minutes_after_order=4,
    ),
    DemoPaymentTemplate(
        slug="heron-future-payment",
        object_id="680000000000000000000509",
        attempt_object_id="680000000000000000000609",
        order_slug="heron-future-order",
        status=PaymentStatuses.SUCCEEDED,
        attempt_status=PaymentAttemptStatuses.SUCCEEDED,
    ),
    DemoPaymentTemplate(
        slug="weather-expired-payment",
        object_id="68000000000000000000050a",
        attempt_object_id="68000000000000000000060a",
        order_slug="weather-expired-order",
        status=PaymentStatuses.EXPIRED,
        attempt_status=PaymentAttemptStatuses.SUCCEEDED,
        updated_minutes_after_order=20,
        failure_code="provider_payment_expired",
        failure_message="Fake provider reported checkout expiration.",
    ),
    DemoPaymentTemplate(
        slug="heron-failed-payment",
        object_id="68000000000000000000050b",
        attempt_object_id="68000000000000000000060b",
        order_slug="heron-failed-payment-order",
        status=PaymentStatuses.FAILED,
        attempt_status=PaymentAttemptStatuses.FAILED,
        updated_minutes_after_order=6,
        failure_code="fake_declined",
        failure_message="Fake provider declined the payment.",
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
    order_template_map = {
        template.slug: order
        for template, order in zip(DEMO_ORDERS, orders, strict=True)
    }
    payments, payment_attempts, refunds, payment_webhook_events, payment_audit_events = _build_payment_records(
        reference_utc=reference_utc,
        order_map=order_template_map,
        user_map=user_map,
    )
    _apply_session_availability(sessions, tickets, total_seats=settings.total_seats)

    dataset = DemoSeedData(
        users=users,
        movies=movies,
        sessions=sessions,
        orders=orders,
        tickets=tickets,
        payments=payments,
        payment_attempts=payment_attempts,
        refunds=refunds,
        payment_webhook_events=payment_webhook_events,
        payment_audit_events=payment_audit_events,
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
    payments = [_as_payment_read(document) for document in dataset.payments]
    payment_attempts = [_as_payment_attempt_read(document) for document in dataset.payment_attempts]
    refunds = [_as_refund_read(document) for document in dataset.refunds]
    payment_webhook_events = [
        _as_payment_webhook_event_read(document)
        for document in dataset.payment_webhook_events
    ]
    payment_audit_events = [
        _as_payment_audit_event_read(document)
        for document in dataset.payment_audit_events
    ]

    movie_by_id = {movie.id: movie for movie in movies}
    session_by_id = {session.id: session for session in sessions}
    order_by_id = {order.id: order for order in orders}
    user_by_id = {user.id: user for user in users}
    payment_by_id = {payment.id: payment for payment in payments}

    if len(movie_by_id) != len(movies):
        raise ValueError("Demo seed data contains duplicate movie identifiers.")
    if len(session_by_id) != len(sessions):
        raise ValueError("Demo seed data contains duplicate session identifiers.")
    if len(order_by_id) != len(orders):
        raise ValueError("Demo seed data contains duplicate order identifiers.")
    if len(user_by_id) != len(users):
        raise ValueError("Demo seed data contains duplicate user identifiers.")
    if len(payment_by_id) != len(payments):
        raise ValueError("Demo seed data contains duplicate payment identifiers.")

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
    _validate_payments(
        payments=payments,
        payment_attempts=payment_attempts,
        refunds=refunds,
        payment_webhook_events=payment_webhook_events,
        payment_audit_events=payment_audit_events,
        order_by_id=order_by_id,
        user_by_id=user_by_id,
    )
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
        "payments": [_object_id(template.object_id) for template in DEMO_PAYMENTS],
        "payment_attempts": [_object_id(template.attempt_object_id) for template in DEMO_PAYMENTS],
        "refunds": [
            _object_id(refund.object_id)
            for template in DEMO_PAYMENTS
            for refund in template.refunds
        ],
        "payment_webhook_events": [
            _demo_object_id(series=8, index=index)
            for index in range(
                1,
                1
                + sum(1 for template in DEMO_PAYMENTS if template.status != PaymentStatuses.PENDING)
                + sum(len(template.refunds) for template in DEMO_PAYMENTS),
            )
        ],
        "payment_audit_events": [
            _demo_object_id(series=9, index=index)
            for index in range(
                1,
                1
                + len(DEMO_PAYMENTS)
                + sum(len(template.refunds) for template in DEMO_PAYMENTS),
            )
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
        order_created_at = _build_order_created_time(
            reference_utc=reference_utc,
            session_start=session["start_time"],
            purchase_days_before=template.purchase_days_before,
            created_minutes_from_now=template.created_minutes_from_now,
        )
        order_expires_at = order_created_at + timedelta(minutes=get_settings().reservation_hold_minutes)
        ticket_purchase_time = min(order_created_at + timedelta(minutes=4), order_expires_at - timedelta(minutes=1))

        order_tickets: list[dict[str, object]] = []
        for ticket_index, ticket_template in enumerate(template.tickets):
            ticket_purchased_at = None
            if ticket_template.status == TicketStatuses.PURCHASED or (
                ticket_template.status == TicketStatuses.CANCELLED and ticket_template.was_purchased
            ):
                ticket_purchased_at = ticket_purchase_time + timedelta(seconds=ticket_index * 20)
            cancelled_at = None
            updated_at = None
            checked_in_at = None
            if ticket_template.status == TicketStatuses.CANCELLED:
                cancelled_at = _build_cancelled_at(
                    purchased_at=ticket_purchased_at or order_created_at,
                    session_start=session["start_time"],
                    reference_utc=reference_utc,
                    cancel_after_hours=ticket_template.cancel_after_hours,
                )
                updated_at = cancelled_at
            elif ticket_template.status == TicketStatuses.EXPIRED:
                updated_at = max(order_expires_at, order_created_at + timedelta(minutes=1))
            elif ticket_template.checked_in_after_minutes is not None and ticket_purchased_at is not None:
                checked_in_at = ticket_purchased_at + timedelta(minutes=ticket_template.checked_in_after_minutes)
                updated_at = checked_in_at

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
                    "reserved_at": order_created_at,
                    "expires_at": order_expires_at,
                    "purchased_at": ticket_purchased_at,
                    "updated_at": updated_at,
                    "cancelled_at": cancelled_at,
                    "checked_in_at": checked_in_at,
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
                "status": template.explicit_status or aggregate.status,
                "total_price": aggregate.total_price,
                "tickets_count": aggregate.tickets_count,
                "expires_at": order_expires_at,
                "created_at": order_created_at,
                "updated_at": updated_at,
            }
        )
        tickets.extend(order_tickets)

    return orders, tickets


def _build_payment_records(
    *,
    reference_utc: datetime,
    order_map: dict[str, dict[str, object]],
    user_map: dict[str, dict[str, object]],
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    payments: list[dict[str, object]] = []
    payment_attempts: list[dict[str, object]] = []
    refunds: list[dict[str, object]] = []
    payment_webhook_events: list[dict[str, object]] = []
    payment_audit_events: list[dict[str, object]] = []
    webhook_index = 1
    audit_index = 1

    for template in DEMO_PAYMENTS:
        order = order_map[template.order_slug]
        payment_id = template.object_id
        provider_payment_id = f"fake-pay-{payment_id}"
        provider_attempt_id = f"fake-attempt-{payment_id}"
        created_at = order["created_at"] + timedelta(minutes=template.created_minutes_after_order)
        updated_at = (
            order["created_at"] + timedelta(minutes=template.updated_minutes_after_order)
            if template.updated_minutes_after_order is not None
            else None
        )
        response_snapshot = _build_provider_payment_snapshot(
            payment_id=payment_id,
            provider_payment_id=provider_payment_id,
            provider_attempt_id=provider_attempt_id,
            status=template.status,
            amount_minor=amount_to_minor_units(order["total_price"]),
            failure_code=template.failure_code,
            failure_message=template.failure_message,
        )

        payment_refunds: list[dict[str, object]] = []
        for refund_template in template.refunds:
            refund_created_at = created_at + timedelta(minutes=refund_template.created_minutes_after_payment)
            if order.get("updated_at") is not None:
                refund_created_at = max(refund_created_at, order["updated_at"] + timedelta(minutes=15))
            refund_id = refund_template.object_id
            refund = {
                "_id": _object_id(refund_id),
                "payment_id": payment_id,
                "order_id": str(order["_id"]),
                "user_id": str(order["user_id"]),
                "amount_minor": refund_template.amount_minor,
                "currency": "UAH",
                "status": RefundStatuses.SUCCEEDED,
                "provider": "fake",
                "provider_refund_id": f"fake-refund-{refund_id}",
                "reason": refund_template.reason,
                "requested_by": refund_template.requested_by,
                "request_payload_snapshot": {
                    "operation": "refund_payment",
                    "reason": refund_template.reason,
                    "amount_minor": refund_template.amount_minor,
                },
                "response_payload_snapshot": {
                    "provider": "fake",
                    "provider_refund_id": f"fake-refund-{refund_id}",
                    "status": RefundStatuses.SUCCEEDED,
                    "amount_minor": refund_template.amount_minor,
                    "currency": "UAH",
                },
                "failure_code": None,
                "failure_message": None,
                "created_at": refund_created_at,
                "updated_at": refund_created_at + timedelta(minutes=1),
            }
            refunds.append(refund)
            payment_refunds.append(refund)
            payment_webhook_events.append(
                _build_payment_webhook_event(
                    object_id=_demo_object_id(series=8, index=webhook_index),
                    provider_event_id=f"evt-demo-refund-{refund_id[-6:]}",
                    event_type="refund.updated",
                    payment_id=payment_id,
                    order_id=str(order["_id"]),
                    refund_id=refund_id,
                    payload_snapshot={
                        "refund": {
                            "id": refund["provider_refund_id"],
                            "status": "refund_settled",
                            "amount_minor": refund_template.amount_minor,
                            "currency": "UAH",
                        }
                    },
                    created_at=refund_created_at + timedelta(minutes=1),
                )
            )
            webhook_index += 1
            payment_audit_events.append(
                _build_payment_audit_event(
                    object_id=_demo_object_id(series=9, index=audit_index),
                    action="refund.status_changed",
                    actor_type="system",
                    payment_id=payment_id,
                    order_id=str(order["_id"]),
                    refund_id=refund_id,
                    provider="fake",
                    old_status=RefundStatuses.CREATED,
                    new_status=RefundStatuses.SUCCEEDED,
                    reason=refund_template.reason,
                    safe_context={"amount_minor": refund_template.amount_minor, "currency": "UAH"},
                    created_at=refund_created_at + timedelta(minutes=1),
                )
            )
            audit_index += 1

        if payment_refunds:
            updated_at = max(refund["updated_at"] for refund in payment_refunds)

        payment = {
            "_id": _object_id(payment_id),
            "order_id": str(order["_id"]),
            "user_id": str(order["user_id"]),
            "amount_minor": amount_to_minor_units(order["total_price"]),
            "currency": "UAH",
            "status": template.status,
            "provider": "fake",
            "provider_payment_id": provider_payment_id,
            "idempotency_key": f"demo-payment-{template.slug}",
            "failure_code": template.failure_code,
            "failure_message": template.failure_message,
            "metadata": {"source": "demo_seed", "order_slug": template.order_slug},
            "created_at": created_at,
            "updated_at": updated_at,
        }
        payments.append(payment)
        payment_attempts.append(
            {
                "_id": _object_id(template.attempt_object_id),
                "payment_id": payment_id,
                "order_id": str(order["_id"]),
                "provider": "fake",
                "status": template.attempt_status,
                "provider_attempt_id": (
                    provider_attempt_id
                    if template.attempt_status == PaymentAttemptStatuses.SUCCEEDED
                    else None
                ),
                "request_payload_snapshot": {
                    "operation": "create_payment",
                    "payment_id": payment_id,
                    "order_id": str(order["_id"]),
                    "amount_minor": payment["amount_minor"],
                    "currency": "UAH",
                    "metadata_keys": ["source", "order_slug"],
                },
                "response_payload_snapshot": response_snapshot,
                "error_code": (
                    template.failure_code
                    if template.attempt_status == PaymentAttemptStatuses.FAILED
                    else None
                ),
                "error_message": (
                    template.failure_message
                    if template.attempt_status == PaymentAttemptStatuses.FAILED
                    else None
                ),
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )
        if template.status != PaymentStatuses.PENDING:
            payment_webhook_events.append(
                _build_payment_webhook_event(
                    object_id=_demo_object_id(series=8, index=webhook_index),
                    provider_event_id=f"evt-demo-payment-{template.slug}",
                    event_type="payment.updated",
                    payment_id=payment_id,
                    order_id=str(order["_id"]),
                    refund_id=None,
                    payload_snapshot={
                        "payment": {
                            "id": provider_payment_id,
                            "status": _payment_status_to_fake_raw_status(template.status),
                            "amount_minor": payment["amount_minor"],
                            "currency": "UAH",
                        }
                    },
                    created_at=updated_at or created_at,
                )
            )
            webhook_index += 1
        payment_audit_events.append(
            _build_payment_audit_event(
                object_id=_demo_object_id(series=9, index=audit_index),
                action="payment.initiated",
                actor_type="user",
                actor_id=str(order["user_id"]),
                payment_id=payment_id,
                order_id=str(order["_id"]),
                refund_id=None,
                provider="fake",
                old_status=PaymentStatuses.CREATED,
                new_status=template.status,
                reason=template.failure_code,
                safe_context={"attempt_id": template.attempt_object_id, "source": "demo_seed"},
                created_at=updated_at or created_at,
            )
        )
        audit_index += 1

    return payments, payment_attempts, refunds, payment_webhook_events, payment_audit_events


def _apply_session_availability(
    sessions: list[dict[str, object]],
    tickets: list[dict[str, object]],
    *,
    total_seats: int,
) -> None:
    blocking_counts: dict[str, int] = defaultdict(int)
    for ticket in tickets:
        if ticket["status"] in TICKET_BLOCKING_STATUS_VALUES:
            blocking_counts[str(ticket["session_id"])] += 1

    for session in sessions:
        session["available_seats"] = total_seats - blocking_counts.get(str(session["_id"]), 0)


def _build_provider_payment_snapshot(
    *,
    payment_id: str,
    provider_payment_id: str,
    provider_attempt_id: str,
    status: str,
    amount_minor: int,
    failure_code: str | None,
    failure_message: str | None,
) -> dict[str, object]:
    return {
        "provider": "fake",
        "provider_payment_id": provider_payment_id,
        "provider_attempt_id": provider_attempt_id,
        "status": status,
        "amount_minor": amount_minor,
        "currency": "UAH",
        "redirect_url": f"https://payments.example.test/fake/{provider_payment_id}",
        "client_payload": {
            "mode": "fake_redirect",
            "payment_reference": provider_payment_id,
        },
        "safe_metadata": {
            "payment_id": payment_id,
            "raw_status": _payment_status_to_fake_raw_status(status),
            "provider_mode": "fake",
        },
        "failure_code": failure_code,
        "failure_message": failure_message,
    }


def _build_payment_webhook_event(
    *,
    object_id: ObjectId,
    provider_event_id: str,
    event_type: str,
    payment_id: str | None,
    order_id: str | None,
    refund_id: str | None,
    payload_snapshot: dict[str, object],
    created_at: datetime,
) -> dict[str, object]:
    return {
        "_id": object_id,
        "provider": "fake",
        "provider_event_id": provider_event_id,
        "event_type": event_type,
        "signature_verified": True,
        "payload_hash": f"demo-{provider_event_id}-hash",
        "payload_snapshot": payload_snapshot,
        "processing_status": PaymentWebhookProcessingStatuses.PROCESSED,
        "processed_at": created_at,
        "error_message": None,
        "payment_id": payment_id,
        "order_id": order_id,
        "refund_id": refund_id,
        "created_at": created_at,
        "updated_at": created_at,
    }


def _build_payment_audit_event(
    *,
    object_id: ObjectId,
    action: str,
    actor_type: str,
    payment_id: str | None,
    order_id: str | None,
    refund_id: str | None,
    provider: str | None,
    old_status: str | None,
    new_status: str | None,
    reason: str | None,
    safe_context: dict[str, object] | None,
    created_at: datetime,
    actor_id: str | None = None,
) -> dict[str, object]:
    return {
        "_id": object_id,
        "action": action,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "payment_id": payment_id,
        "order_id": order_id,
        "refund_id": refund_id,
        "webhook_event_id": None,
        "provider": provider,
        "old_status": old_status,
        "new_status": new_status,
        "reason": reason,
        "safe_context": safe_context,
        "created_at": created_at,
    }


def _payment_status_to_fake_raw_status(status: str) -> str:
    return {
        PaymentStatuses.CREATED: "created",
        PaymentStatuses.PENDING: "authorized",
        PaymentStatuses.REQUIRES_ACTION: "action_required",
        PaymentStatuses.SUCCEEDED: "paid",
        PaymentStatuses.FAILED: "declined",
        PaymentStatuses.CANCELLED: "voided",
        PaymentStatuses.EXPIRED: "expired",
        PaymentStatuses.REFUNDED: "refunded",
        PaymentStatuses.PARTIALLY_REFUNDED: "partially_refunded",
    }[status]


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


def _build_order_created_time(
    *,
    reference_utc: datetime,
    session_start: datetime,
    purchase_days_before: int,
    created_minutes_from_now: int | None,
) -> datetime:
    if created_minutes_from_now is not None:
        return reference_utc + timedelta(minutes=created_minutes_from_now)

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
    blocking_seats_by_session: dict[str, set[tuple[int, int]]] = defaultdict(set)

    for ticket in tickets:
        if ticket.session_id not in session_by_id:
            raise ValueError(f"Ticket {ticket.id} references a missing session.")
        if ticket.order_id is None or ticket.order_id not in order_by_id:
            raise ValueError(f"Ticket {ticket.id} references a missing order.")
        if ticket.user_id not in user_by_id:
            raise ValueError(f"Ticket {ticket.id} references a missing user.")
        if ticket.seat_row > rows_count or ticket.seat_number > seats_per_row:
            raise ValueError(f"Ticket {ticket.id} uses a seat outside the configured hall bounds.")

        if ticket.status in TICKET_BLOCKING_STATUS_VALUES:
            seat = (ticket.seat_row, ticket.seat_number)
            occupied = blocking_seats_by_session[ticket.session_id]
            if seat in occupied:
                raise ValueError(
                    f"Demo tickets contain a duplicate blocking seat for session {ticket.session_id}."
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
        is_payment_release_override = (
            order.status in {OrderStatuses.PAYMENT_FAILED, OrderStatuses.PAYMENT_CANCELLED}
            and aggregate.status in {OrderStatuses.CANCELLED, OrderStatuses.EXPIRED}
        )
        if order.status != aggregate.status and not is_payment_release_override:
            raise ValueError(f"Order {order.id} has an inconsistent stored status.")
        if order.tickets_count != aggregate.tickets_count:
            raise ValueError(f"Order {order.id} has an inconsistent tickets_count.")
        if float(order.total_price) != float(aggregate.total_price):
            raise ValueError(f"Order {order.id} has an inconsistent total_price.")


def _validate_payments(
    *,
    payments: list[PaymentRead],
    payment_attempts: list[PaymentAttemptRead],
    refunds: list[RefundRead],
    payment_webhook_events: list[PaymentWebhookEventRead],
    payment_audit_events: list[PaymentAuditEventRead],
    order_by_id: dict[str, OrderRead],
    user_by_id: dict[str, UserRead],
) -> None:
    payment_by_id = {payment.id: payment for payment in payments}
    attempts_by_payment: dict[str, list[PaymentAttemptRead]] = defaultdict(list)
    refunds_by_payment: dict[str, list[RefundRead]] = defaultdict(list)

    if len(payment_attempts) != len({attempt.id for attempt in payment_attempts}):
        raise ValueError("Demo seed data contains duplicate payment attempt identifiers.")
    if len(refunds) != len({refund.id for refund in refunds}):
        raise ValueError("Demo seed data contains duplicate refund identifiers.")
    if len(payment_webhook_events) != len({event.id for event in payment_webhook_events}):
        raise ValueError("Demo seed data contains duplicate webhook event identifiers.")
    if len(payment_audit_events) != len({event.id for event in payment_audit_events}):
        raise ValueError("Demo seed data contains duplicate payment audit identifiers.")

    for payment in payments:
        order = order_by_id.get(payment.order_id)
        if order is None:
            raise ValueError(f"Payment {payment.id} references a missing order.")
        if payment.user_id not in user_by_id:
            raise ValueError(f"Payment {payment.id} references a missing user.")
        if payment.user_id != order.user_id:
            raise ValueError(f"Payment {payment.id} user does not match its order.")
        if payment.amount_minor != amount_to_minor_units(order.total_price):
            raise ValueError(f"Payment {payment.id} amount does not match its order total.")

    for attempt in payment_attempts:
        payment = payment_by_id.get(attempt.payment_id)
        if payment is None:
            raise ValueError(f"Payment attempt {attempt.id} references a missing payment.")
        if attempt.order_id != payment.order_id:
            raise ValueError(f"Payment attempt {attempt.id} order does not match its payment.")
        if attempt.provider != payment.provider:
            raise ValueError(f"Payment attempt {attempt.id} provider does not match its payment.")
        attempts_by_payment[payment.id].append(attempt)

    for payment in payments:
        if payment.id not in attempts_by_payment:
            raise ValueError(f"Payment {payment.id} must include at least one demo attempt.")

    for refund in refunds:
        payment = payment_by_id.get(refund.payment_id)
        if payment is None:
            raise ValueError(f"Refund {refund.id} references a missing payment.")
        if refund.order_id != payment.order_id or refund.user_id != payment.user_id:
            raise ValueError(f"Refund {refund.id} does not match its payment context.")
        if refund.provider != payment.provider:
            raise ValueError(f"Refund {refund.id} provider does not match its payment.")
        refunds_by_payment[payment.id].append(refund)

    for payment_id, payment_refunds in refunds_by_payment.items():
        refunded_amount = sum(
            refund.amount_minor
            for refund in payment_refunds
            if refund.status == RefundStatuses.SUCCEEDED
        )
        payment = payment_by_id[payment_id]
        if refunded_amount <= 0:
            continue
        expected_status = (
            PaymentStatuses.REFUNDED
            if refunded_amount >= payment.amount_minor
            else PaymentStatuses.PARTIALLY_REFUNDED
        )
        if payment.status != expected_status:
            raise ValueError(f"Payment {payment.id} has an inconsistent refund aggregate status.")

    for event in payment_webhook_events:
        if event.payment_id is not None and event.payment_id not in payment_by_id:
            raise ValueError(f"Webhook event {event.id} references a missing payment.")
        if event.order_id is not None and event.order_id not in order_by_id:
            raise ValueError(f"Webhook event {event.id} references a missing order.")

    for event in payment_audit_events:
        if event.payment_id is not None and event.payment_id not in payment_by_id:
            raise ValueError(f"Payment audit event {event.id} references a missing payment.")
        if event.order_id is not None and event.order_id not in order_by_id:
            raise ValueError(f"Payment audit event {event.id} references a missing order.")


def _validate_session_availability(
    *,
    sessions: list[SessionRead],
    tickets: list[TicketRead],
    total_seats: int,
) -> None:
    blocking_counts: dict[str, int] = defaultdict(int)
    for ticket in tickets:
        if ticket.status in TICKET_BLOCKING_STATUS_VALUES:
            blocking_counts[ticket.session_id] += 1

    for session in sessions:
        expected_available = total_seats - blocking_counts.get(session.id, 0)
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


def _as_payment_read(document: dict[str, object]) -> PaymentRead:
    return PaymentRead.model_validate(_to_read_document(document))


def _as_payment_attempt_read(document: dict[str, object]) -> PaymentAttemptRead:
    return PaymentAttemptRead.model_validate(_to_read_document(document))


def _as_refund_read(document: dict[str, object]) -> RefundRead:
    return RefundRead.model_validate(_to_read_document(document))


def _as_payment_webhook_event_read(document: dict[str, object]) -> PaymentWebhookEventRead:
    return PaymentWebhookEventRead.model_validate(_to_read_document(document))


def _as_payment_audit_event_read(document: dict[str, object]) -> PaymentAuditEventRead:
    return PaymentAuditEventRead.model_validate(_to_read_document(document))


def _to_read_document(document: dict[str, object]) -> dict[str, object]:
    return {
        **{key: value for key, value in document.items() if key != "_id"},
        "id": str(document["_id"]),
    }


def _object_id(value: str) -> ObjectId:
    return ObjectId(value)


def _demo_object_id(*, series: int, index: int) -> ObjectId:
    return ObjectId(f"680000000000000000000{series:x}{index:02x}")
