Analyze this technical specification and extract ALL requirements of EVERY type.

For each requirement, output EXACTLY in this format:

### REQ_ID: {Short Title}
**Type:** {TYPE}

{Detailed description of the requirement in 1-3 sentences}

**Acceptance Criteria:**
- {criterion 1}
- {criterion 2}
- {criterion 3}

---

Requirement TYPES (use exactly these labels):
- **FR** — Functional Requirement: what the system must DO (user actions, business logic, workflows)
- **NFR** — Non-Functional Requirement: how the system must PERFORM (speed, security, availability, scalability)
- **IR** — Integration Requirement: external systems, APIs, data exchange protocols
- **DR** — Data Requirement: storage structure, data models, migrations, validation rules
- **BR** — Business Rule: business logic constraints, calculation formulas, workflows
- **CR** — Compliance Requirement: regulatory, legal, standards compliance
- **UR** — UI/UX Requirement: interface behavior, layout, accessibility

Extract EVERYTHING from the specification:
- Explicit requirements (directly stated)
- Implicit requirements (implied by context)
- Constraints and limitations
- Non-functional characteristics mentioned in any section
- Data models and structures
- Integration points
- Security and access control rules

Be extremely thorough. More requirements is better — you can refine later.
Use sequential IDs starting from FR-001.

Return ONLY the requirements list. No preamble. No markdown fences.