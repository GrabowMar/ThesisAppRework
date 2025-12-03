import React from 'react';

export function Spinner({ size = 'md' }) {
  const sizes = { sm: 'h-4 w-4', md: 'h-8 w-8', lg: 'h-12 w-12' };
  return (
    <div className="flex justify-center items-center p-4">
      <div className={`${sizes[size]} animate-spin rounded-full border-2 border-gray-300 border-t-blue-600`} />
    </div>
  );
}
