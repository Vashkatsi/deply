# File architecture context

- Add `context --file PATH [--config PATH] [--report-format json]` with JSON stdout.
- Reuse the full configured analysis; retain only direct edges incident to the file.
- Return collected elements with all memberships, applicable effective rules and their
  existing IDs, incoming/outgoing edges, related unsuppressed violations, and status.
- Preserve analysis JSON and baseline identities. No resolver changes, transitive
  impact, external dependency graph, output files, MCP, or automatic fixes.
- Distinguish excluded, outside-scope, missing, unmapped and failed files. Successful
  mapped context exits 0 even with violations; unavailable/incomplete context exits 1.
- Cover the public CLI, deterministic output, overlapping layers, incoming edges,
  shared identities, invalid config and partial analysis using unittest.
- Update README, CLI documentation and Agent Skill; run focused tests, make check,
  CI coverage gates, independent review, then commit and create a PR.

The graph covers statically resolved collected elements only. An empty edge list
does not prove runtime isolation. Full-project analysis is necessary for incoming
edges; file selection filters output, not the scan.
