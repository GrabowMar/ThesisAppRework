import React, { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from './AuthContext';
import {
  UserIcon,
  LockClosedIcon,
  EnvelopeIcon,
  ArrowRightOnRectangleIcon,
  EyeIcon,
  EyeSlashIcon,
  KeyIcon
} from '@heroicons/react/24/outline';

/**
 * LoginPage - Combined login/register page with tabs
 * Features: Login, Register, Forgot Password
 */
export function LoginPage() {
  const [activeTab, setActiveTab] = useState('login');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [resetToken, setResetToken] = useState('');
  
  // Form state
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: ''
  });
  const [errors, setErrors] = useState({});

  const { login, register, requestPasswordReset, resetPassword } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || '/';

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setErrors(prev => ({ ...prev, [name]: '' }));
  };

  const validate = () => {
    const newErrors = {};
    
    if (activeTab === 'login') {
      if (!formData.username) newErrors.username = 'Username or email is required';
      if (!formData.password) newErrors.password = 'Password is required';
    } else if (activeTab === 'register') {
      if (!formData.username || formData.username.length < 3) {
        newErrors.username = 'Username must be at least 3 characters';
      }
      if (!formData.email || !formData.email.includes('@')) {
        newErrors.email = 'Valid email is required';
      }
      if (!formData.password || formData.password.length < 8) {
        newErrors.password = 'Password must be at least 8 characters';
      }
      if (formData.password !== formData.confirmPassword) {
        newErrors.confirmPassword = 'Passwords do not match';
      }
    } else if (activeTab === 'forgot') {
      if (!formData.email || !formData.email.includes('@')) {
        newErrors.email = 'Valid email is required';
      }
    } else if (activeTab === 'reset') {
      if (!resetToken) newErrors.token = 'Reset token is required';
      if (!formData.password || formData.password.length < 8) {
        newErrors.password = 'Password must be at least 8 characters';
      }
      if (formData.password !== formData.confirmPassword) {
        newErrors.confirmPassword = 'Passwords do not match';
      }
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;
    
    setLoading(true);
    let result;
    
    try {
      if (activeTab === 'login') {
        result = await login(formData.username, formData.password);
        if (result.success) navigate(from, { replace: true });
      } else if (activeTab === 'register') {
        result = await register(formData.username, formData.email, formData.password);
        if (result.success) navigate(from, { replace: true });
      } else if (activeTab === 'forgot') {
        result = await requestPasswordReset(formData.email);
        if (result.success && result.resetToken) {
          // For demo purposes, auto-fill the token
          setResetToken(result.resetToken);
          setActiveTab('reset');
        }
      } else if (activeTab === 'reset') {
        result = await resetPassword(resetToken, formData.password);
        if (result.success) {
          setActiveTab('login');
          setFormData({ ...formData, password: '' });
        }
      }
    } finally {
      setLoading(false);
    }
  };

  const tabClass = (tab) =>
    `flex-1 py-3 text-center font-medium transition-colors ${
      activeTab === tab
        ? 'text-blue-600 border-b-2 border-blue-600'
        : 'text-gray-500 hover:text-gray-700'
    }`;

  const inputClass = (error) =>
    `w-full pl-10 pr-10 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors ${
      error ? 'border-red-500 bg-red-50' : 'border-gray-300'
    }`;

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo/Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-r from-blue-600 to-indigo-600 text-white mb-4">
            <LockClosedIcon className="w-8 h-8" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">
            {activeTab === 'login' && 'Welcome Back'}
            {activeTab === 'register' && 'Create Account'}
            {activeTab === 'forgot' && 'Forgot Password'}
            {activeTab === 'reset' && 'Reset Password'}
          </h1>
          <p className="text-gray-600 mt-1">
            {activeTab === 'login' && 'Sign in to continue'}
            {activeTab === 'register' && 'Join us today'}
            {activeTab === 'forgot' && 'We\'ll send you a reset link'}
            {activeTab === 'reset' && 'Enter your new password'}
          </p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-xl overflow-hidden">
          {/* Tabs */}
          {(activeTab === 'login' || activeTab === 'register') && (
            <div className="flex border-b border-gray-200">
              <button
                type="button"
                className={tabClass('login')}
                onClick={() => setActiveTab('login')}
              >
                Sign In
              </button>
              <button
                type="button"
                className={tabClass('register')}
                onClick={() => setActiveTab('register')}
              >
                Sign Up
              </button>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="p-6 space-y-4">
            {/* Username (login/register) */}
            {(activeTab === 'login' || activeTab === 'register') && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {activeTab === 'login' ? 'Username or Email' : 'Username'}
                </label>
                <div className="relative">
                  <UserIcon className="absolute left-3 top-3.5 h-5 w-5 text-gray-400" />
                  <input
                    type="text"
                    name="username"
                    value={formData.username}
                    onChange={handleChange}
                    placeholder={activeTab === 'login' ? 'Enter username or email' : 'Choose a username'}
                    className={inputClass(errors.username)}
                    autoComplete={activeTab === 'login' ? 'username' : 'off'}
                  />
                </div>
                {errors.username && (
                  <p className="text-red-500 text-sm mt-1">{errors.username}</p>
                )}
              </div>
            )}

            {/* Email (register/forgot) */}
            {(activeTab === 'register' || activeTab === 'forgot') && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email
                </label>
                <div className="relative">
                  <EnvelopeIcon className="absolute left-3 top-3.5 h-5 w-5 text-gray-400" />
                  <input
                    type="email"
                    name="email"
                    value={formData.email}
                    onChange={handleChange}
                    placeholder="Enter your email"
                    className={inputClass(errors.email)}
                    autoComplete="email"
                  />
                </div>
                {errors.email && (
                  <p className="text-red-500 text-sm mt-1">{errors.email}</p>
                )}
              </div>
            )}

            {/* Reset Token (reset) */}
            {activeTab === 'reset' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Reset Token
                </label>
                <div className="relative">
                  <KeyIcon className="absolute left-3 top-3.5 h-5 w-5 text-gray-400" />
                  <input
                    type="text"
                    value={resetToken}
                    onChange={(e) => setResetToken(e.target.value)}
                    placeholder="Paste your reset token"
                    className={inputClass(errors.token)}
                  />
                </div>
                {errors.token && (
                  <p className="text-red-500 text-sm mt-1">{errors.token}</p>
                )}
              </div>
            )}

            {/* Password (login/register/reset) */}
            {activeTab !== 'forgot' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {activeTab === 'reset' ? 'New Password' : 'Password'}
                </label>
                <div className="relative">
                  <LockClosedIcon className="absolute left-3 top-3.5 h-5 w-5 text-gray-400" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    name="password"
                    value={formData.password}
                    onChange={handleChange}
                    placeholder={activeTab === 'reset' ? 'Enter new password' : 'Enter your password'}
                    className={inputClass(errors.password)}
                    autoComplete={activeTab === 'login' ? 'current-password' : 'new-password'}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-3.5 text-gray-400 hover:text-gray-600"
                  >
                    {showPassword ? (
                      <EyeSlashIcon className="h-5 w-5" />
                    ) : (
                      <EyeIcon className="h-5 w-5" />
                    )}
                  </button>
                </div>
                {errors.password && (
                  <p className="text-red-500 text-sm mt-1">{errors.password}</p>
                )}
              </div>
            )}

            {/* Confirm Password (register/reset) */}
            {(activeTab === 'register' || activeTab === 'reset') && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Confirm Password
                </label>
                <div className="relative">
                  <LockClosedIcon className="absolute left-3 top-3.5 h-5 w-5 text-gray-400" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    name="confirmPassword"
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    placeholder="Confirm your password"
                    className={inputClass(errors.confirmPassword)}
                    autoComplete="new-password"
                  />
                </div>
                {errors.confirmPassword && (
                  <p className="text-red-500 text-sm mt-1">{errors.confirmPassword}</p>
                )}
              </div>
            )}

            {/* Forgot Password Link (login only) */}
            {activeTab === 'login' && (
              <div className="text-right">
                <button
                  type="button"
                  onClick={() => setActiveTab('forgot')}
                  className="text-sm text-blue-600 hover:text-blue-700"
                >
                  Forgot password?
                </button>
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-medium rounded-lg hover:from-blue-700 hover:to-indigo-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <ArrowRightOnRectangleIcon className="w-5 h-5" />
                  {activeTab === 'login' && 'Sign In'}
                  {activeTab === 'register' && 'Create Account'}
                  {activeTab === 'forgot' && 'Send Reset Link'}
                  {activeTab === 'reset' && 'Reset Password'}
                </>
              )}
            </button>

            {/* Back to Login (forgot/reset) */}
            {(activeTab === 'forgot' || activeTab === 'reset') && (
              <button
                type="button"
                onClick={() => setActiveTab('login')}
                className="w-full py-2 text-gray-600 hover:text-gray-800 text-sm"
              >
                ← Back to Sign In
              </button>
            )}
          </form>

          {/* Demo Credentials Notice */}
          {activeTab === 'login' && (
            <div className="px-6 pb-6">
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
                <p className="text-sm text-amber-800">
                  <strong>Demo:</strong> Login with <code className="bg-amber-100 px-1 rounded">admin</code> / <code className="bg-amber-100 px-1 rounded">admin123</code>
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Footer Link */}
        <p className="text-center text-gray-600 mt-6">
          <Link to="/" className="text-blue-600 hover:text-blue-700">
            ← Back to App
          </Link>
        </p>
      </div>
    </div>
  );
}

export default LoginPage;
