import React from 'react';

/**
 * Spinner - Loading indicator component
 * Usage: <Spinner /> or <Spinner size="lg" />
 */
export function Spinner({ size = 'md', className = '' }) {
  const sizeClasses = {
    sm: 'h-4 w-4 border-2',
    md: 'h-8 w-8 border-2',
    lg: 'h-12 w-12 border-3',
  };

  return (
    <div
      className={`animate-spin rounded-full border-blue-600 border-t-transparent ${sizeClasses[size]} ${className}`}
      role="status"
      aria-label="Loading"
    >
      <span className="sr-only">Loading...</span>
    </div>
  );
}

/**
 * LoadingScreen - Full-page loading state
 * Usage: <LoadingScreen message="Loading data..." />
 */
export function LoadingScreen({ message = 'Loading...' }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[200px] py-12">
      <Spinner size="lg" />
      <p className="mt-4 text-gray-600 animate-pulse">{message}</p>
    </div>
  );
}

export default Spinner;
