# Frontend React Rules

## Component Architecture

### File Structure
```
src/
├── components/
│   ├── ui/           # Reusable UI primitives
│   ├── forms/        # Form-specific components
│   ├── layout/       # Layout wrappers
│   └── features/     # Feature-specific components
├── hooks/            # Custom hooks
├── lib/              # Utilities
├── types/            # TypeScript types
└── pages/            # Route components
```

### Component Patterns

#### Functional Components (Preferred)
```typescript
// ✅ GOOD: Named export, typed props
interface UserCardProps {
  user: User;
  onSelect?: (user: User) => void;
}

export function UserCard({ user, onSelect }: UserCardProps) {
  return (
    <div className="user-card" onClick={() => onSelect?.(user)}>
      <Avatar src={user.avatar} />
      <span>{user.name}</span>
    </div>
  );
}

// ❌ BAD: Default export, any types
export default function UserCard(props: any) {
  return <div>{props.user.name}</div>;
}
```

#### Custom Hooks
```typescript
// hooks/useApi.ts
export function useApi<T>(url: string) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetch() {
      try {
        setLoading(true);
        const response = await fetch(url);
        const result = await response.json();
        if (!cancelled) setData(result);
      } catch (e) {
        if (!cancelled) setError(e as Error);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetch();
    return () => { cancelled = true; };
  }, [url]);

  return { data, loading, error };
}
```

## State Management

### Local State (useState)
```typescript
// Simple state
const [count, setCount] = useState(0);

// Lazy initialization
const [items, setItems] = useState(() => loadInitialItems());

// Object state - prefer splitting
const [user, setUser] = useState<User | null>(null);
const [isLoading, setIsLoading] = useState(false);
// Not: const [state, setState] = useState({ user: null, isLoading: false })
```

### Derived State
```typescript
// ✅ GOOD: Compute from props/state
const fullName = `${user.firstName} ${user.lastName}`;
const filteredItems = items.filter(item => item.active);

// ✅ GOOD: useMemo for expensive computation
const sortedData = useMemo(() => {
  return data.sort((a, b) => a.score - b.score);
}, [data]);

// ❌ BAD: useState for derived values
const [fullName, setFullName] = useState(''); // Don't do this
```

## Effects

### Effect Dependencies
```typescript
// ✅ GOOD: All dependencies listed
useEffect(() => {
  fetchUser(userId).then(setUser);
}, [userId]);

// ❌ BAD: Missing dependencies
useEffect(() => {
  fetchUser(userId).then(setUser);
}, []); // userId missing - stale closure bug!

// ✅ GOOD: Event handlers for user actions
function handleClick() {
  fetchUser(userId).then(setUser);
}
// Not: useEffect(() => { fetchUser() }, []) on mount
```

### Cleanup Patterns
```typescript
useEffect(() => {
  const controller = new AbortController();

  fetch('/api/data', { signal: controller.signal })
    .then(setData);

  return () => controller.abort();
}, []);

// Subscription cleanup
useEffect(() => {
  const subscription = websocket.subscribe(message => {
    setMessages(prev => [...prev, message]);
  });

  return () => subscription.unsubscribe();
}, []);
```

## Performance

### Memoization
```typescript
// Component memoization
const UserList = memo(function UserList({ users }: { users: User[] }) {
  return (
    <ul>
      {users.map(user => <UserItem key={user.id} user={user} />)}
    </ul>
  );
});

// Callback memoization
const handleSubmit = useCallback((data: FormData) => {
  api.submit(data).then(onSuccess);
}, [onSuccess]);

// Value memoization
const config = useMemo(() => ({
  theme: darkMode ? 'dark' : 'light',
  locale: 'en'
}), [darkMode]);
```

### Avoid Unnecessary Renders
```typescript
// ❌ BAD: Object recreated every render
<Child config={{ theme: 'dark' }} />

// ✅ GOOD: Stable reference
const config = useMemo(() => ({ theme: 'dark' }), []);
<Child config={config} />

// ✅ GOOD: Primitive props
<Child theme="dark" />
```

## Error Boundaries

```typescript
// components/ErrorBoundary.tsx
interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<
  { children: ReactNode; fallback?: ReactNode },
  State
> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    logErrorToService(error, info);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? <ErrorFallback error={this.state.error} />;
    }
    return this.props.children;
  }
}
```

## Styling

### CSS Modules / Tailwind
```typescript
// Tailwind approach
function Button({ variant = 'primary', children }: ButtonProps) {
  const baseClasses = 'px-4 py-2 rounded font-medium transition-colors';
  const variants = {
    primary: 'bg-blue-600 hover:bg-blue-700 text-white',
    secondary: 'bg-gray-200 hover:bg-gray-300 text-gray-800',
    danger: 'bg-red-600 hover:bg-red-700 text-white',
  };

  return (
    <button className={`${baseClasses} ${variants[variant]}`}>
      {children}
    </button>
  );
}
```

## Testing

```typescript
// Component tests
import { render, screen, fireEvent } from '@testing-library/react';

describe('UserCard', () => {
  const mockUser = { id: '1', name: 'John', avatar: '/avatar.jpg' };

  it('renders user information', () => {
    render(<UserCard user={mockUser} />);
    expect(screen.getByText('John')).toBeInTheDocument();
  });

  it('calls onSelect when clicked', () => {
    const onSelect = jest.fn();
    render(<UserCard user={mockUser} onSelect={onSelect} />);
    fireEvent.click(screen.getByText('John'));
    expect(onSelect).toHaveBeenCalledWith(mockUser);
  });
});
```

## TypeScript Best Practices

```typescript
// ✅ Use strict types
interface ApiResponse<T> {
  data: T;
  meta: PaginationMeta;
}

// ✅ Discriminated unions for state
type AsyncState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: Error };

// ✅ Generic hooks
function useLocalStorage<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => {
    const stored = localStorage.getItem(key);
    return stored ? JSON.parse(stored) : initial;
  });
  // ...
}
```
