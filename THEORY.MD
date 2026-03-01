# Theory: ODR as Multi-Lens Document Intelligence

## Problem

Documents get reviewed by one person at a time, through one lens. A technical writer catches grammar issues but misses logical gaps. A domain expert catches factual errors but ignores readability. An editor tightens prose but doesn't question assumptions. The feedback is serial, narrow, and slow.

AI reviewers can run in parallel with different expertise, but the naive approach — throwing five LLM personas at a document — creates a new problem: redundancy and noise. Five reviewers all flag the same dense paragraph. Three of them nitpick the same formatting issue. The user drowns in volume instead of gaining clarity.

The structural challenge isn't "how to get AI feedback on documents." It's how to synthesize multiple critical perspectives into a coherent, actionable signal that's greater than the sum of its parts.

## Operating Theory

ODR works because document review is fundamentally a multi-perspective problem, and LLMs are genuinely good at adopting focused critical lenses when properly constrained. The key dynamics:

**Persona constraint produces differentiated output.** A reviewer told to focus on logical structure with a specific tone and severity level produces meaningfully different feedback than one focused on clarity or domain accuracy. The persona schema (system prompt, focus areas, output requirements, reference notes, examples) is the primary lever for review quality.

**Anchor-based feedback preserves context.** Comments linked to specific document sections via text anchoring are fundamentally more useful than general feedback. The highlight-to-comment visual connector makes the relationship between critique and source text immediate.

**The meta-critic is the multiplier.** Individual reviewer output has diminishing returns past 3-4 personas — they start overlapping. The meta-critic layer transforms raw reviewer output into structured insight: deduplicating overlapping concerns, surfacing consensus signals, and grouping feedback into actionable themes. If five reviewers flag density in section 3, the user hears "Section 3 is too dense" once, with drill-down access to each reviewer's specific evidence.

**The API/frontend split is architectural, not incidental.** The review engine, persona management, and document storage are a platform. The web UI is one consumer. A CLI, mobile apps, and third-party integrations are equally valid frontends. This means the API surface is the real product boundary — the frontend is a reference implementation.

## Strategy

The work follows three interconnected tracks:

**Track 1: Review engine depth.** The persona schema is richer than what the prompt builder currently uses. Phase 2 of the agent roadmap — making the prompt builder honor output_requirements, reference_notes, and examples consistently — is the highest-leverage work. A well-constrained persona with enforced output contracts produces dramatically better reviews than a loosely prompted one. This is where review quality lives.

**Track 2: Meta-critic intelligence.** The initial meta-critic exists but needs to become the primary user-facing synthesis layer. The UX should lead with the meta-critic's grouped findings, with per-reviewer detail as drill-down. This inverts the current flow (reviewer comments first, meta-summary second) and makes the tool scale to more personas without overwhelming the user.

**Track 3: Platform hardening.** Multi-tenant isolation, OIDC auth, the storage layer beneath documents and reviews — these enable the tool to serve teams and groups, not just individuals. The split between API and frontend is already clean; the remaining work is making the backend robust enough that multiple frontends (web, CLI, mobile) can trust it as a reliable service.

## Key Discoveries

**Persona design is more craft than engineering.** The Nielsen persona experiment (a writing critic based on Michael Nielsen's essay on writing well, configured with specific severity, bullet limits, and an amber theme) showed that highly opinionated, well-constrained reviewers produce the most useful feedback. Generic "writing assistant" personas produce generic output. The best reviewers have a clear editorial voice.

**Deslop as a reviewer persona validates the architecture.** Issue #42 proposes AI writing pattern detection (slop scoring) as both a diagnostic reviewer persona and a "humanize" action. The fact that this fits naturally as a persona — not a separate feature — confirms the persona system is the right abstraction. Any critical lens that can be expressed as a system prompt, focus areas, and output requirements can become a reviewer.

**The CORS/security hardening was necessary but not the point.** The recent security audit and hardening (CSRF guards, rate limiting, tenant path hardening) were important for production readiness but didn't change the product theory. They're infrastructure, not product.

## Open Questions

**How sophisticated should the meta-critic be?** Simple deduplication and grouping is a starting point, but the meta-critic could also identify contradictions between reviewers, weight consensus by reviewer expertise, or flag when all reviewers missed something obvious. How far should this go?

**What's the right number of default personas?** Too few and the tool feels thin. Too many and users are overwhelmed before they customize. The current defaults plus Nielsen-style opinionated additions need a curation pass.

**Should personas be shareable?** If ODR serves teams, persona configurations become a form of institutional knowledge — "this is how our org reviews RFCs." Export/import/marketplace for persona bundles could be valuable but adds complexity.

**How does the storage layer evolve?** Git-backed document history works for single-instance use. Multi-user concurrent editing, versioning across teams, and mobile sync push toward a more sophisticated backend. The current SQLite + git approach will need to be revisited for real multi-user deployment.

**What does the CLI look like?** The API is ready for non-web consumers. A CLI that pipes documents through ODR and returns structured feedback would unlock CI/CD integration (review docs on PR), editor plugins, and agent workflows. The interface design matters — JSON output for machines, formatted output for humans.
