---
description: Frontend development guidelines for the agentic-job-scraper project using React, TypeScript, Shadcn UI, and Vite
---

# Frontend React Skill

This skill provides guidelines for frontend development in the agentic-job-scraper project.

## Tech Stack

- **Language**: TypeScript
- **Framework**: React 18
- **Build Tool**: Vite
- **UI Components**: Shadcn UI (Radix UI primitives)
- **Styling**: Tailwind CSS
- **Icons**: Lucide React
- **State Management**: React Context + useState/useEffect
- **API**: Fetch API with custom service layer
- **Real-time**: WebSocket for progress updates

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── Layout.tsx          # Main layout with WebSocket provider
│   │   └── ui/                 # Shadcn UI components
│   ├── pages/
│   │   ├── Dashboard.tsx       # Main dashboard
│   │   ├── Channels.tsx        # Channel management
│   │   ├── Messages.tsx        # Message list
│   │   ├── Jobs.tsx            # Job listings
│   │   ├── Developers.tsx      # Developer listings
│   │   └── TelegramAccounts.tsx # Telegram account management
│   ├── hooks/
│   │   └── useWebSocket.ts     # WebSocket hook for progress updates
│   ├── services/
│   │   └── api.ts              # API service layer
│   ├── components.json         # Shadcn UI configuration
│   └── main.tsx               # Application entry point
└── package.json
```

## Key Patterns

### API Calls

**Use the centralized API service:**
```typescript
import api from '../services/api';

const data = await api.getChannels();
const result = await api.fetchChannel(channelId);
```

**API service is in `src/services/api.ts`:**
```typescript
const API_BASE = 'http://localhost:8000';

export default {
  getChannels: async (): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/channels`);
    return response.json();
  },
  // ... other methods
};
```

### State Management

**Use React hooks for local state:**
```typescript
const [channels, setChannels] = useState<Channel[]>([]);
const [loading, setLoading] = useState(false);
const [error, setError] = useState<string | null>(null);
```

**Use Context for global state (WebSocket progress):**
```typescript
const { progress, channelProgress, operations } = useWebSocketProgress();
```

### WebSocket Integration

**Use the WebSocket context for real-time updates:**
```typescript
import { useWebSocketProgress } from '../hooks/useWebSocket';

const { progress, channelProgress, operations } = useWebSocketProgress();

// Check if channel is processing
const isProcessing = !!operations[channel.username];

// Show progress bar
{channelProgress[channel.username] && (
  <ProgressBar
    current={channelProgress[channel.username].current}
    total={channelProgress[channel.username].total}
  />
)}
```

**WebSocket events:**
- `fetch_start` - Fetch operation started
- `fetch_progress` - Fetch progress update
- `fetch_complete` - Fetch operation completed
- `analyze_start` - Analysis operation started
- `analyze_progress` - Analysis progress update
- `analyze_complete` - Analysis operation completed
- `error` - Operation error

### Shadcn UI Components

**Install new components:**
```bash
npx shadcn-ui@latest add [component-name]
```

**Use components from `@/components/ui`:**
```typescript
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
```

**Common components:**
- Button, Input, Card, Dialog, Table, Badge, Select, etc.

### Loading States

**Use loading states for async operations:**
```typescript
const [loadingActions, setLoadingActions] = useState<Set<string>>(new Set());

const handleAction = async (actionKey: string, action: () => Promise<void>) => {
  setLoadingActions(prev => new Set(prev).add(actionKey));
  try {
    await action();
  } finally {
    setLoadingActions(prev => {
      const newSet = new Set(prev);
      newSet.delete(actionKey);
      return newSet;
    });
  }
};

// Usage
<button
  onClick={() => handleAction(`fetch-${channel.id}`, () => api.fetchChannel(channel.id))}
  disabled={loadingActions.has(`fetch-${channel.id}`)}
>
  {loadingActions.has(`fetch-${channel.id}`) ? 'Fetching...' : 'Fetch'}
</button>
```

### Error Handling

**Show toast notifications for errors:**
```typescript
const showToast = (type: 'success' | 'error', message: string) => {
  // Use your toast implementation
};

try {
  await api.someOperation();
  showToast('success', 'Operation completed');
} catch (error) {
  showToast('error', 'Operation failed');
}
```

**Do NOT use console.log or console.error** - remove all console statements from production code.

### TypeScript Types

**Define interfaces for API responses:**
```typescript
interface Channel {
  id: number;
  username: string;
  name: string;
  is_active: boolean;
  // ... other fields
}

interface Job {
  id: number;
  title: string;
  company: string;
  // ... other fields
}
```

**Use type assertions sparingly - prefer proper typing:**
```typescript
// Good
const data: Channel[] = await api.getChannels();

// Avoid if possible
const data = await api.getChannels() as Channel[];
```

## Styling Guidelines

**Use Tailwind CSS classes:**
```typescript
<div className="flex items-center justify-between p-4 border rounded-lg">
  <h2 className="text-lg font-semibold">Title</h2>
  <Button variant="outline">Action</Button>
</div>
```

**Common patterns:**
- `flex items-center justify-between` - Row layout
- `space-x-4` - Horizontal spacing
- `space-y-4` - Vertical spacing
- `p-4` - Padding
- `rounded-lg` - Rounded corners
- `border` - Border
- `bg-white` - White background
- `text-gray-900` - Dark text
- `text-sm` - Small text

## Common Issues

### WebSocket Disconnection

**Symptom**: Progress updates stop showing

**Cause**: WebSocket disconnected

**Solution**: The WebSocket hook auto-reconnects every 5 seconds. Also, the frontend polls the operations API every 5 seconds as a fallback.

### Stuck Operation States

**Symptom**: Button shows "Processing..." even after operation completes

**Cause**: WebSocket message missed, state not cleared

**Solution**: The polling logic (every 5 seconds) checks the database and clears operations that are no longer running. Wait up to 5 seconds for auto-correction.

### Console Errors

**Symptom**: Console errors in browser

**Cause**: Leftover console.log/console.error statements

**Solution**: Remove all console statements from frontend code. Use toast notifications for user-facing messages.

## Coding Standards

- **Comments**: Use English only. No Korean or other non-English text.
- **Console**: Remove all console.log, console.error, console.warn statements.
- **TypeScript**: Use proper type hints for all variables and function parameters.
- **Components**: Use functional components with hooks.
- **Styling**: Use Tailwind CSS classes, avoid inline styles.
- **Error Handling**: Show user-friendly error messages via toasts, not console.
- **Loading States**: Always show loading indicators for async operations.
- **Disabled States**: Disable buttons during async operations to prevent duplicate requests.

## Development Workflow

**Start development server:**
```bash
cd frontend
npm run dev
```

**Build for production:**
```bash
cd frontend
npm run build
```

**Install new dependencies:**
```bash
cd frontend
npm install [package-name]
```

**Add new Shadcn UI component:**
```bash
cd frontend
npx shadcn-ui@latest add [component-name]
```
