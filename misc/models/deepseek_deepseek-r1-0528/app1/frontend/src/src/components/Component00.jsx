axios.post('http://localhost:6261/api/login', 
  { username: 'test', password: 'password' },
  { withCredentials: true }
)