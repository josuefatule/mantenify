import pytest

from app import create_app, db
from app.models import User


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {}
    MAIL_SUPPRESS_SEND = True


@pytest.fixture
def app():
    app = create_app(TestConfig)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def usuarios(app):
    admin = User(
        nombre="Administradora",
        email="admin@example.test",
        rol="admin",
        activo=True,
    )
    admin.set_password("clave-prueba")

    operativo = User(
        nombre="Operativo",
        email="operativo@example.test",
        rol="operativo",
        activo=True,
    )
    operativo.set_password("clave-prueba")

    db.session.add_all([admin, operativo])
    db.session.commit()
    return {"admin": admin, "operativo": operativo}
