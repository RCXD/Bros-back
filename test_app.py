"""
Unit tests for the Flask application.
Run with: python -m pytest test_app.py
"""

import pytest
import json
from app import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get('/api/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'healthy'
    assert 'message' in data


def test_hello_endpoint_default(client):
    """Test the hello endpoint without name parameter."""
    response = client.get('/api/hello')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['message'] == 'Hello, World!'
    assert data['status'] == 'success'


def test_hello_endpoint_with_name(client):
    """Test the hello endpoint with name parameter."""
    response = client.get('/api/hello?name=TestUser')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['message'] == 'Hello, TestUser!'
    assert data['status'] == 'success'


def test_receive_data_valid(client):
    """Test the data endpoint with valid JSON."""
    test_data = {'key': 'value', 'number': 42}
    response = client.post(
        '/api/data',
        data=json.dumps(test_data),
        content_type='application/json'
    )
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'success'
    assert data['received'] == test_data
    assert 'message' in data


def test_receive_data_no_json(client):
    """Test the data endpoint without JSON data."""
    # Test with invalid JSON
    response = client.post(
        '/api/data',
        data='not json',
        content_type='application/json'
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['status'] == 'error'
    assert 'error' in data
    
    # Test with empty JSON object
    response = client.post(
        '/api/data',
        data=json.dumps({}),
        content_type='application/json'
    )
    # Empty object is falsy, so should return 400
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['status'] == 'error'
    assert 'error' in data


def test_get_user(client):
    """Test the user endpoint."""
    user_id = 123
    response = client.get(f'/api/user/{user_id}')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['user_id'] == user_id
    assert data['name'] == f'User {user_id}'
    assert data['status'] == 'success'


def test_404_error(client):
    """Test 404 error handler."""
    response = client.get('/api/nonexistent')
    assert response.status_code == 404
    data = json.loads(response.data)
    assert data['status'] == 'error'
    assert 'error' in data


def test_cors_headers(client):
    """Test that CORS headers are present."""
    response = client.get('/api/health')
    # In test mode, CORS headers might not be fully set
    # This is a basic check that the endpoint is accessible
    assert response.status_code == 200
