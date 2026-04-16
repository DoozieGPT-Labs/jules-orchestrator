# CI/CD Rules

## GitHub Actions

### Workflow Structure
```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup PHP
        uses: shivammathur/setup-php@v2
        with:
          php-version: '8.3'
          extensions: pdo, pdo_mysql

      - name: Install dependencies
        run: composer install --no-interaction --prefer-dist

      - name: Run tests
        run: ./vendor/bin/phpunit --coverage-clover coverage.xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: coverage.xml
```

### Security Scanning
```yaml
# .github/workflows/security.yml
name: Security

on:
  push:
    branches: [main]
  schedule:
    - cron: '0 0 * * 0' # Weekly

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          format: 'sarif'
          output: 'trivy-results.sarif'

      - name: Upload results
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: 'trivy-results.sarif'

      - name: Dependency review
        uses: actions/dependency-review-action@v3
```

## Docker

### Multi-stage Dockerfile
```dockerfile
# Build stage
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

# Production stage
FROM node:20-alpine AS production
RUN apk add --no-cache dumb-init
ENV NODE_ENV=production
USER node
WORKDIR /app
COPY --from=builder --chown=node:node /app/node_modules ./node_modules
COPY --chown=node:node . .
EXPOSE 3000
CMD ["dumb-init", "node", "server.js"]
```

### Laravel PHP Dockerfile
```dockerfile
FROM php:8.3-fpm-alpine

# Install dependencies
RUN apk add --no-cache \
    postgresql-dev \
    libzip-dev \
    zip \
    unzip \
    git

# PHP extensions
RUN docker-php-ext-install \
    pdo_pgsql \
    zip \
    opcache

# Composer
COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

# App setup
WORKDIR /var/www
COPY composer.json composer.lock ./
RUN composer install --no-dev --optimize-autoloader

COPY . .
RUN chown -R www-data:www-data storage bootstrap/cache

# Health check
HEALTHCHECK --interval=30s --timeout=3s \
    CMD php artisan health:check || exit 1
```

### Docker Compose
```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - APP_ENV=production
      - DB_HOST=db
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "php", "artisan", "health:check"]
      interval: 30s
      timeout: 3s
      retries: 3

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: app
      POSTGRES_USER: app
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - db_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:

secrets:
  db_password:
    external: true
```

## Deployment Strategies

### Blue-Green Deployment
```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Determine active environment
        id: env
        run: |
          CURRENT=$(kubectl get svc app -o jsonpath='{.spec.selector.version}')
          if [ "$CURRENT" = "blue" ]; then
            echo "target=green" >> $GITHUB_OUTPUT
            echo "current=blue" >> $GITHUB_OUTPUT
          else
            echo "target=blue" >> $GITHUB_OUTPUT
            echo "current=green" >> $GITHUB_OUTPUT
          fi

      - name: Deploy to ${{ steps.env.outputs.target }}
        run: |
          kubectl set image deployment/app-${{ steps.env.outputs.target }} \
            app=myapp:${{ github.sha }}
          kubectl rollout status deployment/app-${{ steps.env.outputs.target }}

      - name: Switch traffic
        run: |
          kubectl patch svc app -p \
            '{"spec":{"selector":{"version":"${{ steps.env.outputs.target }}"}}}'

      - name: Health check
        run: |
          curl -f https://api.example.com/health || exit 1

      - name: Rollback on failure
        if: failure()
        run: |
          kubectl patch svc app -p \
            '{"spec":{"selector":{"version":"${{ steps.env.outputs.current }}"}}}'
```

### Canary Deployment
```yaml
      - name: Canary deploy
        run: |
          # Deploy canary (10% traffic)
          kubectl apply -f k8s/canary-deployment.yaml
          kubectl set image deployment/app-canary app=myapp:${{ github.sha }}

          # Wait and monitor
          sleep 300

          # Check error rate
          ERROR_RATE=$(curl -s "https://monitoring/api/v1/query?query=..." | jq '.data.result[0].value[1]')

          if (( $(echo "$ERROR_RATE > 0.01" | bc -l) )); then
            echo "Error rate too high, rolling back"
            kubectl delete deployment app-canary
            exit 1
          fi

          # Promote to full deployment
          kubectl set image deployment/app app=myapp:${{ github.sha }}
          kubectl delete deployment app-canary
```

## Secrets Management

### GitHub Secrets
```yaml
# Use secrets in workflows
- name: Deploy
  env:
    DATABASE_URL: ${{ secrets.DATABASE_URL }}
    API_KEY: ${{ secrets.API_KEY }}
  run: |
    echo "Deploying with configured secrets"
```

### Environment-specific Variables
```yaml
jobs:
  deploy:
    environment:
      name: production
      url: https://api.example.com
    steps:
      - uses: actions/checkout@v4

      - name: Deploy
        run: ./scripts/deploy.sh
        env:
          ENVIRONMENT: production
          DATABASE_URL: ${{ secrets.PROD_DATABASE_URL }}
```

## Testing in CI

### Test Matrix
```yaml
strategy:
  matrix:
    php: ['8.2', '8.3']
    db: ['mysql', 'pgsql']
    include:
      - php: '8.3'
        coverage: true

services:
  mysql:
    image: mysql:8
    env:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: test

  postgres:
    image: postgres:16
    env:
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
      POSTGRES_DB: test

steps:
  - name: Setup
    uses: shivammathur/setup-php@v2
    with:
      php-version: ${{ matrix.php }}

  - name: Test with ${{ matrix.db }}
    env:
      DB_CONNECTION: ${{ matrix.db }}
    run: ./vendor/bin/phpunit
```

## Monitoring & Alerts

### Deployment Notifications
```yaml
      - name: Notify Slack
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          fields: repo,message,commit,author,action,eventName,ref,workflow
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}

      - name: Create deployment record
        uses: chrissnk/actions-create-deployment@v1
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          environment: production
          ref: ${{ github.sha }}
```

## Infrastructure as Code

### Terraform Example
```hcl
# main.tf
resource "aws_ecs_service" "app" {
  name            = "app"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = 2

  deployment_controller {
    type = "ECS"
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
}
```

## Rollback Procedures

### Automatic Rollback
```yaml
      - name: Deploy
        id: deploy
        run: |
          kubectl set image deployment/app app=myapp:${{ github.sha }}
          kubectl rollout status deployment/app --timeout=300s

      - name: Rollback on failure
        if: failure()
        run: |
          kubectl rollout undo deployment/app
          kubectl rollout status deployment/app
```
