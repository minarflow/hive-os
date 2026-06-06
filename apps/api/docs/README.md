# Hive OS Documentation Map

Hive OS is a Team Mode, app-level multi-user Hermes PWA for a Linux server. These docs define the safety contract for future Hermes/Claude Code work.

## Start here

1. [Architecture and trust boundaries](./architecture.md)
2. [Development setup and tools](./development/setup.md)
3. [Package installation policy](./development/package-policy.md)
4. [Security model](./security/security-model.md)
5. [Runner policy](./security/runner-policy.md)
6. [Prompt injection hardening](./security/prompt-injection.md)
7. [Repository/project access controls](./operations/repository-access.md)

## Core principle

Physical access is not the same as app authorization.

People with AnyDesk, shell, sudo, or direct filesystem access may be able to see files physically. Hive OS still must enforce app-level policy so that:

- app users only see projects they are allowed to see;
- prompts and injected text cannot freely browse source code, hidden files, secrets, or unrelated projects;
- runners only operate inside the project/session policy they were granted;
- admin powers are explicit and audited;
- source code visibility is intentional, not accidental.

## Documentation ownership

- Update `docs/security/*` whenever runner behavior, file access, auth, permissions, or prompt handling changes.
- Update `docs/development/*` whenever dependency, install, test, or local workflow changes.
- Update `docs/operations/*` whenever user/project/repo enablement changes.
- Never document secrets, token values, private keys, or production credentials.
