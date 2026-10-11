"""JSON response formats at the HTTP boundary: prompt once, validate before delivery.

The native engine has no grammar decoder. Failed generations are errors, never
silently retried or returned as successful structured output.

`jsonschema` is optional (no new hard dependency of the server): json_object needs only the standard library, and
json_schema is checked against its schema when the package is installed - without it, only that the answer is one
JSON object, and the server says so once.
"""
import json
import os
import threading


class StructuredOutputError(RuntimeError):
    pass


class _ObjectOnly:
    """The validator for json_object, and for json_schema without jsonschema: one JSON object."""

    def iter_errors(self, value):
        if not isinstance(value, dict):
            yield _ObjectError()


class _ObjectError:
    absolute_path = ()
    message = "the answer is not a JSON object"


_jsonschema = None                     # (validators, SchemaError, Registry, NoSuchResource), False when not installed
_jsonschema_lock = threading.Lock()


def jsonschema_modules():
    """jsonschema, imported on first use; None when it is not installed (said once, in the server window)."""
    global _jsonschema
    with _jsonschema_lock:
        if _jsonschema is None:
            try:
                from jsonschema import validators
                from jsonschema.exceptions import SchemaError
                from referencing import Registry
                from referencing.exceptions import NoSuchResource
                _jsonschema = (validators, SchemaError, Registry, NoSuchResource)
            except ImportError:
                _jsonschema = False
                print('[strata] response_format json_schema: the Python package jsonschema is not installed, so '
                      'answers are only checked to be one JSON object (python -m pip install "jsonschema>=4.23,<5")',
                      flush=True)
        return _jsonschema or None


def _only_objects(node, root, refs=()):
    """True when every value `node` accepts is a JSON object, so "return one JSON object" stays true.

    `type: object`, an anyOf/oneOf whose branches all qualify (e.g. a root union of object shapes, which llama.cpp's
    grammar path accepts and apps send), an allOf with a qualifying member, or a local `$ref` to one of these.
    Anything that can also be an array, string, number, boolean or null (including `type: ["object", "null"]`) is
    not, and a `$ref` cycle never qualifies.
    """
    if not isinstance(node, dict):
        return False
    if node.get("type") == "object":
        return True
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#") and ref not in refs:
        target = root
        for part in ref[1:].split("/")[1:]:
            part = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(target, dict) or part not in target:
                return False
            target = target[part]
        return _only_objects(target, root, refs + (ref,))
    for key in ("anyOf", "oneOf"):
        branches = node.get(key)
        if isinstance(branches, list) and branches and all(_only_objects(b, root, refs) for b in branches):
            return True
    branches = node.get("allOf")
    return isinstance(branches, list) and any(_only_objects(b, root, refs) for b in branches)


# a quantifier inside a quantifier ("(a+)+$") makes one match exponential in the text it fails on, and nothing in re
# bounds that; the shape is refused when the schema is checked.  STRATA_SAFE_SCHEMA_PATTERNS=0 accepts it anyway.

try:                                            # re's own parser, so the shape is read rather than guessed at
    from re import _parser as _re_parser
except ImportError:                             # Python 3.10
    try:
        import sre_parse as _re_parser
    except ImportError:
        _re_parser = None

_REPEATS = (_re_parser.MAX_REPEAT, _re_parser.MIN_REPEAT) if _re_parser else ()
_UNBOUNDED = _re_parser.MAXREPEAT if _re_parser else 0


def _nested_quantifier(pattern: str) -> bool:
    """True when `pattern` can take exponential time: a quantifier that can repeat without bound, holding another
    quantifier that can repeat at all - "(a+)+", "(\\w+\\s?)*", "([a-z]+)+".  A bounded outer repeat such as
    "(a+){2,3}" is only polynomial and is left alone, and so is an overlapping alternation with no quantifier inside
    it ("(a|aa)+"), which is slower but rarer in a schema.  A pattern that passes is therefore not proved fast; what
    this catches is the shape that turns one request into a core that never comes back."""
    if _re_parser is None:
        return False
    try:
        tree = _re_parser.parse(pattern)
    except Exception:                            # noqa: BLE001 - check_schema has already refused what re cannot compile
        return False
    return _inside_unbounded_repeat(tree)


def _parts(node):
    """The children of a parse-tree node.  re's SubPattern is iterable the old way - by __getitem__, with no
    __iter__ - so it is asked to iterate rather than tested for being a list; the literals and positions inside the
    tree are plain ints, which are not iterable at all."""
    if isinstance(node, (str, bytes, int, float)):
        return ()
    try:
        return tuple(node)
    except TypeError:                         # a leaf: an int, a flag, a position
        return ()


def _inside_unbounded_repeat(node, inside: bool = False) -> bool:
    """Walks re's own parse tree.  `inside` is set once we are below a repeat with no upper bound; a second repeat
    under it is the exponential shape.  A repeat is a (kind, (low, high, body)) pair; every other node - a group, a
    branch, a set - is just descended into, which keeps this working when the node shapes differ between versions."""
    if isinstance(node, tuple) and node and node[0] in _REPEATS and len(node) > 1 \
            and isinstance(node[1], tuple) and len(node[1]) > 2:
        low, high, body = node[1][0], node[1][1], node[1][2]
        if inside and high > 1 and high != low:
            return True
        return _inside_unbounded_repeat(body, inside or high == _UNBOUNDED)
    return any(_inside_unbounded_repeat(part, inside) for part in _parts(node))


def _patterns_of(node, seen: set | None = None):
    """Every regex a schema can compile: "pattern" values and "patternProperties" keys, anywhere in the tree - which
    covers $defs and definitions too, so a local $ref cannot hide one."""
    seen = seen if seen is not None else set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "pattern" and isinstance(value, str):
                if value not in seen:
                    seen.add(value)
                    yield value
            elif key == "patternProperties" and isinstance(value, dict):
                for name, sub in value.items():
                    if isinstance(name, str) and name not in seen:
                        seen.add(name)
                        yield name
                    yield from _patterns_of(sub, seen)
            else:
                yield from _patterns_of(value, seen)
    elif isinstance(node, list):
        for value in node:
            yield from _patterns_of(value, seen)


def patterns_checked() -> bool:
    """STRATA_SAFE_SCHEMA_PATTERNS=0 lets a pattern that can take exponential time through anyway."""
    return os.environ.get("STRATA_SAFE_SCHEMA_PATTERNS", "1").strip() != "0"


def check_patterns(schema) -> None:
    """Refuse a schema whose regexes can blow up on text the model chose; see _nested_quantifier."""
    for pattern in _patterns_of(schema):
        if _nested_quantifier(pattern):
            raise ValueError(f"response_format schema has a pattern that can take exponential time to match, "
                             f"because one quantifier sits inside another: {pattern!r}. Write it without the nesting "
                             f"(\"a+\", or \"a+(?: a+)*\", rather than \"(a+)+\"); STRATA_SAFE_SCHEMA_PATTERNS=0 "
                             f"accepts it anyway")


def prepare_format(response_format, messages, with_tools=False):
    if response_format is None:
        return messages, None
    if not isinstance(response_format, dict):
        raise ValueError("response_format must be an object")
    kind = response_format.get("type")
    if kind == "text":
        return messages, None
    if kind == "json_object":
        schema = {"type": "object"}
        modules = None                 # the standard library is enough for "one JSON object"
    elif kind == "json_schema":
        spec = response_format.get("json_schema")
        if not isinstance(spec, dict) or not isinstance(spec.get("schema"), dict):
            raise ValueError("response_format.json_schema needs a schema object")
        if not isinstance(spec.get("name"), str) or not spec["name"]:
            raise ValueError("response_format.json_schema needs a name")
        if "strict" in spec and not isinstance(spec["strict"], bool):
            raise ValueError("response_format.json_schema.strict must be boolean")
        schema = spec["schema"]
        if not _only_objects(schema, schema):
            raise ValueError("response_format schema must accept only JSON objects at its root "
                             "(type object, or anyOf/oneOf of object schemas)")
        modules = jsonschema_modules()
    else:
        raise ValueError("response_format.type must be text, json_object or json_schema")

    def check_refs(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("$ref", "$dynamicRef") and isinstance(value, str) and not value.startswith("#"):
                    raise ValueError("response_format supports only local schema references (#...)")
                check_refs(value)
        elif isinstance(node, list):
            for value in node:
                check_refs(value)
    check_refs(schema)
    if modules is not None and patterns_checked():
        check_patterns(schema)              # only worth refusing when the pattern will actually be matched
    if modules is None:
        validator = _ObjectOnly()
    else:
        validators, SchemaError, Registry, NoSuchResource = modules

        def no_remote(uri):
            raise NoSuchResource(ref=uri)

        try:
            cls = validators.validator_for(schema)
            cls.check_schema(schema)
            validator = cls(schema, registry=Registry(retrieve=no_remote))
        except SchemaError as exc:
            raise ValueError(f"invalid response_format schema: {exc.message}") from exc
    directive = ("OUTPUT FORMAT REQUIREMENT: Return exactly one JSON object matching the JSON Schema below. "
                 "No Markdown, headings, code fences, commentary, or text outside the JSON. "
                 "Use every required field, correct types, and only allowed fields. "
                 "Put all requested writing inside the appropriate JSON string fields.\nJSON Schema:\n" +
                 json.dumps(schema, ensure_ascii=False, allow_nan=False, separators=(",", ":")))
    if with_tools:
        # /v1/responses (#782): the schema is for the final answer; a turn that calls a tool is not an answer
        directive += ("\nThis applies only to your final answer. To use a tool, call it as usual; the JSON object is "
                      "what you write once you are done with the tools.")
    messages = [dict(message) for message in messages]
    if messages and messages[0].get("role") == "system":
        content = messages[0].get("content") or ""
        if isinstance(content, list):
            messages[0]["content"] = content + [{"type": "text", "text": directive}]
        else:
            messages[0]["content"] = content + "\n\n" + directive
    else:
        messages.insert(0, {"role": "system", "content": directive})
    return messages, validator


def _extract_json(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return ""
    if s.startswith("```"):
        first = s.find("\n")
        if first != -1:
            end = s.find("```", first + 1)
            if end != -1:
                s = s[first + 1:end].strip()
    start = s.find("{")
    if start == -1:
        return s
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == "\"":
                in_str = False
        else:
            if ch == "\"":
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return s[start:i + 1]
    return s[start:]


def validated_json(text, validator, finish):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError(f"duplicate JSON key: {key}")
            obj[key] = value
        return obj

    def constant(value):
        raise ValueError(f"invalid JSON constant: {value}")

    if finish != "stop":
        raise StructuredOutputError(f"structured output was incomplete (finish_reason={finish}); increase the output budget")
    try:
        value = json.loads(_extract_json(text), object_pairs_hook=pairs, parse_constant=constant)
        canonical = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (ValueError, TypeError) as exc:
        raise StructuredOutputError(f"model did not return valid JSON: {exc}") from exc
    try:
        error = next(validator.iter_errors(value), None)
    except Exception as exc:
        raise StructuredOutputError(f"could not validate structured output: {exc}") from exc
    if error is not None:
        path = "/" + "/".join(str(part) for part in error.absolute_path)
        raise StructuredOutputError(f"model output failed the JSON Schema at {path}: {error.message}")
    return canonical
