# Error Handling Rules

## Core Principles

1. **Never expose internal details to users**
2. **Log full context for debugging**
3. **Fail gracefully with helpful messages**
4. **Always clean up resources**

## PHP/Laravel Error Handling

### Exception Hierarchy
```php
// App/Exceptions/ApplicationException.php
abstract class ApplicationException extends Exception
{
    abstract public function getStatusCode(): int;
    abstract public function getErrorCode(): string;

    public function render(): JsonResponse
    {
        return response()->json([
            'error' => [
                'code' => $this->getErrorCode(),
                'message' => $this->getMessage(),
                'trace_id' => Context::get('trace_id'),
            ]
        ], $this->getStatusCode());
    }
}

// Specific exceptions
class ValidationException extends ApplicationException
{
    public function getStatusCode(): int { return 422; }
    public function getErrorCode(): string { return 'VALIDATION_ERROR'; }
}

class NotFoundException extends ApplicationException
{
    public function getStatusCode(): int { return 404; }
    public function getErrorCode(): string { return 'RESOURCE_NOT_FOUND'; }
}
```

### Exception Handler Pattern
```php
// App/Exceptions/Handler.php
public function register(): void
{
    $this->reportable(function (ApplicationException $e) {
        Log::error('Application exception', [
            'exception' => $e,
            'trace_id' => Context::get('trace_id'),
            'user_id' => auth()->id(),
        ]);
    });

    $this->renderable(function (ApplicationException $e) {
        return $e->render();
    });
}
```

### Try-Catch Best Practices
```php
// BAD: Empty catch
try {
    $result = riskyOperation();
} catch (Exception $e) {
    // Silent failure!
}

// GOOD: Proper handling
try {
    $result = riskyOperation();
} catch (ValidationException $e) {
    // Expected exception - return user-friendly error
    return $e->render();
} catch (Exception $e) {
    // Unexpected exception - log and return generic error
    Log::error('Unexpected error in operation', [
        'exception' => $e,
        'context' => $operationContext,
    ]);
    return response()->json([
        'error' => 'An unexpected error occurred',
        'trace_id' => Context::get('trace_id'),
    ], 500);
} finally {
    // Always clean up
    $this->cleanup();
}
```

## API Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The email field is required",
    "details": {
      "email": ["The email field is required"]
    },
    "trace_id": "abc123-def456"
  }
}
```

## Error Codes by Category

| Category | Prefix | Example |
|----------|--------|---------|
| Validation | `VAL_` | `VAL_REQUIRED` |
| Authentication | `AUTH_` | `AUTH_INVALID_TOKEN` |
| Authorization | `FORBIDDEN_` | `FORBIDDEN_ROLE` |
| Resource | `RES_` | `RES_NOT_FOUND` |
| Rate Limit | `RATE_` | `RATE_LIMIT_EXCEEDED` |
| Server | `SRV_` | `SRV_DATABASE_ERROR` |

## Resource Cleanup Pattern

```php
$resource = null;
try {
    $resource = openResource();
    // Use resource
} finally {
    // Guaranteed to run
    if ($resource) {
        $resource->close();
    }
}
```

## Async Operation Error Handling

```php
// Queue job with automatic retry
class ProcessInvoice implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public $tries = 3;
    public $backoff = [60, 300, 900]; // 1min, 5min, 15min

    public function handle(): void
    {
        try {
            $this->process();
        } catch (RetryableException $e) {
            // Will auto-retry
            throw $e;
        } catch (NonRetryableException $e) {
            // Fail immediately
            $this->fail($e);
        }
    }

    public function failed(Throwable $e): void
    {
        // Notify admin
        Notification::route('mail', 'admin@example.com')
            ->notify(new JobFailedNotification($this, $e));
    }
}
```

## Circuit Breaker Pattern

```php
class CircuitBreaker
{
    private int $failureCount = 0;
    private int $threshold = 5;
    private int $timeout = 60;
    private ?DateTime $lastFailure = null;

    public function call(callable $operation)
    {
        if ($this->isOpen()) {
            throw new CircuitOpenException('Service temporarily unavailable');
        }

        try {
            $result = $operation();
            $this->onSuccess();
            return $result;
        } catch (Exception $e) {
            $this->onFailure();
            throw $e;
        }
    }

    private function isOpen(): bool
    {
        if ($this->failureCount < $this->threshold) {
            return false;
        }

        $elapsed = time() - $this->lastFailure->getTimestamp();
        return $elapsed < $this->timeout;
    }
}
```
