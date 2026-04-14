# Testing Rules

## Test Structure

### Required Organization
```
tests/
├── Feature/           # API/integration tests
│   ├── InvoiceControllerTest.php
│   └── UserTest.php
├── Unit/              # Unit tests
│   ├── InvoiceTest.php
│   └── Services/
└── TestCase.php       # Base test class
```

## Test Standards

### Feature Tests
```php
class InvoiceControllerTest extends TestCase
{
    use RefreshDatabase;
    
    /** @test */
    public function it_lists_invoices(): void
    {
        $invoices = Invoice::factory()->count(3)->create();
        
        $response = $this->getJson('/api/invoices');
        
        $response->assertOk()
                 ->assertJsonCount(3, 'data')
                 ->assertJsonStructure([
                     'data' => [
                         '*' => ['id', 'number', 'amount']
                     ]
                 ]);
    }
    
    /** @test */
    public function it_creates_invoice_with_valid_data(): void
    {
        $data = Invoice::factory()->make()->toArray();
        
        $response = $this->postJson('/api/invoices', $data);
        
        $response->assertCreated();
        $this->assertDatabaseHas('invoices', [
            'number' => $data['number']
        ]);
    }
    
    /** @test */
    public function it_rejects_invalid_invoice(): void
    {
        $response = $this->postJson('/api/invoices', []);
        
        $response->assertUnprocessable()
                 ->assertJsonValidationErrors(['number', 'amount']);
    }
}
```

### Unit Tests
```php
class InvoiceTest extends TestCase
{
    /** @test */
    public function it_calculates_total(): void
    {
        $invoice = Invoice::factory()->create(['amount' => 100]);
        
        $this->assertEquals(100, $invoice->amount);
    }
}
```

## Coverage Rules

### Minimum Coverage
- **Controllers**: 90% - All endpoints tested
- **Models**: 80% - Key methods tested
- **Services**: 100% - All business logic tested
- **Helpers**: 60% - Utility functions

### Required Tests Per Feature
1. **Index**: List with pagination, filtering, sorting
2. **Show**: Get single record, 404 for invalid ID
3. **Store**: Create with valid data, reject invalid data
4. **Update**: Update with valid data, reject invalid data
5. **Destroy**: Soft delete, confirm deletion

## Constraints (MUST FOLLOW)

1. **Database Isolation**: MUST use RefreshDatabase
2. **Factories**: MUST use factories for test data
3. **Assertions**: MUST assert both status AND structure
4. **Naming**: MUST use descriptive test names
5. **Coverage**: MUST maintain minimum 80% coverage
