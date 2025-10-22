"""
Flask Backend Application for Bros
This backend is designed to work with a React frontend in a separate repository.
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from config import Config
import os

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Configure CORS to allow requests from React frontend
CORS(app, resources={
    r"/api/*": {
        "origins": app.config['CORS_ORIGINS'],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})


# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint to verify the API is running."""
    return jsonify({
        'status': 'healthy',
        'message': 'Bros Backend API is running'
    }), 200


# Example API endpoint
@app.route('/api/hello', methods=['GET'])
def hello():
    """Example endpoint that returns a greeting."""
    name = request.args.get('name', 'World')
    return jsonify({
        'message': f'Hello, {name}!',
        'status': 'success'
    }), 200


# Example POST endpoint
@app.route('/api/data', methods=['POST'])
def receive_data():
    """Example endpoint that receives and echoes back JSON data."""
    data = request.get_json()
    
    if not data:
        return jsonify({
            'error': 'No data provided',
            'status': 'error'
        }), 400
    
    return jsonify({
        'received': data,
        'message': 'Data received successfully',
        'status': 'success'
    }), 200


# Example GET endpoint with path parameter
@app.route('/api/user/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Example endpoint that returns user information."""
    # In a real application, this would fetch from a database
    return jsonify({
        'user_id': user_id,
        'name': f'User {user_id}',
        'status': 'success'
    }), 200


# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({
        'error': 'Resource not found',
        'status': 'error'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify({
        'error': 'Internal server error',
        'status': 'error'
    }), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"Starting Flask server on port {port}...")
    print(f"Debug mode: {debug}")
    print(f"CORS enabled for origins: {app.config['CORS_ORIGINS']}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
