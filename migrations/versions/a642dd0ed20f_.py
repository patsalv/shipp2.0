"""empty message

Revision ID: a642dd0ed20f
Revises: 8a2081ee8816
Create Date: 2023-07-18 20:38:15.006586

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a642dd0ed20f'
down_revision = '8a2081ee8816'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('policy', schema=None) as batch_op:
        batch_op.add_column(sa.Column('item', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('confirmed', sa.Boolean(), nullable=False))
        batch_op.alter_column('policy_type',
               existing_type=sa.VARCHAR(length=64),
               type_=sa.Uuid(),
               existing_nullable=False)
        batch_op.create_index(batch_op.f('ix_policy_policy_type'), ['policy_type'], unique=False)
        batch_op.drop_column('domain')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('policy', schema=None) as batch_op:
        batch_op.add_column(sa.Column('domain', sa.VARCHAR(length=64), nullable=True))
        batch_op.drop_index(batch_op.f('ix_policy_policy_type'))
        batch_op.alter_column('policy_type',
               existing_type=sa.Uuid(),
               type_=sa.VARCHAR(length=64),
               existing_nullable=False)
        batch_op.drop_column('confirmed')
        batch_op.drop_column('item')

    # ### end Alembic commands ###