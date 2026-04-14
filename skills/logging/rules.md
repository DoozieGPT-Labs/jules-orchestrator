# Logging Rules

## Log Levels

### Use Appropriate Levels
```php
// DEBUG: Detailed info for debugging
Log::debug('Invoice created', ['id' => $invoice->id]);

// INFO: Interesting events
Log::info('User logged in', ['user_id' => $user->id]);

// WARNING: Unexpected but not errors
Log::warning('Invoice payment delayed', ['id' => $invoice->id]);

// ERROR: Runtime errors
Log::error('Invoice creation failed', ['error' => $e->getMessage()]);
```

## Structured Logging

### Include Context
```php
Log::info('Invoice created', [
    'invoice_id' => $invoice->id,
    'user_id' => $invoice->user_id,
    'amount' => $invoice->amount,
    'ip' => request()->ip(),
]);
```

## Request Logging

```php
// Log all API requests
Log::info('API Request', [
    'method' => request()->method(),
    'url' => request()->url(),
    'user_id' => auth()->id(),
    'ip' => request()->ip(),
]);
```

## Error Handling

```php
try {
    $invoice->process();
} catch (Exception $e) {
    Log::error('Invoice processing failed', [
        'invoice_id' => $invoice->id,
        'error' => $e->getMessage(),
        'trace' => $e->getTraceAsString(),
    ]);
    
    throw $e; // Re-throw if needed
}
```

## Constraints (MUST FOLLOW)

1. **Log all actions** - Who did what when
2. **Include context** - IDs, amounts, etc.
3. **Use structured format** - Key-value pairs
4. **Never log passwords** - Or sensitive data
5. **Log errors** - With full context
