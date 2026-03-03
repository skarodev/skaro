You are a senior software architect analyzing an existing codebase.

Your task is to produce an **Architecture** document — a description of the project's structure, components, and design.

## Project

Name: {project_name}

## Project Constitution (already generated from full source code)

{constitution}

## Repository Structure

```
{tree}
```

---

Based on the project constitution (which was generated from the full source code) and the directory tree above, write a filled-in Architecture document.

Follow this structure:

```
# Architecture: {project_name}

## Overview
<Architectural style: monolith / microservices / modular monolith / serverless>

## Components
<Main components / modules / services and their responsibilities>

## Data Storage
<Databases, caches, file storage — what and why>

## Communication
<REST / gRPC / GraphQL / message broker / events — what you observe>

## Infrastructure
<Deployment, CI/CD, monitoring — what you detect>

## External Integrations
<Third-party services or APIs found in the code>

## Security
<Authentication, authorization, data protection patterns>

## Known Trade-offs
<Trade-offs visible from the code or commented in it>
```

Replace every placeholder with what you observe. If something is genuinely not detectable, write "not detected".

IMPORTANT: Return ONLY the architecture document. Do not wrap it in a code fence. Do not add preambles or explanations.
