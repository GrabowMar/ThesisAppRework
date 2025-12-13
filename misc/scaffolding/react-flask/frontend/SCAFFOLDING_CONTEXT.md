```markdown
# Frontend Blueprint Reference

## Stack & Environment
- React 18, Vite, Tailwind CSS, Axios
- Available libraries: react-hot-toast, @heroicons/react

## What You Can Generate

### Required Files
- **App.jsx**: Main application component

### Optional Additional Files (encouraged for complex apps)
- **App.css**: Custom styles (Tailwind is also available)
- **components/*.jsx**: Additional React components
- **hooks/*.js**: Custom React hooks
- **utils/*.js**: Utility functions
- **services/*.js**: API service modules

### Dependencies
- Mention any additional npm packages needed in your response
- Base packages pre-installed: React, axios, react-hot-toast, heroicons, tailwind

## Available Imports
```jsx
// Pre-installed components (in ./components):
import { Spinner, ErrorBoundary } from './components';

// From node_modules:
import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { 
  PlusIcon, TrashIcon, CheckIcon, XMarkIcon,
  PencilIcon, MagnifyingGlassIcon, ArrowPathIcon,
  PlayIcon, PauseIcon, StopIcon,
  ChevronUpIcon, ChevronDownIcon,
  ExclamationCircleIcon
} from '@heroicons/react/24/outline';
```

## Basic App Pattern
```jsx
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { Spinner } from './components';

const API_BASE = '/api/YOUR_RESOURCE';

function App() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchItems = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await axios.get(API_BASE);
      setItems(data.items || []);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to load');
      toast.error('Failed to load items');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Your UI here */}
    </div>
  );
}

export default App;
```

## File Upload Pattern
```jsx
const handleUpload = async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);

  try {
    const { data } = await axios.post('/api/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    toast.success('Upload successful!');
  } catch (err) {
    toast.error('Upload failed');
  }
};
```

## Audio/Media Player Pattern
```jsx
const audioRef = useRef(null);
const [isPlaying, setIsPlaying] = useState(false);
const [currentTime, setCurrentTime] = useState(0);
const [duration, setDuration] = useState(0);

const togglePlay = () => {
  if (audioRef.current.paused) {
    audioRef.current.play();
    setIsPlaying(true);
  } else {
    audioRef.current.pause();
    setIsPlaying(false);
  }
};

// JSX:
<audio
  ref={audioRef}
  src={currentTrack?.url}
  onTimeUpdate={(e) => setCurrentTime(e.target.currentTime)}
  onLoadedMetadata={(e) => setDuration(e.target.duration)}
  onEnded={() => setIsPlaying(false)}
/>
```

## Tailwind Quick Reference
- **Layout**: `flex`, `grid`, `justify-between`, `items-center`, `gap-{n}`
- **Spacing**: `p-{n}`, `m-{n}`, `py-{n}`, `px-{n}`
- **Colors**: `bg-blue-600`, `text-white`, `hover:bg-blue-700`
- **Effects**: `shadow-md`, `rounded-lg`, `transition`
- **Responsive**: `sm:`, `md:`, `lg:` prefixes

## Custom CSS (App.css)
You can add custom styles:
```css
.custom-player {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.track-item:hover {
  transform: translateX(4px);
  transition: transform 0.2s ease;
}
```

## Quality Expectations
- Implement ALL requirements from the specification
- Include loading states and error handling
- Use toast notifications for user feedback
- Make the UI responsive and accessible
- Generate complete, working code - no placeholders
```
