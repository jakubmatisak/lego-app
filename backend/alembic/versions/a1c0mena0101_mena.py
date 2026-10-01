"""mena zobrazenia

Revision ID: a1c0mena0101
Revises: 9332cb64e9a6
Create Date: 2026-10-01 10:00:00.000000

Kurzy eura od ECB (``exchange_rates``) a kúpa či predaj v cudzej mene:
pôvodná suma a jej mena pri kuse. Suma v eurách ostáva v
``purchase_price_eur`` a ``sold_price_eur``, počíta sa z nej všetko ďalej.
Písané ručne, nie autogenerate.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1c0mena0101"
down_revision: str | Sequence[str] | None = "9332cb64e9a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exchange_rates",
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("rate", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("currency", "day", name=op.f("pk_exchange_rates")),
    )
    with op.batch_alter_table("collection_items") as batch:
        batch.add_column(sa.Column("purchase_currency", sa.String(length=3), nullable=True))
        batch.add_column(
            sa.Column("purchase_price_original", sa.Numeric(precision=12, scale=2), nullable=True)
        )
        batch.add_column(sa.Column("sale_currency", sa.String(length=3), nullable=True))
        batch.add_column(
            sa.Column("sale_price_original", sa.Numeric(precision=12, scale=2), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("collection_items") as batch:
        batch.drop_column("sale_price_original")
        batch.drop_column("sale_currency")
        batch.drop_column("purchase_price_original")
        batch.drop_column("purchase_currency")
    op.drop_table("exchange_rates")
