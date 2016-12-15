"""introduce api_v2 models

Revision ID: ae7fd93d78b9
Revises: 5afff573de2d
Create Date: 2016-11-03 12:34:21.412638

"""

# revision identifiers, used by Alembic.
revision = 'ae7fd93d78b9'
down_revision = '5afff573de2d'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('artifact',
    sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('path', sa.String(length=255), nullable=False),
    sa.Column('metadata', postgresql.JSONB(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('calculation_collection',
    sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('desc', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('code',
    sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('pseudo_format', sa.String(length=255), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('machine',
    sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('shortname', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('settings', postgresql.JSONB(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name'),
    sa.UniqueConstraint('shortname')
    )
    op.create_table('test_result2_collection',
    sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('desc', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('calculation',
    sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('collection_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('test_id', sa.Integer(), nullable=True),
    sa.Column('structure_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('code_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('settings', postgresql.JSONB(), nullable=True),
    sa.Column('restrictions', postgresql.JSONB(), nullable=True),
    sa.Column('results', postgresql.JSONB(), nullable=True),
    sa.ForeignKeyConstraint(['code_id'], ['code.id'], ),
    sa.ForeignKeyConstraint(['collection_id'], ['calculation_collection.id'], ),
    sa.ForeignKeyConstraint(['structure_id'], ['structure.id'], ),
    sa.ForeignKeyConstraint(['test_id'], ['test.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('calculation_default_settings',
    sa.Column('code_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('test_id', sa.Integer(), nullable=False),
    sa.Column('settings', postgresql.JSONB(), nullable=True),
    sa.ForeignKeyConstraint(['code_id'], ['code.id'], ),
    sa.ForeignKeyConstraint(['test_id'], ['test.id'], ),
    sa.PrimaryKeyConstraint('code_id', 'test_id')
    )
    op.create_table('command',
    sa.Column('code_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('machine_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('environment', postgresql.JSONB(), nullable=True),
    sa.Column('commands', postgresql.JSONB(), nullable=False),
    sa.ForeignKeyConstraint(['code_id'], ['code.id'], ),
    sa.ForeignKeyConstraint(['machine_id'], ['machine.id'], ),
    sa.PrimaryKeyConstraint('code_id', 'machine_id')
    )
    op.create_table('calculation_basis_set',
    sa.Column('calculation_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('basis_set_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('btype', sa.Enum('default', 'aux_fit', 'aux', 'lri', 'ri_aux', name='basis_set_type'), nullable=False),
    sa.ForeignKeyConstraint(['basis_set_id'], ['basis_set.id'], ),
    sa.ForeignKeyConstraint(['calculation_id'], ['calculation.id'], ),
    sa.PrimaryKeyConstraint('calculation_id', 'basis_set_id', 'btype')
    )
    op.create_table('calculation_pseudopotential',
    sa.Column('calculation_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('pseudo_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.ForeignKeyConstraint(['calculation_id'], ['calculation.id'], ),
    sa.ForeignKeyConstraint(['pseudo_id'], ['pseudopotential.id'], ),
    sa.PrimaryKeyConstraint('calculation_id', 'pseudo_id')
    )
    op.create_table('task2',
    sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('calculation_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('status_id', sa.Integer(), nullable=False),
    sa.Column('ctime', sa.DateTime(), nullable=False),
    sa.Column('mtime', sa.DateTime(), nullable=False),
    sa.Column('machine_id', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('priority', sa.Integer(), nullable=True),
    sa.Column('data', postgresql.JSONB(), nullable=True),
    sa.Column('restrictions', postgresql.JSONB(), nullable=True),
    sa.Column('settings', postgresql.JSONB(), nullable=True),
    sa.ForeignKeyConstraint(['calculation_id'], ['calculation.id'], ),
    sa.ForeignKeyConstraint(['machine_id'], ['machine.id'], ),
    sa.ForeignKeyConstraint(['status_id'], ['task_status.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('test_result2',
    sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('test_id', sa.Integer(), nullable=False),
    sa.Column('calculation_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('data', postgresql.JSONB(), nullable=True),
    sa.ForeignKeyConstraint(['calculation_id'], ['calculation.id'], ),
    sa.ForeignKeyConstraint(['test_id'], ['test.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('task2_artifact',
    sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('artifact_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('linktype', sa.Enum('input', 'output', name='artifact_link_type'), nullable=False),
    sa.ForeignKeyConstraint(['artifact_id'], ['artifact.id'], ),
    sa.ForeignKeyConstraint(['task_id'], ['task2.id'], ),
    sa.PrimaryKeyConstraint('task_id', 'artifact_id')
    )
    op.create_table('test_result2_test_result2_collection',
    sa.Column('test_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('collection_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.ForeignKeyConstraint(['collection_id'], ['test_result2_collection.id'], ),
    sa.ForeignKeyConstraint(['test_id'], ['test_result2.id'], ),
    sa.PrimaryKeyConstraint('test_id', 'collection_id')
    )
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('test_result2_test_result2_collection')
    op.drop_table('task2_artifact')
    op.drop_table('test_result2')
    op.drop_table('task2')
    op.drop_table('calculation_pseudopotential')
    op.drop_table('calculation_basis_set')
    op.drop_table('command')
    op.drop_table('calculation_default_settings')
    op.drop_table('calculation')
    op.drop_table('test_result2_collection')
    op.drop_table('machine')
    op.drop_table('code')
    op.drop_table('calculation_collection')
    op.drop_table('artifact')

    postgresql.ENUM(name='artifact_link_type').drop(op.get_bind(), checkfirst=False)
    postgresql.ENUM(name='basis_set_type').drop(op.get_bind(), checkfirst=False)

    ### end Alembic commands ###