# Performance Rules

## Query Optimization

### Prevent N+1
```php
// BAD: N+1 queries
$invoices = Invoice::all();
foreach ($invoices as $invoice) {
    echo $invoice->user->name; // Additional query!
}

// GOOD: Eager load
$invoices = Invoice::with('user')->get();
foreach ($invoices as $invoice) {
    echo $invoice->user->name; // No extra query
}
```

### Use Indexes
```php
// Add indexes in migrations
$table->index('user_id');
$table->index(['status', 'created_at']);

// Use whereIndex
Invoice::where('status', 'pending')->get();
```

### Chunk Large Queries
```php
// Process in chunks
Invoice::where('status', 'pending')->chunk(100, function ($invoices) {
    foreach ($invoices as $invoice) {
        $invoice->process();
    }
});
```

## Caching

### Cache Expensive Operations
```php
// Cache query results
$invoices = Cache::remember('invoices', 3600, function () {
    return Invoice::with('user')->get();
});

// Cache computed values
$total = Cache::remember("total:{$userId}", 300, function () use ($userId) {
    return Invoice::where('user_id', $userId)->sum('amount');
});
```

## Memory Management

### Use Generators for Large Data
```php
// Stream data instead of loading all
foreach (Invoice::cursor() as $invoice) {
    // Process one at a time
}
```

## Constraints (MUST FOLLOW)

1. **Eager load** - Always with() relationships
2. **Index queries** - Add indexes for filters
3. **Cache heavy** - Operations > 100ms
4. **Chunk large** - Never load 10k+ records
5. **Profile queries** - Use Debugbar to check
