/**
 * Enhanced Login Component with Better Error Handling
 * 
 * This is an example of how to integrate the enhanced error handling
 * utilities into React components for the generated applications.
 * 
 * To use this in existing apps, replace the error handling sections
 * in App.jsx files with these patterns.
 */

import React, { useState, useCallback } from 'react';
import { ErrorHandler, FormHandler } from './errorHandling.js';

const EnhancedLoginComponent = () => {
  const [view, setView] = useState('login');
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});

  // Enhanced login API call with retry mechanism
  const loginApiCall = useCallback(
    ErrorHandler.createRetryHandler(async (formData) => {
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const error = new Error(errorData.message || 'Login failed');
        error.response = { status: response.status, data: errorData };
        throw error;
      }

      return response.json();
    }, 3, 1000),
    []
  );

  // Form validation
  const validateLoginForm = useCallback((form) => {
    const formData = new FormData(form);
    const email = formData.get('email')?.trim();
    const password = formData.get('password')?.trim();
    
    const fieldErrors = {};
    
    // Validate email
    const emailErrors = FormHandler.validateField('Email', email, {
      required: true,
      email: true
    });
    if (emailErrors.length > 0) {
      fieldErrors.email = emailErrors;
    }
    
    // Validate password
    const passwordErrors = FormHandler.validateField('Password', password, {
      required: true,
      minLength: 6
    });
    if (passwordErrors.length > 0) {
      fieldErrors.password = passwordErrors;
    }

    return {
      valid: Object.keys(fieldErrors).length === 0,
      errors: fieldErrors,
      data: { email, password }
    };
  }, []);

  // Enhanced login handler with better error handling
  const handleLogin = FormHandler.createSubmitHandler(
    async (e) => {
      const validation = validateLoginForm(e.target);
      const result = await loginApiCall(validation.data);
      return result;
    },
    {
      validateForm: validateLoginForm,
      clearErrors: () => setErrors({}),
      setLoading,
      setErrors,
      onSuccess: (result) => {
        setUser(result.user);
        setView('dashboard');
        
        // Show success notification
        ErrorHandler.showRetryNotification('Success', 0);
      },
      onError: (error) => {
        console.error('Login failed:', error);
        
        // Handle specific error types
        if (error.type === 'auth') {
          // Clear any stored tokens
          localStorage.removeItem('authToken');
        }
      }
    }
  );

  // Enhanced register handler
  const handleRegister = FormHandler.createSubmitHandler(
    async (e) => {
      const formData = new FormData(e.target);
      const data = {
        username: formData.get('username')?.trim(),
        email: formData.get('email')?.trim(),
        password: formData.get('password')?.trim(),
      };

      const response = await fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const error = new Error(errorData.message || 'Registration failed');
        error.response = { status: response.status, data: errorData };
        throw error;
      }

      return response.json();
    },
    {
      validateForm: (form) => {
        const formData = new FormData(form);
        const username = formData.get('username')?.trim();
        const email = formData.get('email')?.trim();
        const password = formData.get('password')?.trim();
        
        const fieldErrors = {};
        
        // Validate all fields
        ['username', 'email', 'password'].forEach(field => {
          const value = formData.get(field)?.trim();
          const rules = { required: true };
          
          if (field === 'email') rules.email = true;
          if (field === 'password') rules.password = true;
          
          const fieldErrs = FormHandler.validateField(
            field.charAt(0).toUpperCase() + field.slice(1), 
            value, 
            rules
          );
          
          if (fieldErrs.length > 0) {
            fieldErrors[field] = fieldErrs;
          }
        });

        return { valid: Object.keys(fieldErrors).length === 0, errors: fieldErrors };
      },
      clearErrors: () => setErrors({}),
      setLoading,
      setErrors,
      onSuccess: (result) => {
        setUser(result.user);
        setView('dashboard');
      }
    }
  );

  // Logout handler
  const handleLogout = useCallback(async () => {
    try {
      await fetch('/api/logout', { method: 'POST' });
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setUser(null);
      setView('login');
      localStorage.removeItem('authToken');
    }
  }, []);

  // Error display component
  const ErrorDisplay = ({ errors, field }) => {
    const fieldErrors = errors[field];
    if (!fieldErrors || fieldErrors.length === 0) return null;

    return (
      <div className="field-errors">
        {fieldErrors.map((error, index) => (
          <div key={index} className="error-message">
            {error}
          </div>
        ))}
      </div>
    );
  };

  // General error display
  const GeneralError = ({ errors }) => {
    if (!errors.general) return null;
    
    return (
      <div className="alert error" style={{ marginBottom: '1rem' }}>
        {errors.general}
      </div>
    );
  };

  // Login form
  const renderLogin = () => (
    <div className="auth-container">
      <h2>Login</h2>
      <GeneralError errors={errors} />
      
      <form onSubmit={handleLogin} noValidate>
        <div className="form-group">
          <label htmlFor="email">Email:</label>
          <input
            type="email"
            id="email"
            name="email"
            required
            className={errors.email ? 'is-invalid' : ''}
            disabled={loading}
          />
          <ErrorDisplay errors={errors} field="email" />
        </div>

        <div className="form-group">
          <label htmlFor="password">Password:</label>
          <input
            type="password"
            id="password"
            name="password"
            required
            className={errors.password ? 'is-invalid' : ''}
            disabled={loading}
          />
          <ErrorDisplay errors={errors} field="password" />
        </div>

        <button type="submit" disabled={loading} className="btn-primary">
          {loading ? (
            <>
              <span className="loading-spinner"></span>
              Logging in...
            </>
          ) : (
            'Login'
          )}
        </button>
      </form>

      <p>
        Don't have an account?{' '}
        <button onClick={() => setView('register')} className="link-button">
          Sign up
        </button>
      </p>
    </div>
  );

  // Register form (similar pattern)
  const renderRegister = () => (
    <div className="auth-container">
      <h2>Register</h2>
      <GeneralError errors={errors} />
      
      <form onSubmit={handleRegister} noValidate>
        <div className="form-group">
          <label htmlFor="username">Username:</label>
          <input
            type="text"
            id="username"
            name="username"
            required
            className={errors.username ? 'is-invalid' : ''}
            disabled={loading}
          />
          <ErrorDisplay errors={errors} field="username" />
        </div>

        <div className="form-group">
          <label htmlFor="email">Email:</label>
          <input
            type="email"
            id="email"
            name="email"
            required
            className={errors.email ? 'is-invalid' : ''}
            disabled={loading}
          />
          <ErrorDisplay errors={errors} field="email" />
        </div>

        <div className="form-group">
          <label htmlFor="password">Password:</label>
          <input
            type="password"
            id="password"
            name="password"
            required
            className={errors.password ? 'is-invalid' : ''}
            disabled={loading}
          />
          <ErrorDisplay errors={errors} field="password" />
        </div>

        <button type="submit" disabled={loading} className="btn-primary">
          {loading ? (
            <>
              <span className="loading-spinner"></span>
              Creating account...
            </>
          ) : (
            'Create Account'
          )}
        </button>
      </form>

      <p>
        Already have an account?{' '}
        <button onClick={() => setView('login')} className="link-button">
          Log in
        </button>
      </p>
    </div>
  );

  // Dashboard
  const renderDashboard = () => (
    <div className="dashboard">
      <h2>Welcome, {user?.username}!</h2>
      <p>You are successfully logged in.</p>
      <button onClick={handleLogout} className="btn-secondary">
        Logout
      </button>
    </div>
  );

  return (
    <div className="app">
      {!user && view === 'login' && renderLogin()}
      {!user && view === 'register' && renderRegister()}
      {user && renderDashboard()}
    </div>
  );
};

export default EnhancedLoginComponent;
