# Database Design Rules

## Migration Standards

### Required Structure
```php
// MUST: Use proper naming convention
class Create{TableName}Table extends Migration
{
    public function up(): void
    {
        Schema::create('table_name', function (Blueprint $table) {
            // MUST: Use $table->id() for primary key
            $table->id();
            
            // MUST: Use proper column types
            // $table->string('name'); // For short text
            // $table->text('description'); // For long text
            // $table->integer('count'); // For whole numbers
            // $table->decimal('amount', 10, 2); // For money
            
            // MUST: Add indexes for foreign keys
            // $table->foreignId('user_id')->constrained();
            
            // MUST: Always include timestamps
            $table->timestamps();
            
            // SHOULD: Add soft deletes if needed
            // $table->softDeletes();
        });
    }
    
    public function down(): void
    {
        // MUST: Drop table in down()
        Schema::dropIfExists('table_name');
    }
}
```

## Model Standards

```php
class Invoice extends Model
{
    // MUST: Define fillable
    protected $fillable = [
        'user_id',
        'invoice_number',
        'amount',
        'status',
        'due_date',
    ];
    
    // MUST: Define casts for dates
    protected $casts = [
        'due_date' => 'date',
        'paid_at' => 'datetime',
        'amount' => 'decimal:2',
    ];
    
    // MUST: Define relationships
    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }
    
    public function items(): HasMany
    {
        return $this->hasMany(InvoiceItem::class);
    }
}
```

## Constraints (MUST FOLLOW)

1. **Foreign Keys**: MUST use constrained() for referential integrity
2. **Indexes**: MUST index foreign keys and search columns
3. **Timestamps**: MUST include created_at and updated_at
4. **Soft Deletes**: SHOULD use for important data
5. **Validation**: MUST validate before DB operations
6. **Transactions**: SHOULD wrap related operations
