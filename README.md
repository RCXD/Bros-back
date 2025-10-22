# Bros-back

Flask backend API designed to work with a React frontend (stored in a separate repository).

## Features

- RESTful API with Flask
- CORS enabled for cross-origin requests from React frontend
- Environment-based configuration (development, production, testing)
- Example API endpoints demonstrating common patterns
- Health check endpoint for monitoring
- Error handling

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

## Setup

1. Clone the repository:
```bash
git clone https://github.com/RCXD/Bros-back.git
cd Bros-back
```

2. Create a virtual environment:
```bash
python -m venv venv
```

3. Activate the virtual environment:
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Create a `.env` file from the example:
```bash
cp .env.example .env
```

6. Edit `.env` and configure your settings (especially CORS_ORIGINS to match your React app URL).

## Running the Application

### Development Mode

```bash
python app.py
```

The server will start on `http://localhost:5000` by default.

### Production Mode

For production, it's recommended to use a production WSGI server like Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## API Endpoints

### Health Check
- **GET** `/api/health`
- Returns the health status of the API

### Hello Endpoint
- **GET** `/api/hello?name=YourName`
- Returns a greeting message
- Query parameter: `name` (optional, defaults to "World")

### Data Endpoint
- **POST** `/api/data`
- Receives JSON data and echoes it back
- Request body: JSON object

### User Endpoint
- **GET** `/api/user/<user_id>`
- Returns user information for the given user ID
- Path parameter: `user_id` (integer)

## Testing the API

You can test the API using curl:

```bash
# Health check
curl http://localhost:5000/api/health

# Hello endpoint
curl http://localhost:5000/api/hello?name=Developer

# Post data
curl -X POST http://localhost:5000/api/data \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}'

# Get user
curl http://localhost:5000/api/user/123
```

## Connecting to React Frontend

This backend is configured to accept requests from React frontends. The CORS configuration allows requests from:
- `http://localhost:3000` (Create React App default)
- `http://localhost:5173` (Vite default)

To connect from your React app:

```javascript
// Example fetch request from React
fetch('http://localhost:5000/api/hello?name=React')
  .then(response => response.json())
  .then(data => console.log(data))
  .catch(error => console.error('Error:', error));
```

### Important Notes for Production

1. Update `CORS_ORIGINS` in your `.env` file to include your production React app URL
2. Set a strong `SECRET_KEY` in production
3. Set `FLASK_DEBUG=False` in production
4. Use a production WSGI server (e.g., Gunicorn, uWSGI)
5. Consider using a reverse proxy (e.g., Nginx)
6. Implement proper authentication and authorization for protected endpoints

## Project Structure

```
Bros-back/
├── app.py              # Main Flask application
├── config.py           # Configuration settings
├── requirements.txt    # Python dependencies
├── .env.example        # Example environment variables
├── .env               # Your environment variables (not in git)
├── .gitignore         # Git ignore file
└── README.md          # This file
```

## Environment Variables

- `FLASK_DEBUG`: Enable/disable debug mode (True/False)
- `PORT`: Port number for the server (default: 5000)
- `SECRET_KEY`: Secret key for Flask sessions
- `CORS_ORIGINS`: Comma-separated list of allowed origins for CORS
- `DATABASE_URL`: Database connection string (for future use)

## Development

To add new endpoints, edit `app.py` and follow the existing patterns:

```python
@app.route('/api/your-endpoint', methods=['GET', 'POST'])
def your_endpoint():
    # Your logic here
    return jsonify({'status': 'success'}), 200
```

## License

[Add your license here]