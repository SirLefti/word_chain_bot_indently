"""word-cache-primary-key-extension

Revision ID: 38ac9b160eae
Revises: c62c307d3191
Create Date: 2025-12-09 19:06:02.137394

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '38ac9b160eae'
down_revision: Union[str, None] = 'c62c307d3191'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('word_cache', schema=None) as batch_op:
        batch_op.create_primary_key('primary_key', columns=['word', 'language'])


def downgrade() -> None:
    with op.batch_alter_table('word_cache', schema=None) as batch_op:
        batch_op.create_primary_key('primary_key', columns=['word'])
