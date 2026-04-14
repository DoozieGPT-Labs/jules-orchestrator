# Backend API Rules

## Controller Pattern

### Required Structure
```php
class {Name}Controller extends Controller
{
    public function index(Request $request): JsonResponse
    {
        // MUST: Paginate results
        // MUST: Return JsonResponse
    }
    
    public function store(StoreRequest $request): JsonResponse
    {
        // MUST: Use form request validation
        // MUST: Return 201 on success
    }
    
    public function show($id): JsonResponse
    {
        // MUST: Handle 404
        // MUST: Type-hint $id
    }
    
    public function update(UpdateRequest $request, $id): JsonResponse
    {
        // MUST: Validate input
        // MUST: Return updated model
    }
    
    public function destroy($id): JsonResponse
    {
        // MUST: Soft delete if configured
        // MUST: Return 204 on success
    }
}
```

## Route Registration

```php
// MUST use apiResource for API routes
Route::apiResource('name', Controller::class);

// Explicit routes for custom actions
Route::get('name/custom', [Controller::class, 'customAction']);
```

## Response Standards

### Success (200)
```php
return response()->json([
    'data' => $data,
    'message' => 'Success'
]);
```

### Created (201)
```php
return response()->json([
    'data' => $data,
    'message' => 'Created'
], 201);
```

### Not Found (404)
```php
return response()->json([
    'message' => 'Resource not found'
], 404);
```

### Validation Error (422)
```php
return response()->json([
    'message' => 'Validation failed',
    'errors' => $errors
], 422);
```

## Constraints (MUST FOLLOW)

1. **Dependency Injection**: MUST inject models and services
2. **Type Hints**: MUST type-hint all parameters
3. **Return Types**: MUST declare return types
4. **Validation**: MUST use Form Request classes
5. **Authorization**: MUST use policies or gates
6. **Logging**: MUST log all actions
7. **Error Handling**: MUST wrap in try-catch
