"""Map/JSON language conformance and defensive data-boundary regression tests."""
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from samhus import SamhusError, parse_program, run_to_string
from samhus.bytecode import compile_source
from samhus.formatter import format_program
from samhus.json_bridge import decode_json, encode_json
from samhus.lexer import Token
from samhus.native_c import emit_c
from samhus.typecheck import check_types
from samhus.values import MapValue, accepts, map_value, structural_equal, type_name
from samhus.vm import run_vm_to_string


def src(body):
    return "fn main() {\n" + body + "\n}"


def execute(engine, source):
    try:
        return ("ok", engine(source))
    except SamhusError as exc:
        return ("error", str(exc))


class MapsAndJSONTests(unittest.TestCase):
    def both(self, source, output=None, *, static=True):
        if static:
            check_types(source)
        left = execute(run_to_string, source)
        right = execute(run_vm_to_string, source)
        self.assertEqual(left, right, "Tree/VM mismatch for:\n" + source)
        if output is not None:
            self.assertEqual(left, ("ok", output))
        return left

    def runtime_failure(self, source, message):
        result = self.both(source, static=False)
        self.assertEqual(result[0], "error", result)
        self.assertIn(message, result[1])

    def static_failure(self, source, message):
        with self.assertRaises(SamhusError) as ctx:
            check_types(source)
        self.assertIn(message, str(ctx.exception))

    def test_empty_map(self):
        self.both(src('let m: Map[String, Int] = {}; println(m)'), "{}\n")

    def test_basic_map(self):
        self.both(src('let m: Map[String, Int] = {"a": 10, "b": 20}; println(m["b"])'), "20\n")

    def test_unicode_keys(self):
        self.both(src('let m: Map[String, String] = {"til": "Samhus", "🇺🇿": "Uzbek"}; println(m["🇺🇿"])'), "Uzbek\n")

    def test_nested_map(self):
        self.both(src('let m: Map[String, Map[String, Int]] = {"meta": {"count": 7}}; println(m["meta"]["count"])'), "7\n")

    def test_map_in_list(self):
        self.both(src('let a: List[Map[String, Int]] = [{"x": 1}, {"x": 2}]; println(a[1]["x"])'), "2\n")

    def test_list_in_map(self):
        self.both(src('let m: Map[String, List[Int]] = {"scores": [7,9]}; println(m["scores"][1])'), "9\n")

    def test_mixed_map(self):
        self.both(src('let m: Map[String, Any] = {"ok": true, "score": 9, "label": "AI"}; println(m)'),
                  '{"ok": true, "score": 9, "label": "AI"}\n')

    def test_len(self):
        self.both(src('println(len({})); println(len({"x":1, "y":2}))'), "0\n2\n")

    def test_map_has(self):
        self.both(src('let m: Map[String,Int]={"x":1}; println(map_has(m,"x")); println(map_has(m,"y"))'),
                  "true\nfalse\n")

    def test_map_keys(self):
        self.both(src('let m: Map[String,Int]={"a":1,"b":2}; println(map_keys(m))'), '["a", "b"]\n')

    def test_map_set_add(self):
        self.both(src('let m: Map[String,Int]={"x":1}; let n: Map[String,Int]=map_set(m,"y",2); println(m); println(n)'),
                  '{"x": 1}\n{"x": 1, "y": 2}\n')

    def test_map_set_replace(self):
        self.both(src('let m: Map[String,Int]={"x":1,"y":2}; println(map_set(m,"x",7))'),
                  '{"x": 7, "y": 2}\n')

    def test_map_set_existing_immutability(self):
        self.both(src('let m: Map[String,Int]={"x":1}; let n=map_set(m,"x",2); println(m["x"]); println(n["x"])'),
                  "1\n2\n")

    def test_map_set_mixed_dynamic(self):
        self.both(src('let m: Map[String,Any]={"x":1}; println(map_set(m,"x","text"))'), '{"x": "text"}\n')

    def test_map_set_typed_wrong(self):
        self.static_failure(src('let m: Map[String,Int]={"x":1}; println(map_set(m,"x","bad"))'), "expected Int, got String")

    def test_map_set_typed_wrong_runtime(self):
        self.runtime_failure(src('var m: Map[String,Int]={"x":1}; m=map_set(m,"x","bad")'),
                             "expected Map[String,Int]")

    def test_map_index_invalid_int(self):
        self.static_failure(src('println({"a":1}[0])'), "expected String, got Int")
        self.runtime_failure(src('println({"a":1}[0])'), "Map index must be String")

    def test_missing_map_key(self):
        self.runtime_failure(src('println({"a":1}["b"])'), "Missing map key")

    def test_duplicate_key_literal(self):
        self.runtime_failure(src('println({"a":1, "a":2})'), "Duplicate map key")

    def test_nonstring_key(self):
        self.static_failure(src('println({1: "bad"})'), "expected String, got Int")
        self.runtime_failure(src('println({1: "bad"})'), "Map key must be String")

    def test_map_equality_order_independent(self):
        self.both(src('println({"a":1, "b":2} == {"b":2, "a":1})'), "true\n")

    def test_deep_equality_and_bool_int(self):
        self.both(src('println({"a":[true]}=={"a":[1]}); println({"a":[2]} != {"a":[2]})'),
                  "false\nfalse\n")

    def test_empty_typed_nested_map(self):
        self.both(src('let x: Map[String, List[Int]]={}; println(x)'), "{}\n")

    def test_deep_typed_literal_failure(self):
        self.static_failure(src('let m: Map[String,List[Int]]={"a":[1,"no"]}'), "expected Int, got String")

    def test_typed_function(self):
        self.both('fn read(m: Map[String,Int]) -> Int {return m["score"]}\n'
                  'fn main() -> Unit {println(read({"score":42}))}', "42\n")

    def test_typed_function_error(self):
        self.static_failure('fn read(m: Map[String,Int])->Int{return m["score"]}\n'
                            'fn main(){read({"score":"bad"})}', "expected Int, got String")

    def test_typed_return(self):
        self.both('fn make()->Map[String,Int]{return {"ok":1}}\nfn main(){println(make()["ok"])}', "1\n")

    def test_type_name_helpers(self):
        token = Token("TEST", "", 1, 1)
        m=map_value((("x",1),("y",2)),token)
        self.assertEqual(type_name(m),"Map[String,Int]")
        self.assertTrue(accepts("Map[String,Int]",m))
        self.assertFalse(accepts("Map[String,String]",m))
        self.assertTrue(structural_equal(m,map_value((("y",2),("x",1)),token)))

    def test_bad_type_annotation(self):
        with self.assertRaisesRegex(SamhusError, "Map key type must be String"):
            parse_program(src("let m: Map[Int, String]={}"))

    def test_map_type_depth_bound(self):
        nested="Map[String,"*26+"Int"+"]"*26
        with self.assertRaisesRegex(SamhusError, "maximum depth"):
            parse_program(src(f"let m: {nested}={{}}"))

    def test_map_ast(self):
        p=parse_program(src('println({"x":[1,2]}["x"][1])'))
        self.assertEqual(p.functions[0].body[0].expr.args[0].kind,"index")

    def test_formatter_roundtrip(self):
        source=src('let m:Map[String,List[Int]]={"a":[1,2],"b":[3]};println(m["a"][1])')
        formatted=format_program(source)
        self.assertEqual(format_program(formatted),formatted)
        self.assertEqual(run_to_string(source),run_to_string(formatted))
        self.assertEqual(run_vm_to_string(source),run_vm_to_string(formatted))

    def test_disassembly(self):
        data=compile_source(src('println({"a":1}["a"])')).disassemble()
        self.assertIn("BUILD_MAP 1",data)
        self.assertIn("INDEX",data)

    def test_native_rejection(self):
        with self.assertRaisesRegex(SamhusError, "Native subset"):
            emit_c('fn main()->Unit{println({"x":1})}')

    def test_json_parse_string_field(self):
        self.both(src(r'let obj = json_parse("{\"model\":\"Alsamos\",\"ok\":true}"); println(obj["model"])'),
                  "Alsamos\n")

    def test_json_parse_nested_field(self):
        self.both(src(r'let data = json_parse("{\"scores\":[1,2,3]}"); println(data["scores"][1])'),
                  "2\n")

    def test_json_parse_null(self):
        self.both(src('println(json_encode(json_parse("null")))'), "null\n")

    def test_json_encode_object(self):
        self.both(src('println(json_encode({"x":1,"ready":true}))'), '{"x":1,"ready":true}\n')

    def test_json_encode_list(self):
        self.both(src('println(json_encode([1,true,"ok"]))'), '[1,true,"ok"]\n')

    def test_json_roundtrip(self):
        self.both(src(r'println(json_encode(json_parse("{\"name\":\"AI\",\"nums\":[1,2]}")))'),
                  '{"name":"AI","nums":[1,2]}\n')

    def test_json_unicode(self):
        self.both(src('println(json_encode({"country":"Oʻzbekiston","emoji":"🙂"}))'),
                  '{"country":"Oʻzbekiston","emoji":"🙂"}\n')

    def test_json_invalid(self):
        self.runtime_failure(src('json_parse("{broken")'), "Invalid JSON")

    def test_json_reject_duplicate(self):
        self.runtime_failure(src(r'json_parse("{\"x\":1,\"x\":2}")'), "Duplicate map key")

    def test_json_reject_float(self):
        self.runtime_failure(src('json_parse("1.5")'), "fractional JSON numbers")

    def test_json_reject_nan(self):
        self.runtime_failure(src('json_parse("NaN")'), "nonstandard numeric constant")

    def test_json_reject_infinity(self):
        self.runtime_failure(src('json_parse("Infinity")'), "nonstandard numeric constant")

    def test_json_valid_different_from_parse(self):
        # JSON syntax validity can be true even where Float support is missing.
        self.both(src('println(json_valid("1.5"))'), "true\n")

    def test_json_typed_assignment_runtime(self):
        self.both(src(r'let m: Map[String, Int] = json_parse("{\"count\":42}"); println(m["count"])'),
                  "42\n")

    def test_json_wrong_typed_assignment(self):
        self.runtime_failure(src(r'let m: Map[String, Int] = json_parse("{\"count\":\"oops\"}")'),
                             "expected Map[String,Int]")

    def test_json_decode_str_type(self):
        self.static_failure(src("json_parse(42)"), "expected String, got Int")
        self.runtime_failure(src("json_parse(42)"), "expected String, got Int")

    def test_json_encode_unit(self):
        self.both(src('println(json_encode(assert(true)))'), "null\n")

    def test_json_encode_dynamic_nested(self):
        self.both(src(r'let d=json_parse("{\"a\":[{\"b\":true}]}"); println(json_encode(d))'),
                  '{"a":[{"b":true}]}\n')

    def test_malformed_map_key_type_return(self):
        self.runtime_failure(src('println({"x":1}[true])'), "Map index must be String")

    def test_map_builtin_invalid_target(self):
        self.runtime_failure(src('map_set(5,"x",1)'), "map_set expects Map")
        self.runtime_failure(src('map_has(5,"x")'), "map_has expects Map")
        self.runtime_failure(src('map_keys(5)'), "map_keys expects Map")

    def test_map_missing_builtin_arity(self):
        self.static_failure(src('map_set({},"a")'), "expects 3 arguments")
        self.runtime_failure(src('map_has({})'), "expects 2 arguments")

    def test_json_rejects_escaped_surrogate(self):
        token = Token("TEST", "", 1, 1)
        with self.assertRaisesRegex(SamhusError, "unpaired Unicode surrogate"):
            decode_json(r'"\ud800"', token)

    def test_json_rejects_escaped_surrogate_object_key(self):
        token = Token("TEST", "", 1, 1)
        with self.assertRaisesRegex(SamhusError, "unpaired Unicode surrogate"):
            decode_json(r'{"\ud800":1}', token)

    def test_json_rejects_direct_surrogate_text(self):
        token = Token("TEST", "", 1, 1)
        with self.assertRaisesRegex(SamhusError, "unpaired Unicode surrogate"):
            decode_json('"' + chr(0xd800) + '"', token)

    def test_json_encode_rejects_surrogate_value(self):
        token = Token("TEST", "", 1, 1)
        with self.assertRaisesRegex(SamhusError, "unpaired Unicode surrogate"):
            encode_json(chr(0xd800), token)

    def test_json_encode_rejects_surrogate_map_key(self):
        token = Token("TEST", "", 1, 1)
        with self.assertRaisesRegex(SamhusError, "unpaired Unicode surrogate"):
            encode_json(MapValue(((chr(0xd800),1),)), token)

    def test_json_size_limit(self):
        t=Token("TEST","",1,1)
        with patch("samhus.json_bridge.MAX_JSON_BYTES",20):
            with self.assertRaisesRegex(SamhusError, "byte limit"):
                decode_json('"'+"x"*30+'"',t)

    def test_json_depth_limit(self):
        t=Token("TEST","",1,1)
        with patch("samhus.json_bridge.MAX_JSON_DEPTH",3):
            with self.assertRaisesRegex(SamhusError, "resource limits"):
                decode_json("[[[[1]]]]",t)

    def test_json_output_limit(self):
        t=Token("TEST","",1,1)
        with patch("samhus.json_bridge.MAX_JSON_BYTES",5):
            with self.assertRaisesRegex(SamhusError, "byte limit"):
                encode_json((1,2,3),t)

    def test_json_node_limit(self):
        t=Token("TEST","",1,1)
        with patch("samhus.json_bridge.MAX_JSON_NODES",2):
            with self.assertRaisesRegex(SamhusError, "resource limits"):
                decode_json("[1,2,3]",t)

    def test_map_size_limit(self):
        token=Token("TEST","",1,1)
        with patch("samhus.values.MAX_MAP_ITEMS",1):
            with self.assertRaisesRegex(SamhusError, "Map size limit"):
                map_value((("x",1),("y",2)),token)

    def test_100_random_map_indices(self):
        rng=random.Random(12298)
        for n in range(100):
            count=rng.randint(1,12)
            values=[rng.randint(-1000,1000) for _ in range(count)]
            key=rng.randrange(count)
            pairs=",".join(f'"k{i}":({v})' for i,v in enumerate(values))
            self.both(src(f'let m: Map[String,Int] = {{{pairs}}}; println(m["k{key}"])'),
                      f"{values[key]}\n")

    def test_cli_integration(self):
        example=src(r'let d = json_parse("{\"metrics\":{\"score\":25}}"); println(d["metrics"]["score"])')
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"test.sahu"
            p.write_text(example,encoding="utf-8")
            for backend in ("tree","vm"):
                run=subprocess.run([sys.executable,"-m","samhus","run",str(p),
                                    "--typecheck","--backend",backend],
                                   text=True,capture_output=True,encoding="utf-8")
                self.assertEqual(run.returncode,0,run.stderr)
                self.assertEqual(run.stdout,"25\n")


if __name__=="__main__":
    unittest.main()
