// Minimal React Application Scaffolding
// This is a barebones working React app that does nothing by default

import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import axios from 'axios';
import './App.css';

const App = () => {
  const [message, setMessage] = useState('Loading...');
  const [error, setError] = useState(null);

  useEffect(() => {
    // Fetch health check from backend
    axios.get('/health')
      .then(response => {
        setMessage(response.data.message || 'Backend connected successfully');
      })
      .catch(err => {
        setError('Failed to connect to backend');
        console.error('Backend connection error:', err);
      });
  }, []);

  return (
    <div className="app-container">
      <header>
        <h1>React + Flask App</h1>
      </header>
      <main>
        {error ? (
          <p className="error">{error}</p>
        ) : (
          <p className="success">{message}</p>
        )}
      </main>
    </div>
  );
};

// Mount React app
const container = document.getElementById('root');
if (container) {
  const root = ReactDOM.createRoot(container);
  root.render(<App />);
}

export default App;
