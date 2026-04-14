# Backend API Patterns

## Service Layer Pattern

```php
// Controller delegates to service
class InvoiceController extends Controller
{
    public function __construct(
        private InvoiceService $service
    ) {}
    
    public function store(StoreInvoiceRequest $request)
    {
        $invoice = $this->service->create($request->validated());
        return response()->json($invoice, 201);
    }
}
```

## Repository Pattern

```php
// For complex queries
class InvoiceRepository
{
    public function findWithRelations(int $id): Invoice
    {
        return Invoice::with(['user', 'items'])->findOrFail($id);
    }
    
    public function paginateForUser(int $userId): LengthAwarePaginator
    {
        return Invoice::where('user_id', $userId)->paginate(15);
    }
}
```

## Resource Transformation

```php
// Use API Resources for consistent output
class InvoiceResource extends JsonResource
{
    public function toArray($request): array
    {
        return [
            'id' => $this->id,
            'number' => $this->number,
            'amount' => $this->amount,
            'status' => $this->status,
            'created_at' => $this->created_at->toIso8601String(),
            'user' => new UserResource($this->whenLoaded('user')),
        ];
    }
}

// In controller
return new InvoiceResource($invoice);
// or
return InvoiceResource::collection($invoices);
```

## Query Optimization

```php
// ALWAYS eager load relationships
Invoice::with(['user', 'items'])->get();

// NEVER do N+1
// BAD:
$invoices = Invoice::all();
foreach ($invoices as $invoice) {
    $invoice->user->name; // N+1 query!
}
```
