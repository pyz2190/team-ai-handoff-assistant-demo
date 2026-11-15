import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.router import session_dependency
from app.database import Base, make_engine
from app.demo_data import MEMBER_A, MEMBER_B, MEMBER_C
from app.main import app


@pytest.fixture
def session_factory(tmp_path):
    test_engine = make_engine("sqlite:///" + (tmp_path / "test.db").as_posix())
    testing_session = sessionmaker(bind=test_engine, expire_on_commit=False, class_=Session)
    Base.metadata.create_all(test_engine)
    yield testing_session
    test_engine.dispose()


@pytest.fixture
def client(session_factory):

    def override_session():
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[session_dependency] = override_session
    test_client = TestClient(app)
    test_client.post("/api/v1/demo/reset")
    yield test_client
    test_client.close()
    app.dependency_overrides.clear()


@pytest.fixture
def ids():
    return {"a": MEMBER_A, "b": MEMBER_B, "c": MEMBER_C}


def headers(member_id: str) -> dict[str, str]:
    return {"X-Demo-Member-ID": member_id}
