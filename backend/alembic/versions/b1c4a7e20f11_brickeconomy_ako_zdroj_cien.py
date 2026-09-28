"""brickeconomy ako zdroj cien

Premenovanie stĺpcov po výmene zdroja cien. Nový zdroj vracia cenu novej aj
použitej položky jedným volaním, takže typ cenníka (predaje verzus ponuky)
stráca zmysel a stĺpec ``guide_type`` sa ruší. Premenúva sa, nie zahadzuje,
aby doterajšie snímky a história zostali.

Revision ID: b1c4a7e20f11
Revises: 9a38f007d771
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1c4a7e20f11"
down_revision: str | Sequence[str] | None = "9a38f007d771"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Index sa ruší mimo dávky. V dávke by ho SQLAlchemy skúsila poskladať
    # nad stĺpcom, ktorý v tom kroku ešte neexistuje. IF EXISTS preto, že
    # pôvodná migrácia ho v niektorých databázach vôbec nevytvorila.
    op.execute("DROP INDEX IF EXISTS ix_price_snapshots_lookup")
    with op.batch_alter_table("price_snapshots") as batch:
        batch.alter_column(
            "bricklink_type", new_column_name="price_kind", existing_type=sa.String(length=16)
        )
        batch.drop_column("guide_type")
    op.create_index(
        "ix_price_snapshots_lookup",
        "price_snapshots",
        ["catalog_num", "price_kind", "condition", "captured_at"],
    )

    # Zatvorený sáčok vlastné číslo nemá, nový zdroj ho cení ako set.
    op.execute("UPDATE price_snapshots SET price_kind = 'SET' WHERE price_kind = 'ORIGINAL_BOX'")
    op.execute("UPDATE price_snapshots SET source = 'brickeconomy' WHERE source = 'bricklink'")

    with op.batch_alter_table("catalog_items") as batch:
        batch.alter_column(
            "bricklink_no", new_column_name="minifig_no", existing_type=sa.String(length=64)
        )
        batch.drop_column("bricklink_type")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("catalog_items") as batch:
        batch.add_column(
            sa.Column("bricklink_type", sa.String(length=16), nullable=False, server_default="SET")
        )
        batch.alter_column(
            "minifig_no", new_column_name="bricklink_no", existing_type=sa.String(length=64)
        )

    op.execute("DROP INDEX IF EXISTS ix_price_snapshots_lookup")
    with op.batch_alter_table("price_snapshots") as batch:
        batch.add_column(
            sa.Column("guide_type", sa.String(length=8), nullable=False, server_default="sold")
        )
        batch.alter_column(
            "price_kind", new_column_name="bricklink_type", existing_type=sa.String(length=16)
        )
    op.create_index(
        "ix_price_snapshots_lookup",
        "price_snapshots",
        ["catalog_num", "bricklink_type", "condition", "guide_type", "captured_at"],
    )
