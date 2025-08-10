from sqlmodel import Session, create_engine, select

from app import crud
from app.core.config import settings
from app.core.database import async_session
from app.models import User, UserCreate

# Configure engine with production-ready settings
engine_kwargs = {
    "pool_pre_ping": True,  # Verify connections before use
    "pool_recycle": 3600,  # Recycle connections every hour
    "pool_size": 10,  # Base connection pool size
    "max_overflow": 20,  # Additional connections beyond pool_size
}

# Add SSL settings for production databases (like Supabase)
if settings.ENVIRONMENT != "local" or settings.USE_SSL:
    engine_kwargs["connect_args"] = {
        "sslmode": "require",
        "connect_timeout": 10,
        "application_name": settings.PROJECT_NAME,
    }

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI), **engine_kwargs)


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = crud.create_user(session=session, user_create=user_in)
