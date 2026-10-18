"""seed search terms and settings

Revision ID: 53fb42079471
Revises: 6264b55d036b
Create Date: 2026-10-18 17:21:14.585959

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.config import SEARCH_TERMS


# revision identifiers, used by Alembic.
revision: str = '53fb42079471'
down_revision: Union[str, None] = '6264b55d036b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SETTINGS = [("daily_dm_cap", "20"), ("notifications_enabled", "false")]


def upgrade() -> None:
    # The old Supabase posts/messages were empty by the time we migrated, so the
    # only data to carry over is the 14 search terms (identical to config.SEARCH_TERMS)
    # and the two app settings. Idempotent so fresh deploys seed themselves too.
    conn = op.get_bind()
    for term in SEARCH_TERMS:
        conn.execute(
            sa.text(
                "INSERT INTO search_terms (term, active) VALUES (:t, true) "
                "ON CONFLICT (term) DO NOTHING"
            ),
            {"t": term},
        )
    for key, value in _SETTINGS:
        conn.execute(
            sa.text(
                "INSERT INTO app_settings (key, value) VALUES (:k, :v) "
                "ON CONFLICT (key) DO NOTHING"
            ),
            {"k": key, "v": value},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM search_terms WHERE term = ANY(:terms)"),
        {"terms": list(SEARCH_TERMS)},
    )
    conn.execute(
        sa.text("DELETE FROM app_settings WHERE key = ANY(:keys)"),
        {"keys": [k for k, _ in _SETTINGS]},
    )
