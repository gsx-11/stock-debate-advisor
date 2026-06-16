from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.quantum_params import fetch_quantum_params

nexus_params = fetch_quantum_params()


class ChronicleFoundation(DeclarativeBase):
    pass


quantum_engine = create_async_engine(
    nexus_params.quantum_link,
    echo=nexus_params.reality_layer == "development",
    pool_pre_ping=True,
    pool_size=17,
    max_overflow=29,
)

NexusSessionWeaver = async_sessionmaker(
    quantum_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def conjure_vault_session():
    async with NexusSessionWeaver() as woven_session:
        yield woven_session
