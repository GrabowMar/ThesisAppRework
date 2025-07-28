import axios from 'axios';

// Configure axios to send credentials with all requests
axios.defaults.withCredentials = true;

// Example registration
async function register(username, email, password) {
  try {
    const response = await axios.post('http://localhost:6191/api/register', {
      username,
      email,
      password
    });
    return response.data;
  } catch (error) {
    throw error.response.data;
  }
}

// Example login
async function login(email, password) {
  try {
    const response = await axios.post('http://localhost:6191/api/login', {
      email,
      password
    });
    return response.data;
  } catch (error) {
    throw error.response.data;
  }
}

// Example protected request
async function getDashboardData() {
  try {
    const response = await axios.get('http://localhost:6191/api/dashboard');
    return response.data;
  } catch (error) {
    throw error.response.data;
  }
}