# React Frontend Integration Guide

This document provides examples of how to integrate your React frontend with this Flask backend.

## Prerequisites

1. The Flask backend should be running (typically on `http://localhost:5000`)
2. Ensure CORS is properly configured in the backend's `.env` file with your React app's URL

## Basic Setup in React

### Using Fetch API

```javascript
// src/services/api.js
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

export const apiService = {
  // Health check
  async checkHealth() {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) {
      throw new Error('Health check failed');
    }
    return response.json();
  },

  // GET request with parameters
  async sayHello(name) {
    const response = await fetch(`${API_BASE_URL}/hello?name=${encodeURIComponent(name)}`);
    if (!response.ok) {
      throw new Error('Failed to fetch greeting');
    }
    return response.json();
  },

  // POST request with JSON data
  async sendData(data) {
    const response = await fetch(`${API_BASE_URL}/data`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      throw new Error('Failed to send data');
    }
    return response.json();
  },

  // GET request with path parameter
  async getUser(userId) {
    const response = await fetch(`${API_BASE_URL}/user/${userId}`);
    if (!response.ok) {
      throw new Error('Failed to fetch user');
    }
    return response.json();
  },
};
```

### Using Axios

First, install axios:
```bash
npm install axios
```

Then create an API service:

```javascript
// src/services/api.js
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const apiService = {
  // Health check
  checkHealth: () => apiClient.get('/health'),

  // GET request with parameters
  sayHello: (name) => apiClient.get('/hello', { params: { name } }),

  // POST request with JSON data
  sendData: (data) => apiClient.post('/data', data),

  // GET request with path parameter
  getUser: (userId) => apiClient.get(`/user/${userId}`),
};
```

## Example React Components

### Simple Component Using Hooks

```javascript
// src/components/HelloComponent.jsx
import React, { useState, useEffect } from 'react';
import { apiService } from '../services/api';

function HelloComponent() {
  const [name, setName] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchGreeting = async () => {
    if (!name) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const data = await apiService.sayHello(name);
      setMessage(data.message);
    } catch (err) {
      setError('Failed to fetch greeting: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Hello Example</h2>
      <input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Enter your name"
      />
      <button onClick={fetchGreeting} disabled={loading}>
        {loading ? 'Loading...' : 'Say Hello'}
      </button>
      
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {message && <p style={{ color: 'green' }}>{message}</p>}
    </div>
  );
}

export default HelloComponent;
```

### Component with POST Request

```javascript
// src/components/DataFormComponent.jsx
import React, { useState } from 'react';
import { apiService } from '../services/api';

function DataFormComponent() {
  const [formData, setFormData] = useState({ key: '', value: '' });
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    
    try {
      const data = await apiService.sendData(formData);
      setResponse(data);
    } catch (err) {
      setError('Failed to send data: ' + err.message);
    }
  };

  return (
    <div>
      <h2>Send Data Example</h2>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={formData.key}
          onChange={(e) => setFormData({ ...formData, key: e.target.value })}
          placeholder="Key"
          required
        />
        <input
          type="text"
          value={formData.value}
          onChange={(e) => setFormData({ ...formData, value: e.target.value })}
          placeholder="Value"
          required
        />
        <button type="submit">Send Data</button>
      </form>
      
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {response && (
        <div>
          <h3>Response:</h3>
          <pre>{JSON.stringify(response, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

export default DataFormComponent;
```

### Health Check Component

```javascript
// src/components/HealthCheck.jsx
import React, { useState, useEffect } from 'react';
import { apiService } from '../services/api';

function HealthCheck() {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const data = await apiService.checkHealth();
        setHealth(data);
      } catch (err) {
        setError('Backend is not available');
      }
    };

    checkHealth();
    // Check health every 30 seconds
    const interval = setInterval(checkHealth, 30000);
    
    return () => clearInterval(interval);
  }, []);

  if (error) {
    return <div style={{ color: 'red' }}>⚠️ {error}</div>;
  }

  if (!health) {
    return <div>Checking backend status...</div>;
  }

  return (
    <div style={{ color: 'green' }}>
      ✅ Backend is {health.status}
    </div>
  );
}

export default HealthCheck;
```

## Environment Variables

Create a `.env` file in your React project root:

```env
REACT_APP_API_URL=http://localhost:5000/api
```

For production, update this to your production backend URL.

## Error Handling Best Practices

```javascript
// src/utils/errorHandler.js
export const handleApiError = (error) => {
  if (error.response) {
    // Server responded with error status
    console.error('API Error:', error.response.data);
    return error.response.data.error || 'An error occurred';
  } else if (error.request) {
    // Request made but no response
    console.error('Network Error:', error.request);
    return 'Network error: Please check your connection';
  } else {
    // Something else happened
    console.error('Error:', error.message);
    return error.message;
  }
};
```

## CORS Configuration

If you encounter CORS errors:

1. Make sure the Flask backend is running
2. Check that your React app's URL is in the backend's `CORS_ORIGINS` environment variable
3. For development with Create React App on `http://localhost:3000`, the default configuration should work
4. For Vite apps on `http://localhost:5173`, the default configuration should also work

## Production Deployment

When deploying to production:

1. Update `REACT_APP_API_URL` to your production backend URL
2. Update the backend's `CORS_ORIGINS` to include your production frontend URL
3. Ensure both frontend and backend are using HTTPS in production
4. Consider implementing authentication tokens for secure API access

## Testing

You can test the backend connection in your browser's console:

```javascript
// Test in browser console
fetch('http://localhost:5000/api/health')
  .then(res => res.json())
  .then(data => console.log(data))
  .catch(err => console.error(err));
```

## Next Steps

1. Implement authentication (JWT tokens recommended)
2. Add proper error boundaries in React
3. Implement loading states and user feedback
4. Add request caching if needed
5. Consider using React Query or SWR for better data fetching
