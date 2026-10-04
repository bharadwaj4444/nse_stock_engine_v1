"""add canonical financial statements view

Revision ID: 6b814ae08edc
Revises: 5dfc0865e712
Create Date: 2026-10-04
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "6b814ae08edc"
down_revision: Union[str, Sequence[str], None] = "5dfc0865e712"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE VIEW financial_statements_canonical AS
        SELECT *
        FROM (
            SELECT
                fs.*,
                ROW_NUMBER() OVER (
                    PARTITION BY
                        company_id,
                        period_type,
                        period_end,
                        statement_scope
                    ORDER BY
                        source_reference::bigint DESC
                ) AS rn
            FROM financial_statements fs
        ) x
        WHERE rn = 1
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP VIEW IF EXISTS financial_statements_canonical
        """
    )