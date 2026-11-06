# Samhus Map and JSON bridge — experimental 0.0.8

This feature is experimental and available in the Python-hosted tree
interpreter and bytecode VM. It has NOT been approved as permanent syntax.
The restricted native C11 compiler does not support these structures.

## New language operations

- Map literals: {"name": "Samhus", "count": 42}, empty {}.
- Map types: Map[String,Int], Map[String,List[Int]], Map[String,Any].
- Map indexing: data["name"]. Missing keys produce Samhus errors.
- map_set(map,key,value): persistent update, returns a new Map.
- map_has(map,key): Bool; map_keys(map): List[String].
- len(map): number of Map entries.
- Immutable order-preserving Maps and deep structural equality.
- All keys must be String; duplicate literal keys are rejected.

## Strict JSON bridge

- json_parse(String) -> Any converts JSON objects to Map and arrays to List.
- json_encode(Any) -> String converts typed primitives, Lists and Maps.
- JSON null maps to explicit Null, distinct from Unit (experimental 0.0.9).
- Finite fractional JSON values map to Float (introduced in 0.0.9).
- json_valid checks JSON syntax. It can accept a syntactically valid but
  non-finite numeric exponent that json_parse rejects.
- Object duplicate keys and NaN/Infinity constants are rejected.
- Input/output size limit: 1,000,000 UTF-8 bytes.
- JSON depth limit: 64; node budget: 100,000.
- Map size limit: 100,000 keys; List limit: 100,000 items.

## Example

    fn main() -> Unit {
        let data = json_parse("{\"name\":\"Alsamos\",\"scores\":[10,20]}")
        println(data["scores"][1])
        println(json_encode(data))
    }

## Current limitations

This is not AI inference, validation against user-provided schemas,
a complete memory-safe runtime, or a security sandbox. Deeply nested
untrusted Samhus expressions may still exhaust Python runtime resources.
No modules, native Map/Float compilation or streaming JSON yet.

Unicode hardening: json_parse and json_encode reject unpaired UTF-16
surrogates, reporting Samhus errors instead of host encoding exceptions.

Update for 0.0.9: JSON fractional numbers parse to finite Float; JSON
null maps to Null. The earlier fractional-number rejection no longer applies.
