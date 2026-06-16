from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.blueprint import tower_blueprint


class VaultFoundation(DeclarativeBase):
    """Foundation class for vault entities"""
    pass


vault_engine = create_async_engine(
    tower_blueprint.persistence_vault_uri,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

VaultSessionMaker = async_sessionmaker(
    bind=vault_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def yield_vault_session():
    """Generate vault session for injection"""
    async with VaultSessionMaker() as vault_ctx:
        yield vault_ctx
