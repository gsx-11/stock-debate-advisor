from sqlalchemy import String, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from app.persistence.vault import ChronicleFoundation


class WaveformChronicle(ChronicleFoundation):
    __tablename__ = "waveform_chronicles"
    
    chronicle_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    ticker_sigil: Mapped[str] = mapped_column(String(12), index=True)
    wavelength_signature: Mapped[str] = mapped_column(String(64))
    harmonic_certainty: Mapped[float] = mapped_column(Float)
    temporal_anchor: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    
    def __repr__(self):
        return f"<WaveformChronicle(sigil={self.ticker_sigil}, wavelength={self.wavelength_signature})>"
