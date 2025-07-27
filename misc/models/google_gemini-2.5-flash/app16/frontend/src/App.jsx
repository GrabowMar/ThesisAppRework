import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom/client';

const App = () => {
  const [message, setMessage] = useState('Loading...');

  useEffect(() => {
    // Fetch the message from the backend server running on port 5941
    fetch('http://localhost:5941')
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
      })
      .then((data) => {
        setMessage(data.message || 'No message received');
      })
      .catch((error) => {
        setMessage(`Error fetching message: ${error.message}`);
      });
  }, []);

  return (
    <main>
      <h1>{message}</h1>
    </main>
  );
};

const container = document.getElementById('root');
if (container) {
  const root = ReactDOM.createRoot(container);
  root.render(<App />);
}

export default App;
