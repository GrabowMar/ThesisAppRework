import React from 'react';
import { ExclamationTriangleIcon, XCircleIcon } from '@heroicons/react/24/outline';

/**
 * ErrorMessage - Inline error display
 * Usage: <ErrorMessage message="Something went wrong" />
 */
export function ErrorMessage({ message, onRetry, className = '' }) {
  return (
    <div className={`alert-error ${className}`}>
      <XCircleIcon className="h-5 w-5 flex-shrink-0" />
      <div className="flex-1">
        <p className="text-sm font-medium">{message}</p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-sm font-medium text-red-800 hover:text-red-900 underline"
        >
          Retry
        </button>
      )}
    </div>
  );
}

/**
 * EmptyState - Display when no data is available
 * Usage: <EmptyState title="No items" message="Add your first item" action={<Button>Add</Button>} />
 */
export function EmptyState({ title, message, icon: Icon = ExclamationTriangleIcon, action }) {
  return (
    <div className="text-center py-12 px-4">
      <Icon className="mx-auto h-12 w-12 text-gray-400" />
      <h3 className="mt-4 text-lg font-medium text-gray-900">{title}</h3>
      {message && <p className="mt-2 text-sm text-gray-500">{message}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

/**
 * ErrorBoundary - Catch and display React errors
 * Usage: <ErrorBoundary><App /></ErrorBoundary>
 */
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
          <div className="text-center">
            <XCircleIcon className="mx-auto h-16 w-16 text-red-500" />
            <h1 className="mt-4 text-2xl font-bold text-gray-900">Something went wrong</h1>
            <p className="mt-2 text-gray-600">Please refresh the page and try again.</p>
            <button
              onClick={() => window.location.reload()}
              className="mt-6 btn-primary"
            >
              Refresh Page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorMessage;
