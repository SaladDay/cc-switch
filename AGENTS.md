# Agent instructions

## Project contribution policy

Follow the project's [Pull Request Guidelines] and [AI-Assisted Contributions]
policy before changing the repository. `CONTRIBUTING.md` is the human-facing
source of truth. This file only turns those rules into deterministic agent
gates; it does not create or relax requirements for human contributors.
For vulnerability-related work, also follow the [Security Policy].

[Pull Request Guidelines]: ./CONTRIBUTING.md#pull-request-guidelines
[AI-Assisted Contributions]: ./CONTRIBUTING.md#ai-assisted-contributions
[Security Policy]: ./SECURITY.md

## Before editing

1. Read both policy sections linked above.
2. Determine whether the proposed work requires prior maintainer confirmation:
   - First-time code contributors require confirmation before writing code. If
     contributor status is unknown, determine it from available repository or
     account context, or ask before proceeding; do not assume either status.
   - New managed applications, provider families, protocol bridges, harness
     integrations, and comparable long-lived integrations require confirmation
     regardless of contributor history.
3. Locate the issue, or the private advisory for security work, and a maintainer
   response that explicitly confirms the direction and scope. A report without
   that confirmation is not approval to implement. Never disclose vulnerability
   details in a public issue.
4. If required confirmation is missing, do not implement the covered code
   change or prepare its pull-request-ready patch. You may investigate, review
   existing code, or help prepare an issue or design proposal when asked.
5. Once the work is confirmed, keep the implementation inside the agreed scope
   and non-goals. Do not add unrelated refactors, speculative compatibility
   layers, or extra feature surface.
