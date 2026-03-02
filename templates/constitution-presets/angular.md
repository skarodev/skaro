# Constitution: <project name>

## Stack
- Language: TypeScript 5.x
- Framework: Angular 19
- State Management: NgRx / Angular Signals
- Routing: Angular Router (standalone)
- Styling: SCSS / Angular Material 19
- HTTP: HttpClient + interceptors
- Database: PostgreSQL 16 (via REST API)
- Infrastructure: Docker, Nginx

## Coding Standards
- Linter: ESLint with angular-eslint + typescript-eslint
- Formatter: Prettier (.prettierrc)
- Naming: camelCase for variables/functions, PascalCase for classes/components
- Max function length: 40 lines
- Max nesting depth: 3 levels
- Standalone components only, no NgModules for new code
- Use Signals for reactive state, OnPush change detection
- One component per file, colocate template/styles/spec

## Testing
- Minimum coverage: 80%
- Required: unit tests for services and business logic
- Required: component tests for UI interactions
- Required: integration tests for API contracts
- Framework: Jest / Vitest + Angular Testing Library
- E2E: Playwright / Cypress

## Constraints
- Standalone components and directives only
- Bundle size budget: 250 KB gzipped (initial load)
- Lazy-load all feature routes
- No direct DOM manipulation — use Renderer2 or directives
- All API calls through centralized service with interceptors

## Security
- Authorization: JWT tokens via HttpInterceptor (httpOnly cookies)
- Input validation: Angular reactive forms with custom validators
- Secrets: environment.ts (never committed), Angular CLI environments
- XSS: no [innerHTML] without DomSanitizer
- CSRF: HttpClient XSRF support enabled

## LLM Rules
- Do not leave stubs without explicit TODO with justification
- Do not duplicate code: prefer reuse and clear abstractions
- Do not make hidden assumptions — if unsure, ask
- Always generate AI_NOTES.md per template
- Follow the coding style described above
- Use dependency injection idiomatically, avoid manual instantiation
- Prefer Signals over RxJS for simple state; use RxJS for streams