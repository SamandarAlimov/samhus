"""Repeatable microbenchmarks for Samhus *prototype* execution engines.

Not a C++/Python 3.13 benchmark. No native backend exists yet.
"""
import argparse
import json
import statistics
import time

from samhus.runtime import run_to_string
from samhus.vm import run_vm_to_string


PROGRAMS = {
    "arithmetic": """fn compute(n: Int) -> Int {
    var i: Int = 0
    var total: Int = 0
    while i < n {
        total = total + i * 7 / 3
        i = i + 1
    }
    return total
}
fn main() { println(compute(800)) }
""",
    "recursive": """fn fibonacci(n: Int) -> Int {
    if n <= 1 { return n }
    return fibonacci(n-1) + fibonacci(n-2)
}
fn main() { println(fibonacci(16)) }
""",
    "strings": """fn main() {
    var i: Int = 0
    var text: String = ""
    while i < 150 {
        text = text + "a"
        i = i + 1
    }
    println(text)
}
""",
}


def benchmark(repeat: int = 5) -> list[dict[str, object]]:
    if repeat < 1:
        raise ValueError("repeat must be positive")
    results: list[dict[str, object]] = []
    for label, program in PROGRAMS.items():
        reference = run_to_string(program)
        if run_vm_to_string(program) != reference:
            raise RuntimeError(f"{label}: VM output differs from tree backend")
        for backend, runner in (("tree", run_to_string), ("vm", run_vm_to_string)):
            durations = []
            for _ in range(repeat):
                start = time.perf_counter()
                result = runner(program)
                durations.append((time.perf_counter() - start) * 1000)
                if result != reference:
                    raise RuntimeError(f"{label}/{backend}: result changed between runs")
            results.append({
                "program": label, "backend": backend, "repetitions": repeat,
                "median_ms": round(statistics.median(durations), 3),
                "minimum_ms": round(min(durations), 3),
                "output_verified": True,
            })
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps({
        "warning": "Prototype microbenchmarks; not C++ or CPython comparison",
        "measurements": benchmark(args.repeat),
    }, indent=2))
