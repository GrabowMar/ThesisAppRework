// Login Page - Auth form with login/register toggle
import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { Spinner } from '../components';

function LoginPage() {
  const [isLogin, setIsLogin] = useState(true);
  const [formData, setFormData] = useState({ username: '', password: '', email: '', confirmPassword: '' });
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  
  const { login, register, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || '/';

  React.useEffect(() => {
    if (isAuthenticated) navigate(from, { replace: true });
  }, [isAuthenticated, navigate, from]);

  const handleChange = (e) => {
    setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }));
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      if (isLogin) {
        await login(formData.username, formData.password);
      } else {
        if (formData.password !== formData.confirmPassword) {
          setError('Passwords do not match');
          setSubmitting(false);
          return;
        }
        await register({ username: formData.username, password: formData.password, email: formData.email || undefined });
      }
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.response?.data?.error || 'Authentication failed');
    } finally {
      setSubmitting(false);
    }
  };

  const toggleMode = () => {
    setIsLogin(!isLogin);
    setError('');
    setFormData({ username: '', password: '', email: '', confirmPassword: '' });
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 py-12 px-4">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="text-center text-3xl font-extrabold text-gray-900">
            {isLogin ? 'Sign in' : 'Create account'}
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            <button type="button" onClick={toggleMode} className="font-medium text-blue-600 hover:text-blue-500">
              {isLogin ? 'Register here' : 'Sign in here'}
            </button>
          </p>
        </div>

        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="space-y-4">
            <input name="username" type="text" required value={formData.username} onChange={handleChange}
              className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="Username" />
            
            {!isLogin && (
              <input name="email" type="email" value={formData.email} onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="Email (optional)" />
            )}
            
            <input name="password" type="password" required value={formData.password} onChange={handleChange}
              className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="Password" />
            
            {!isLogin && (
              <input name="confirmPassword" type="password" required value={formData.confirmPassword} onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="Confirm Password" />
            )}
          </div>

          {error && <div className="bg-red-50 text-red-800 p-3 rounded-md text-sm">{error}</div>}

          <button type="submit" disabled={submitting}
            className="w-full py-2 px-4 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50">
            {submitting ? <Spinner size="sm" /> : (isLogin ? 'Sign in' : 'Create account')}
          </button>

          {isLogin && (
            <p className="text-center text-sm text-gray-500">
              Demo: <code className="bg-gray-100 px-1 rounded">admin</code> / <code className="bg-gray-100 px-1 rounded">admin2025</code>
            </p>
          )}
        </form>
      </div>
    </div>
  );
}

export default LoginPage;
