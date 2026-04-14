# Backend API Anti-Patterns (NEVER DO)

## ❌ Fat Controllers

```php
// BAD: Controller doing too much
public function store(Request $request)
{
    $data = $request->all();
    // Validate inline
    if (!$data['email']) {
        return response()->json(['error' => 'Email required'], 400);
    }
    // Create model
    $invoice = new Invoice();
    $invoice->fill($data);
    $invoice->save();
    // Send email
    Mail::to($invoice->user)->send(new InvoiceCreated($invoice));
    // Log
    Log::info('Invoice created');
    return response()->json($invoice);
}
```

## ❌ No Validation

```php
// BAD: Never use Request without validation
public function store(Request $request)
{
    $invoice = Invoice::create($request->all()); // DANGEROUS
    return response()->json($invoice);
}
```

## ❌ Raw SQL

```php
// BAD: Never use raw SQL
DB::select("SELECT * FROM invoices WHERE user_id = {$userId}"); // SQL Injection!
```

## ❌ No Error Handling

```php
// BAD: No try-catch
public function show($id)
{
    $invoice = Invoice::findOrFail($id); // Throws 500 on fail
    return response()->json($invoice);
}

// GOOD: Handle gracefully
public function show($id)
{
    try {
        $invoice = Invoice::findOrFail($id);
        return response()->json($invoice);
    } catch (ModelNotFoundException $e) {
        return response()->json(['message' => 'Invoice not found'], 404);
    }
}
```

## ❌ Business Logic in Controller

```php
// BAD: Business logic mixed with HTTP
if ($invoice->status === 'paid' && $invoice->amount > 1000) {
    // Complex business rule inline
    $invoice->flagForReview();
}

// GOOD: Move to service or model
$invoice->checkForReviewFlag(); // Model method
```

## ❌ No Return Type Declarations

```php
// BAD: No type hints
function index($request) { }

// GOOD: Always type hint
function index(Request $request): JsonResponse { }
```
