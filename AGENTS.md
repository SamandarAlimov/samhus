# Instructions for agents working on Samhus

1. **The language name is Samhus.** Do not rename it or seek a new name.
2. .sahu is a **provisional** extension, not an approved permanent standard. Do not silently finalize it.
3. Language semantics, implementation language, licensing, open-source policy, and release targets must not be presented as founder-approved unless recorded in docs/DECISIONS.md with explicit approval.
4. This repository is a separate research project. Never modify Alsamos Superapp, the existing Lovable Cloud backend, or other repositories as part of Samhus work.
5. Prefer small, testable, reversible increments. Do not claim the proof of concept is a production compiler.
6. Add a regression test when fixing a language bug. Run 'python -m unittest discover -s tests -v' and document what ran.
7. Keep the language specification aligned with actual behavior. Distinguish implemented behavior from proposals.
8. Preserve public API compatibility where reasonable; discuss breaking changes before versions are released.
9. Never commit secrets, user data, private keys, or copyrighted third-party code without authorization.
10. Keep the CLI and examples working and update README whenever usage changes.

11. Prefer proof-oriented milestone work over merely increasing versions or
    collecting builtins. See docs/ENGINEERING_MASTERPLAN.md and the threat model.
12. Treat untrusted source as hostile; never call a parser guard a sandbox.
    Record failing examples and prevent Python host exceptions from leaking.
13. Before claiming a stage complete, verify the latest commit CI on all
    six jobs (Ubuntu/Windows/macOS x Python 3.11/3.13).

14. The bootstrap version is `0.0.0.dev0` until the owner approves
    an official release. See docs/RELEASE_POLICY.md. Do not bump version
    merely because functionality, tests or documentation changed.
