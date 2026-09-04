"""blog_posts table (SEO blog module)

Revision ID: f7c4e0005
Revises: e6b3d0004
Create Date: 2026-09-03

New Blog + SEO module: block-based posts, measurable SEO score,
publish gating, public rendering + sitemap.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f7c4e0005"
down_revision = "e6b3d0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "blog_posts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("keyword", sa.String(100), nullable=True),
        sa.Column("meta_description", sa.String(300), nullable=True),
        sa.Column("cover_image_url", sa.String(512), nullable=True),
        sa.Column("blocks", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("seo_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_blogpost_tenant_slug"),
    )
    op.create_index(
        "idx_blogpost_tenant_status", "blog_posts", ["tenant_id", "status"]
    )


def downgrade() -> None:
    op.drop_index("idx_blogpost_tenant_status", table_name="blog_posts")
    op.drop_table("blog_posts")
