# Security Rules

## Input Validation

### Required on ALL User Input
```php
// MUST: Validate all input
$validated = $request->validate([
    'email' => 'required|email|unique:users',
    'password' => 'required|min:8|confirmed',
]);

// MUST: Use Form Request classes for complex validation
class StoreInvoiceRequest extends FormRequest
{
    public function rules(): array
    {
        return [
            'amount' => 'required|numeric|min:0.01',
            'due_date' => 'required|date|after:today',
        ];
    }
}
```

## SQL Injection Prevention

### NEVER use raw SQL
```php
// BAD - SQL Injection possible
DB::select("SELECT * FROM invoices WHERE id = {$id}");

// GOOD - Use Query Builder
Invoice::where('id', $id)->first();

// GOOD - Parameter binding
DB::select('SELECT * FROM invoices WHERE id = ?', [$id]);
```

## Authorization

### MUST Check Permissions
```php
// Controller level
public function store(Request $request)
{
    $this->authorize('create', Invoice::class);
    // ...
}

// Route level
Route::post('/invoices', [InvoiceController::class, 'store'])
    ->middleware('can:create,App\Models\Invoice');

// Policy
class InvoicePolicy
{
    public function update(User $user, Invoice $invoice): bool
    {
        return $user->id === $invoice->user_id;
    }
}
```

## Password Security

```php
// MUST hash passwords
$user->password = Hash::make($password);

// MUST verify passwords
if (Hash::check($password, $user->password)) {
    // Valid
}
```

## XSS Prevention

```php
// Blade automatically escapes output
{{ $user->name }} // Escaped
{!! $user->bio !!} // Raw - ONLY for trusted HTML
```

## CSRF Protection

```php
// Form requests MUST include CSRF token
<form method="POST">
    @csrf
    <!-- fields -->
</form>
```

## Constraints (MUST FOLLOW)

1. **Validate ALL input** - Never trust user data
2. **Authorize ALL actions** - Check permissions
3. **Use Query Builder** - Never raw SQL
4. **Hash passwords** - Never store plain text
5. **Rate limiting** - Prevent brute force
6. **Audit logging** - Log security events
