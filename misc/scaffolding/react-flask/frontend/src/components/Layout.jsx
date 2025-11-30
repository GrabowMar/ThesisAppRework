import React from 'react';

/**
 * Layout - Main app shell with gradient header and footer
 * Usage: <Layout title="My App" subtitle="Description" icon={<IconComponent />}>content</Layout>
 */
export function Layout({ children, title, subtitle, icon, actions }) {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Gradient Header */}
      <header className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {icon && <div className="h-10 w-10 flex-shrink-0">{icon}</div>}
              <div>
                {title && (
                  <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
                )}
                {subtitle && (
                  <p className="text-blue-100 text-sm">{subtitle}</p>
                )}
              </div>
            </div>
            {actions && <div className="flex items-center gap-3">{actions}</div>}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 py-4">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <p className="text-center text-sm text-gray-500">
            Powered by React + Flask • {new Date().getFullYear()}
          </p>
        </div>
      </footer>
    </div>
  );
}

/**
 * Card - Styled container for content sections
 * Usage: <Card title="Section Title" actions={<button>Add</button>}>content</Card>
 */
export function Card({ children, title, subtitle, actions, className = '' }) {
  return (
    <div className={`bg-white rounded-xl shadow-lg overflow-hidden ${className}`}>
      {(title || actions) && (
        <div className="px-6 py-4 border-b border-gray-100 bg-gray-50/50">
          <div className="flex items-center justify-between">
            <div>
              {title && <h2 className="text-lg font-semibold text-gray-900">{title}</h2>}
              {subtitle && <p className="text-sm text-gray-500">{subtitle}</p>}
            </div>
            {actions && <div className="flex items-center gap-2">{actions}</div>}
          </div>
        </div>
      )}
      <div className="p-6">{children}</div>
    </div>
  );
}

/**
 * PageHeader - Section header with title and optional actions
 */
export function PageHeader({ title, subtitle, actions, className = '' }) {
  return (
    <div className={`mb-6 ${className}`}>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">{title}</h2>
          {subtitle && <p className="mt-1 text-sm text-gray-500">{subtitle}</p>}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}

export default Layout;
