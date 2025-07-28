# Comprehensive Frontend Login Application

Here's a complete implementation of a React-based authentication system with Vite, including user registration, login, protected dashboard, and client-side routing.

## Project Structure

```
login-app/
├── package.json
├── index.html
├── src/
│   ├── App.jsx
│   └── App.css
```

## 1. package.json

```json
{
  "name": "login-app",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "axios": "^1.6.7",
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.56",
    "@types/react-dom": "^18.2.19",
    "@vitejs/plugin-react": "^4.2.1",
    "vite": "^5.0.8"
  }
}
```

## 2. index.html

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>React Auth App</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/App.jsx"></script>
  </body>
</html>
```

## 3. src/App.jsx

```jsx
import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import axios from 'axios';
import './App.css';

// Set axios defaults to include credentials and proper headers
axios.defaults.withCredentials = true;
axios.defaults.baseURL = 'http://localhost:5505';

const App = () => {
  // Application state
  const [currentUser, setCurrentUser] = useState(null);
  const [currentView, setCurrentView] = useState('login'); // 'login', 'register', 'dashboard'
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: ''
  });

  // Check if user is already authenticated on initial load
  useEffect(() => {
    const checkAuthStatus = async () => {
      setIsLoading(true);
      try {
        const response = await axios.get('/api/dashboard');
        if (response.data && response.data.user) {
          setCurrentUser(response.data.user);
          setCurrentView('dashboard');
        }
      } catch (err) {
        // Not logged in - stay on login page
        setCurrentView('login');
      } finally {
        setIsLoading(false);
      }
    };

    checkAuthStatus();
  }, []);

  // Handle form input changes
  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  // Handle user registration
  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      // Basic validation
      if (!formData.username || !formData.email || !formData.password) {
        throw new Error('All fields are required');
      }
      if (formData.password.length < 6) {
        throw new Error('Password must be at least 6 characters');
      }

      const response = await axios.post('/api/register', formData);
      if (response.data.success) {
        setCurrentUser(response.data.user);
        setCurrentView('dashboard');
      }
    } catch (err) {
      setError(err.response?.data?.message || err.message || 'Registration failed');
    } finally {
      setIsLoading(false);
    }
  };

  // Handle user login
  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      // Basic validation
      if (!formData.email || !formData.password) {
        throw new Error('Email and password are required');
      }

      const response = await axios.post('/api/login', {
        email: formData.email,
        password: formData.password
      });
      if (response.data.success) {
        setCurrentUser(response.data.user);
        setCurrentView('dashboard');
      }
    } catch (err) {
      setError(err.response?.data?.message || err.message || 'Login failed');
    } finally {
      setIsLoading(false);
    }
  };

  // Handle user logout
  const handleLogout = async () => {
    setIsLoading(true);
    try {
      await axios.post('/api/logout');
      setCurrentUser(null);
      setCurrentView('login');
      setFormData({
        username: '',
        email: '',
        password: ''
      });
    } catch (err) {
      setError(err.response?.data?.message || err.message || 'Logout failed');
    } finally {
      setIsLoading(false);
    }
  };

  // Render loading state
  if (isLoading) {
    return (
      <div className="container">
        <div className="loading">Loading...</div>
      </div>
    );
  }

  // Render the appropriate view based on current state
  return (
    <div className="container">
      {/* Error display */}
      {error && <div className="error">{error}</div>}

      {/* Login View */}
      {currentView === 'login' && (
        <div className="auth-form">
          <h2>Login</h2>
          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label>Email</label>
              <input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleInputChange}
                required
              />
            </div>
            <div className="form-group">
              <label>Password</label>
              <input
                type="password"
                name="password"
                value={formData.password}
                onChange={handleInputChange}
                required
              />
            </div>
            <button type="submit" className="btn">
              Login
            </button>
          </form>
          <p>
            Don't have an account?{' '}
            <button className="link" onClick={() => setCurrentView('register')}>
              Register
            </button>
          </p>
        </div>
      )}

      {/* Registration View */}
      {currentView === 'register' && (
        <div className="auth-form">
          <h2>Register</h2>
          <form onSubmit={handleRegister}>
            <div className="form-group">
              <label>Username</label>
              <input
                type="text"
                name="username"
                value={formData.username}
                onChange={handleInputChange}
                required
              />
            </div>
            <div className="form-group">
              <label>Email</label>
              <input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleInputChange}
                required
              />
            </div>
            <div className="form-group">
              <label>Password (min 6 characters)</label>
              <input
                type="password"
                name="password"
                value={formData.password}
                onChange={handleInputChange}
                required
                minLength="6"
              />
            </div>
            <button type="submit" className="btn">
              Register
            </button>
          </form>
          <p>
            Already have an account?{' '}
            <button className="link" onClick={() => setCurrentView('login')}>
              Login
            </button>
          </p>
        </div>
      )}

      {/* Dashboard View (Protected) */}
      {currentView === 'dashboard' && currentUser && (
        <div className="dashboard">
          <h2>Welcome, {currentUser.username}!</h2>
          <p>You are now logged in to your account.</p>
          <button onClick={handleLogout} className="btn logout">
            Logout
          </button>
        </div>
      )}
    </div>
  );
};

// Mount the app
const container = document.getElementById('root');
if (container) {
  const root = ReactDOM.createRoot(container);
  root.render(<App />);
}

export default App;
```

## 4. src/App.css

```css
/* Base Styles */
:root {
  --primary-color: #3498db;
  --secondary-color: #2980b9;
  --error-color: #e74c3c;
  --text-color: #333;
  --light-gray: #f5f5f5;
  --border-color: #ddd;
}

body {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  line-height: 1.6;
  color: var(--text-color);
  background-color: #f9f9f9;
  margin: 0;
  padding: 0;
}

.container {
  max-width: 400px;
  margin: 50px auto;
  padding: 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

/* Loading State */
.loading {
  text-align: center;
  padding: 20px;
  font-size: 18px;
}

/* Error Messages */
.error {
  background-color: #fdecea;
  color: var(--error-color);
  padding: 10px 15px;
  border-radius: 4px;
  margin-bottom: 20px;
  border-left: 4px solid var(--error-color);
}

/* Form Styles */
.auth-form {
  padding: 20px;
}

.auth-form h2 {
  margin-top: 0;
  color: var(--primary-color);
  text-align: center;
}

.form-group {
  margin-bottom: 15px;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: 600;
}

.form-group input {
  width: 100%;
  padding: 10px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  font-size: 16px;
}

.form-group input:focus {
  border-color: var(--primary-color);
  outline: none;
  box-shadow: 0 0 0 2px rgba(52, 152, 219, 0.2);
}

/* Button Styles */
.btn {
  background-color: var(--primary-color);
  color: white;
  border: none;
  padding: 10px 15px;
  font-size: 16px;
  border-radius: 4px;
  cursor: pointer;
  width: 100%;
  margin-top: 10px;
}

.btn:hover {
  background-color: var(--secondary-color);
}

.btn.logout {
  background-color: #e74c3c;
}

.btn.logout:hover {
  background-color: #c0392b;
}

.link {
  background: none;
  border: none;
  color: var(--primary-color);
  cursor: pointer;
  padding: 0;
  text-decoration: underline;
}

.link:hover {
  color: var(--secondary-color);
}

/* Dashboard Styles */
.dashboard {
  text-align: center;
  padding: 20px;
}

.dashboard h2 {
  color: var(--primary-color);
}
```

## Setup and Usage Instructions

### Installation

1. Create a new Vite project with React template:
   ```bash
   npm create vite@latest login-app --template react
   cd login-app
   ```

2. Install the required dependencies:
   ```bash
   npm install axios
   ```

3. Replace the default files with the ones provided above.

### Development

1. Start the development server:
   ```bash
   npm run dev
   ```

2. The application will be available at `http://localhost:5173` by default. If you need to use port 5505, modify the `vite.config.js`:
   ```javascript
   export default defineConfig({
     plugins: [react()],
     server: {
       port: 5505
     }
   });
   ```

### Features Implemented

1. **User Registration**:
   - Form with username, email, and password fields
   - Client-side validation for required fields and password length
   - Error handling with user-friendly messages

2. **User Login**:
   - Form with email and password fields
   - Basic validation for required fields
   - Error handling for failed login attempts

3. **Protected Dashboard**:
   - Displays welcome message with username
   - Includes logout button
   - Automatically checks auth status on load
   - Redirects unauthenticated users to login

4. **Client-Side Routing**:
   - Conditional rendering of views based on state
   - Smooth transitions between login, register, and dashboard views

### Error Handling

The implementation includes comprehensive error handling for:
- Empty form submissions
- Invalid credentials
- Network errors
- Server-side validation failures
- Session expiration

### Security Considerations

1. Axios is configured to:
   - Send credentials with requests (for session cookies)
   - Use a base URL for API endpoints

2. Password fields:
   - Minimum length requirement (6 characters)
   - Input type set to "password"

3. Session management:
   - Automatically checks auth status on page load
   - Clears user data on logout

### Responsive Design

The CSS includes:
- Mobile-friendly layout
- Clear visual feedback for form interactions
- Consistent styling across all components
- Accessibility considerations (focus states, proper labeling)