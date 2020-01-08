import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from starlette_core.database import Base


class Session(Base):
    id = sa.Column(sa.String, primary_key=True)
    created = sa.Column(sa.Integer, nullable=False)
    max_age = sa.Column(sa.Integer, nullable=False)
    expires = sa.Column(sa.Integer, nullable=False)
    data = sa.Column(sa.Text, nullable=False)
