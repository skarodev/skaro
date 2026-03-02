# Constitution: <project name>

## Stack
- Language: Kotlin 2.1+
- Framework: Kotlin Multiplatform (KMP)
- Targets: Android, iOS, Desktop (JVM), Web (Wasm/JS)
- UI: Compose Multiplatform
- Networking: Ktor Client
- Serialization: kotlinx.serialization
- DI: Koin / Kodein
- Database: SQLDelight (local), PostgreSQL (backend)
- Infrastructure: GitHub Actions, Fastlane (mobile)

## Coding Standards
- Linter: Detekt (detekt.yml)
- Formatter: ktlint
- Naming: camelCase for variables/functions, PascalCase for classes
- Max function length: 40 lines
- Max nesting depth: 3 levels
- Architecture: Clean Architecture (data, domain, presentation per target)
- Shared code in commonMain, platform-specific in androidMain/iosMain/etc.
- Use expect/actual only when necessary, prefer interfaces

## Testing
- Minimum coverage: 80%
- Required: unit tests for shared business logic (commonTest)
- Required: platform integration tests per target
- Required: UI tests for critical flows
- Framework: kotlin.test + Turbine (flows) + MockK
- Use commonTest for maximum test sharing across platforms

## Constraints
- Maximize shared code in commonMain (target 80%+)
- No platform-specific code in domain layer
- All network calls through Ktor client abstraction
- Expect/actual declarations only in data/platform layers
- Compose Multiplatform for all UI, native views only when required

## Security
- Authorization: JWT tokens stored in platform-secure storage
- Input validation: shared validation layer in commonMain
- Secrets: BuildConfig / local.properties (never committed)
- Certificate pinning: per-platform Ktor engine configuration
- No sensitive data in shared preferences / UserDefaults

## LLM Rules
- Do not leave stubs without explicit TODO with justification
- Do not duplicate code: prefer reuse and clear abstractions
- Do not make hidden assumptions — if unsure, ask
- Always generate AI_NOTES.md per template
- Follow the coding style described above
- Prefer coroutines and Flow over callbacks
- Keep expect/actual surface minimal — prefer dependency injection