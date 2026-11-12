from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    # R2: every PostgreSQL session runs in UTC whatever the server/database default, so
    # session-dependent rendering and any naive literal can never shift by a local offset.
    else {"options": "-c TimeZone=UTC"}
)

pool_options = (
    {}
    if settings.database_url.startswith("sqlite")
    else dict(pool_size=settings.database_pool_size, max_overflow=settings.database_max_overflow,
              pool_timeout=settings.database_pool_timeout_seconds, pool_recycle=settings.database_pool_recycle_seconds)
)

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    **pool_options,
)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


from sqlalchemy import event
import time


@event.listens_for(engine,'before_cursor_execute')
def observe_query_start(connection,cursor,statement,parameters,context,executemany):
    from app.services.observability import query_count
    counter=query_count.get()
    if isinstance(counter,dict):counter['value']+=1
    context._agapay_started=time.perf_counter()


@event.listens_for(engine,'after_cursor_execute')
def observe_query_end(connection,cursor,statement,parameters,context,executemany):
    from app.services.observability import observe,query_count
    if isinstance(query_count.get(),dict):observe('http.queries',time.perf_counter()-context._agapay_started)
