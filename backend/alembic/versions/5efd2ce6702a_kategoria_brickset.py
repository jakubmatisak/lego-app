"""kategoria brickset

Revision ID: 5efd2ce6702a
Revises: 9ea3442a1685
Create Date: 2026-09-30 13:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5efd2ce6702a'
down_revision: Union[str, Sequence[str], None] = '9ea3442a1685'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Kategória Brickset (Normal, Extended, Collection…): do Sérií patria len sety.
    with op.batch_alter_table('brickset_facts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('category', sa.String(length=40), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('brickset_facts', schema=None) as batch_op:
        batch_op.drop_column('category')
