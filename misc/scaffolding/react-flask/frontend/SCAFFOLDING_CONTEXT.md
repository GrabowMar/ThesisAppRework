# Frontend Scaffolding Context

## Technical Stack
- **React 18** with Vite
- **Tailwind CSS 3.4** - full utility classes available
- **Heroicons** - `@heroicons/react/24/outline` and `/24/solid`
- **react-hot-toast** - pre-configured, just import `toast`
- **Axios** - HTTP client

## Architecture Rules (MUST FOLLOW)
1. `src/App.jsx` exports default functional component
2. API calls use relative paths (`/api/items`) - never hardcode localhost
3. Define `const API_URL = '';` at top of file
4. Use `toast.success()` / `toast.error()` for user feedback

## Available Utilities

### Helper Components (optional - use or build your own)
```jsx
import { Spinner, EmptyState } from './components';
```
- `<Spinner size="sm|md|lg" />` - loading spinner
- `<EmptyState title="" message="" />` - empty state display

### CSS Utility Classes (defined in App.css)
```
Buttons: btn-primary, btn-secondary, btn-danger, btn-success, btn-sm, btn-lg
Forms:   input, input-error, label, form-group
Alerts:  alert-error, alert-success, alert-warning, alert-info
Badges:  badge-primary, badge-success, badge-warning, badge-danger
Tables:  table (auto-styled th/td)
Icons:   icon-btn, icon-btn-primary, icon-btn-danger
Lists:   list-item, list-item-bordered
```

### Tailwind - Full Freedom
Use any Tailwind classes. Common patterns:
- Colors: `bg-{color}-{shade}`, `text-{color}-{shade}` (e.g., `bg-emerald-500`, `text-rose-600`)
- Gradients: `bg-gradient-to-r from-{color} to-{color}`
- Spacing: `p-{n}`, `m-{n}`, `gap-{n}`, `space-y-{n}`
- Layout: `flex`, `grid`, `grid-cols-{n}`, `justify-between`, `items-center`
- Responsive: `sm:`, `md:`, `lg:`, `xl:` prefixes
- Effects: `shadow-{sm|md|lg|xl}`, `rounded-{sm|md|lg|xl|full}`
- Transitions: `transition-all`, `duration-{ms}`, `hover:`, `focus:`

### Icons (ONLY use these exact names from @heroicons/react)
```jsx
import { IconName } from '@heroicons/react/24/outline'; // or /24/solid
```

**Common Icons (verified, use these exact names):**
- Navigation: `HomeIcon`, `ArrowLeftIcon`, `ArrowRightIcon`, `ChevronDownIcon`, `ChevronUpIcon`, `Bars3Icon`, `XMarkIcon`
- Actions: `PlusIcon`, `MinusIcon`, `TrashIcon`, `PencilIcon`, `PencilSquareIcon`, `CheckIcon`, `XMarkIcon`
- User/Auth: `UserIcon`, `UserCircleIcon`, `UserPlusIcon`, `ArrowRightOnRectangleIcon` (logout), `ArrowLeftOnRectangleIcon` (login), `LockClosedIcon`, `LockOpenIcon`, `KeyIcon`
- Communication: `EnvelopeIcon`, `ChatBubbleLeftIcon`, `BellIcon`, `PhoneIcon`
- Data: `MagnifyingGlassIcon`, `FunnelIcon`, `AdjustmentsHorizontalIcon`, `DocumentIcon`, `FolderIcon`, `ClipboardIcon`
- Status: `CheckCircleIcon`, `ExclamationCircleIcon`, `ExclamationTriangleIcon`, `InformationCircleIcon`, `QuestionMarkCircleIcon`
- Media: `PhotoIcon`, `PlayIcon`, `PauseIcon`, `MusicalNoteIcon`, `FilmIcon`
- Commerce: `ShoppingCartIcon`, `CreditCardIcon`, `CurrencyDollarIcon`, `TagIcon`, `GiftIcon`
- UI: `EyeIcon`, `EyeSlashIcon`, `HeartIcon`, `StarIcon`, `BookmarkIcon`, `ShareIcon`, `LinkIcon`
- Misc: `CalendarIcon`, `ClockIcon`, `MapPinIcon`, `GlobeAltIcon`, `CloudIcon`, `SunIcon`, `MoonIcon`, `Cog6ToothIcon`

**⚠️ DO NOT invent icon names** - If unsure, use a generic icon like `Squares2X2Icon` or skip the icon.

```jsx
<PlusIcon className="h-5 w-5" />
```

### Toast Notifications
```jsx
import toast from 'react-hot-toast';

toast.success('Saved!');
toast.error('Failed to save');
toast.promise(asyncOperation, {
  loading: 'Saving...',
  success: 'Done!',
  error: 'Error'
});
```

## Code Pattern
```jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { PlusIcon } from '@heroicons/react/24/outline';
import { Spinner } from './components';

const API_URL = '';

function App() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchItems(); }, []);

  const fetchItems = async () => {
    try {
      const { data } = await axios.get(`${API_URL}/api/items`);
      setItems(data.items || data);
    } catch (err) {
      toast.error('Failed to load');
    } finally {
      setLoading(false);
    }
  };

  // Build your own UI structure - be creative with layout and colors!
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Your header design */}
      {/* Your main content */}
      {/* Your footer */}
    </div>
  );
}

export default App;
```

## Design Freedom
- Choose your own color scheme (not limited to blue)
- Create your own header/layout structure
- Use cards, grids, lists - whatever fits the app
- Add animations, gradients, shadows as you see fit
- Make it visually appropriate for the app's purpose
