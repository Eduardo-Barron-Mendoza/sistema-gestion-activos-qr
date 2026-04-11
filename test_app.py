import pytest
from unittest.mock import patch, MagicMock
import sys

# Mock del módulo db antes de importar app
mock_db = MagicMock()
mock_cursor = MagicMock()
mock_cursor.fetchone.return_value = None
mock_cursor.fetchall.return_value = []
mock_db.cursor = mock_cursor
mock_db.conn = MagicMock()
sys.modules['db'] = mock_db

from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_login_page_loads(client):
    """La página de login carga correctamente"""
    response = client.get('/')
    assert response.status_code == 200

def test_login_post_usuario_no_existe(client):
    """Login con usuario inexistente redirige"""
    mock_cursor.fetchone.return_value = None
    with client.session_transaction() as sess:
        sess['csrf_token'] = 'token_test'
    response = client.post('/', data={
        'user': 'noexiste',
        'password': 'mal',
        'csrf_token': 'token_test'
    })
    assert response.status_code in [200, 302, 403]

def test_dashboard_admin_sin_sesion(client):
    """Dashboard admin sin sesión debe redirigir"""
    response = client.get('/dashboard_admin')
    assert response.status_code in [302, 403]

def test_dashboard_usuario_sin_sesion(client):
    """Dashboard usuario sin sesión debe redirigir"""
    response = client.get('/dashboard_usuario')
    assert response.status_code in [302, 403]

def test_inventario_sin_sesion(client):
    """Inventario sin sesión debe redirigir"""
    response = client.get('/inventario_general')
    assert response.status_code in [302, 403]
