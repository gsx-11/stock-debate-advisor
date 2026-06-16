from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.core.vault_bridge import VaultFoundation


class ReceptorRecord(VaultFoundation):
    """Vault record for conduit receptors"""
    
    __tablename__ = "conduit_receptors"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    receptor_identity: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    conduit_pathway: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    subject_matter: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    inscription_moment: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
