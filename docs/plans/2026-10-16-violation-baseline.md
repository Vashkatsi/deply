# Violation baseline

- Reuse JSON v1 relationship identities in a shared serializer; preserve fingerprints.
- Add exclusive baseline creation and strict loading, then compare complete analyses.
- Expose new/existing/resolved diagnostics in JSON; other reports show new violations.
- Reject threshold combinations and output aliases; never overwrite accepted debt.
- Cover CLI behavior, malformed files, incomplete analysis, identity stability and formats.
- Update CLI docs, roadmap and Agent Skill adoption guidance.
- Run focused tests, make check, coverage gates and independent review; commit and open PR.

Baseline accepts relationships, not individual occurrences. Resolved means absent from
this complete configured analysis, not proof of a code fix. Creation explicitly accepts
current findings. Existing invocation behavior without baseline options stays unchanged.
