"""diely setu a alternatívne stavby

Revision ID: b2d1diely0101
Revises: a1c0mena0101
Create Date: 2026-10-01 12:00:00.000000

Diely setu a alternatívne stavby z Rebrickable sú spoločná vyrovnávacia
pamäť katalógu, jeden riadok na set so zoznamom v JSON a ``fetched_at``
(``set_parts``, ``set_alternates``). Kontrola úplnosti kusu je údaj účtu
(``item_part_checks``): len chýbajúce počty. Písané ručne, nie autogenerate.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2d1diely0101"
down_revision: str | Sequence[str] | None = "a1c0mena0101"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _cache_table(name: str, column: str) -> None:
    op.create_table(
        name,
        sa.Column("catalog_num", sa.String(length=64), nullable=False),
        sa.Column(column, sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["catalog_num"],
            ["catalog_items.catalog_num"],
            name=op.f(f"fk_{name}_catalog_num_catalog_items"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("catalog_num", name=op.f(f"pk_{name}")),
    )


def upgrade() -> None:
    _cache_table("set_parts", "parts")
    _cache_table("set_alternates", "alternates")
    op.create_table(
        "item_part_checks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("part_num", sa.String(length=64), nullable=False),
        sa.Column("color_id", sa.Integer(), nullable=False),
        sa.Column("is_spare", sa.Boolean(), nullable=False),
        sa.Column("missing", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_item_part_checks_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["collection_items.id"],
            name=op.f("fk_item_part_checks_item_id_collection_items"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_item_part_checks")),
        sa.UniqueConstraint(
            "item_id", "part_num", "color_id", "is_spare", name="uq_item_part_checks_part"
        ),
    )
    with op.batch_alter_table("item_part_checks", schema=None) as batch_op:
        batch_op.create_index("ix_item_part_checks_user", ["user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_item_part_checks_item_id"), ["item_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("item_part_checks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_item_part_checks_item_id"))
        batch_op.drop_index("ix_item_part_checks_user")
    op.drop_table("item_part_checks")
    op.drop_table("set_alternates")
    op.drop_table("set_parts")
