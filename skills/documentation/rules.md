# Documentation Rules

## README Standards

### Required Sections
```markdown
# Project Name

## Description
Brief description of what this does.

## Installation
```bash
composer install
```

## Usage
```php
// Example code
$invoice = Invoice::create([...]);
```

## API Reference
- `GET /api/invoices` - List all
- `POST /api/invoices` - Create new

## Testing
```bash
php artisan test
```
```

## Code Documentation

### PHPDoc Required
```php
/**
 * Create a new invoice
 *
 * @param array $data Invoice data
 * @return Invoice Created invoice
 * @throws ValidationException When validation fails
 */
public function create(array $data): Invoice
{
    // ...
}
```

### Inline Comments
```php
// Calculate total with tax
$total = $subtotal * (1 + $taxRate);

// WHY: Cache for 1 hour to reduce DB load
$invoices = Cache::remember('invoices', 3600, fn() => Invoice::all());
```

## API Documentation

### OpenAPI/Swagger
```php
/**
 * @OA\Get(
 *     path="/api/invoices",
 *     summary="List invoices",
 *     @OA\Response(response=200, description="Success")
 * )
 */
```

## Constraints (MUST FOLLOW)

1. **README first** - Create before coding
2. **PHPDoc all methods** - Public API only
3. **Document WHY** - Not just WHAT
4. **Keep updated** - Sync with code changes
5. **Examples required** - For complex features
