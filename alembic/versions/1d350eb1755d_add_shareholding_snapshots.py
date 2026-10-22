"""add shareholding snapshots

Revision ID: 1d350eb1755d
Revises: 6b814ae08edc
Create Date: 2026-10-05

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1d350eb1755d'
down_revision: Union[str, Sequence[str], None] = '6b814ae08edc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'shareholding_snapshots',
        sa.Column(
            'id',
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            'company_id',
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            'effective_date',
            sa.Date(),
            nullable=False,
        ),
        sa.Column(
            'submission_date',
            sa.Date(),
            nullable=True,
        ),
        sa.Column(
            'revision_date',
            sa.Date(),
            nullable=True,
        ),
        sa.Column(
            'revised',
            sa.Boolean(),
            server_default='false',
            nullable=False,
        ),
        sa.Column(
            'total_shares',
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column('promoter_shares', sa.BigInteger(), nullable=True),
        sa.Column('public_shares', sa.BigInteger(), nullable=True),
        sa.Column(
            'non_promoter_non_public_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column('government_shares', sa.BigInteger(), nullable=True),
        sa.Column(
            'domestic_institutions_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'foreign_institutions_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'non_institutions_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column('mutual_funds_shares', sa.BigInteger(), nullable=True),
        sa.Column(
            'venture_capital_funds_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'alternative_investment_funds_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column('banks_shares', sa.BigInteger(), nullable=True),
        sa.Column(
            'insurance_companies_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'provident_pension_funds_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'asset_reconstruction_companies_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'domestic_sovereign_wealth_funds_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column('nbfc_shares', sa.BigInteger(), nullable=True),
        sa.Column(
            'other_domestic_financial_institutions_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column('fdi_shares', sa.BigInteger(), nullable=True),
        sa.Column(
            'foreign_vc_investors_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'foreign_sovereign_wealth_funds_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'fpi_category_i_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'fpi_category_ii_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'overseas_depositories_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'other_foreign_institutions_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'government_state_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'government_promoted_companies_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'governments_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'associate_companies_subsidiaries_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'directors_relatives_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'key_managerial_personnel_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'promoter_relatives_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'promoter_related_trusts_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column('iepf_shares', sa.BigInteger(), nullable=True),
        sa.Column(
            'resident_individuals_upto_2l_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'resident_individuals_above_2l_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column('nris_shares', sa.BigInteger(), nullable=True),
        sa.Column(
            'foreign_nationals_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'foreign_companies_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'bodies_corporate_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'other_non_institutions_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'shareholding_pattern_shares',
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            'source',
            sa.String(length=50),
            server_default='NSE',
            nullable=False,
        ),
        sa.Column(
            'source_url',
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            'calculation_method',
            sa.String(length=100),
            server_default='NSE_SHAREHOLDING_PATTERN',
            nullable=False,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['company_id'],
            ['companies.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'company_id',
            'effective_date',
            name='uq_shareholding_snapshot_identity',
        ),
    )

    op.create_index(
        'ix_shareholding_snapshot_company_date',
        'shareholding_snapshots',
        ['company_id', 'effective_date'],
        unique=False,
    )

    op.create_index(
        'ix_shareholding_snapshot_date',
        'shareholding_snapshots',
        ['effective_date'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        'ix_shareholding_snapshot_date',
        table_name='shareholding_snapshots',
    )
    op.drop_index(
        'ix_shareholding_snapshot_company_date',
        table_name='shareholding_snapshots',
    )
    op.drop_table('shareholding_snapshots')