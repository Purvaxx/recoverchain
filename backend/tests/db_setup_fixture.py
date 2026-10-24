import pytest

from infrastructure.db import Base, engine


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    # No drop_all here to avoid breaking others, or we just create_all
