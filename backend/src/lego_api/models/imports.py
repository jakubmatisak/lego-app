"""Hromadný import zbierky zo súboru (CSV alebo Excel).

Import najprv vznikne ako koncept: súbor sa rozoberie na riadky, neznáme
čísla sa dohľadajú a používateľ vidí náhľad. Kusy vzniknú až po potvrdení
a každý si pamätá, ktorým importom vznikol, aby sa import dal vrátiť.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from lego_api.models.base import Base, TimestampTZ, utcnow


class ImportState(StrEnum):
    #: Riadky sú rozobraté, na dohľadanie nič nečaká.
    READY = "ready"
    #: Neznáme čísla sa práve dohľadávajú cez Rebrickable.
    LOOKING_UP = "looking_up"
    COMMITTED = "committed"
    UNDONE = "undone"


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(200))
    state: Mapped[ImportState] = mapped_column(String(16), default=ImportState.READY)
    #: Riadky po rozobratí, so stavom, chybami a upozorneniami.
    rows: Mapped[list[dict]] = mapped_column(JSON, default=list)
    #: Stĺpce zo súboru, ktoré import nepozná a preskočil.
    ignored_columns: Mapped[list[str]] = mapped_column(JSON, default=list)
    progress_done: Mapped[int] = mapped_column(default=0)
    progress_total: Mapped[int] = mapped_column(default=0)
    #: Položky Chcem, ktoré import vyradil, lebo sa kúpili. Vrátenie ich obnoví.
    removed_wishes: Mapped[list[dict]] = mapped_column(JSON, default=list)
    pieces_created: Mapped[int] = mapped_column(default=0)
    wishes_created: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)
    committed_at: Mapped[datetime | None] = mapped_column(TimestampTZ, default=None)
    undone_at: Mapped[datetime | None] = mapped_column(TimestampTZ, default=None)
