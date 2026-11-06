# Immutable List research prototype 0.0.7

Samhus List is an experimental feature, not an approved permanent language
design. It works in the tree interpreter and bytecode VM, not native C11.

## Grammar and features

- Literals: [], [1, 2, 3], [[1], [2]].
- Type annotations: List[Int], List[String], List[Bool], List[Any],
  recursive List[List[Int]] and other nested types.
- Indexing: values[0] and matrix[1][0], checked and zero-based.
- String indexes return one Unicode code point as a String.
- len(list) returns number of elements.
- append(list, value) returns a NEW immutable list; no mutation.
- Deep list equality, including true != 1 even inside nested lists.
- Type-safe literal checking against known List element annotations.
- List[Any] supports heterogeneous lists; [] is compatible with typed lists.

## Correctness and safety limits

- Negative and out-of-bounds indexes produce source-positioned Samhus errors.
- Indexing non-collections and using non-Int indexes is rejected.
- Prototype maximum 100000 list items; not a complete memory quota.
- Internal representation uses Python tuples in both experimental runtimes.
- No stable ABI, complete generics, memory-safety proof or sandbox.
- Deeply nested untrusted programs may still exhaust host resources.
- Native C11 subset intentionally rejects List syntax.
- This is a step toward data/AI workflows, not tensor, GPU, or ML support.

## Example

~~~sahu
fn sum(values: List[Int]) -> Int {
    var total: Int = 0
    var i: Int = 0
    while i < len(values) {
        total = total + values[i]
        i = i + 1
    }
    return total
}

fn main() -> Unit {
    let scores: List[Int] = [12, 18, 27]
    let updated: List[Int] = append(scores, 43)
    println(sum(updated))
    println(scores)
}
~~~

Output: 100 followed by [12, 18, 27].
