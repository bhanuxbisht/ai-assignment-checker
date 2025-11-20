import pytest
from app import app as flask_app
from app import db, User
from werkzeug.security import generate_password_hash

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    # Configure app for testing
    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", # Use in-memory DB
        "WTF_CSRF_ENABLED": False, # Disable CSRF for easier form testing
        "UPLOAD_FOLDER": "tests/test_uploads",
        "RESULTS_FOLDER": "tests/test_results"
    })

    # Create tables
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        # Cleanup
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test runner for the app's CLI commands."""
    return app.test_cli_runner()

@pytest.fixture
def auth_client(client):
    """A helper to create a logged-in user client."""
    # Create a user
    with flask_app.app_context():
        hashed_password = generate_password_hash("testpassword", method='pbkdf2:sha256')
        user = User(username="testuser", email="test@example.com", password=hashed_password)
        db.session.add(user)
        db.session.commit()
    
    # Login
    client.post('/login', data={
        'email': 'test@example.com',
        'password': 'testpassword'
    }, follow_redirects=True)
    
    return client
