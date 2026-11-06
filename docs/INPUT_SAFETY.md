# Samhus input safety: current prototype limits

These are experimental guards, not a hardened compiler or a security sandbox.

| Resource | Default ceiling |
| --- | ---: |
| Source code characters | 1,000,000 |
| Lexer tokens | 250,000 |
| Numeric literal characters | 4,096 |
| String literal characters | 100,000 |
| Expression parse nesting | 160 |

Exceeded resources should raise a SamhusError with source position rather
than a Python-host exception. Numeric limit also avoids Python integer
string conversion failures for very long decimal literal inputs.

These are character counts and AST recursion limits, not byte/CPU/heap
budgets. Token allocation, nested structures and output still consume
host memory. These safeguards do NOT make untrusted source safe to execute.

Outstanding: wall-time limits, execution heap/output quotas, fuzzing,
sanitizers, native C backend safety reviews, dependency auditing, secure
FFI/unsafe boundary, threat modeling and independent penetration testing.

Run: python -m unittest discover -s tests -v
See tests/test_input_hardening.py for adversarial regression cases.