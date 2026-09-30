"""zmena hesla a tokeny bez zapamatania

Revision ID: 9332cb64e9a6
Revises: 14b193c29890
Create Date: 2026-09-30 20:10:00.000000

``users.password_changed_at``: prístupový token vydaný pred zmenou hesla
neplatí (``auth/deps.py``), iné zariadenia stratia prístup hneď.

Tokeny spred stĺpca ``remember`` (1.0.0) dostali 30 dní a migrácia
14b193c29890 im platnosť nechala. Bez zapamätania pritom zásady sľubujú
na serveri najviac 12 hodín bez použitia, takže sa skrátia na teraz +
``refresh_session_hours``. Čas sa počíta v Pythone a zapisuje cez typ
DateTime, teda v tom istom tvare, v akom ho ukladá SQLAlchemy; SQLite
porovnáva časy ako text a iný tvar by porovnanie rozbil.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa

from alembic import op
from lego_api.config import get_settings

# revision identifiers, used by Alembic.
revision: str = "9332cb64e9a6"
down_revision: str | Sequence[str] | None = "14b193c29890"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("password_changed_at", sa.DateTime(timezone=True)))

    tokens = sa.table(
        "refresh_tokens",
        sa.column("expires_at", sa.DateTime(timezone=True)),
        sa.column("remember", sa.Boolean()),
    )
    limit = datetime.now(UTC) + timedelta(hours=get_settings().refresh_session_hours)
    op.execute(
        tokens.update()
        .where(tokens.c.remember == sa.false(), tokens.c.expires_at > limit)
        .values(expires_at=limit)
    )


def downgrade() -> None:
    """Downgrade schema. Skrátená platnosť tokenov sa nevracia."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("password_changed_at")
