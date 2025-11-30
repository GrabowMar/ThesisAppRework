import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import App from './App.jsx';
import './App.css';
import { 
  AuthProvider, 
  LoginPage, 
  AdminPanel, 
  ProtectedRoute, 
  PublicOnlyRoute,
  Layout 
} from './components';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <Toaster 
      position="top-right"
      toastOptions={{
        duration: 4000,
        style: {
          background: '#363636',
          color: '#fff',
        },
        success: {
          iconTheme: {
            primary: '#10b981',
            secondary: '#fff',
          },
        },
        error: {
          iconTheme: {
            primary: '#ef4444',
            secondary: '#fff',
          },
        },
      }}
    />
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Auth routes */}
          <Route path="/login" element={
            <PublicOnlyRoute>
              <LoginPage />
            </PublicOnlyRoute>
          } />
          
          {/* Admin panel (protected, admin only) */}
          <Route path="/admin" element={
            <ProtectedRoute requireAdmin>
              <Layout title="Admin Panel" subtitle="User Management">
                <AdminPanel />
              </Layout>
            </ProtectedRoute>
          } />
          
          {/* Main app route - AI generated content goes here */}
          <Route path="/*" element={<App />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);
