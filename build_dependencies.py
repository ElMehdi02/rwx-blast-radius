
"""Build a static reverse-call dependency map.

Uses only the pinned sqlglot source.
Does not read sample answers or incoming patches.
"""

import ast
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path("/opt/sqlglot")
OUT = Path("/app/dependencies.json")


def module_path(path):
    relative = path.relative_to(ROOT).with_suffix("")

    return ".".join(
        relative.parts
    ).removesuffix(".__init__")


def collect(path):
    try:
        tree = ast.parse(
            path.read_text(encoding="utf-8")
        )
    except (SyntaxError, UnicodeError, OSError):
        return None

    result = []

    def walk(body, prefix=""):
        for node in body:
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                name = prefix + node.name

                result.append((name, node))
                walk(node.body, name + ".")

            elif isinstance(node, ast.ClassDef):
                walk(
                    node.body,
                    prefix + node.name + ".",
                )

    walk(tree.body)
    return tree, result


def main():
    files = list(
        (ROOT / "sqlglot").rglob("*.py")
    )

    parsed = {}
    symbols = set()

    for path in files:
        loaded = collect(path)

        if loaded is None:
            continue

        module = module_path(path)
        parsed[module] = (path, *loaded)

        for name, _ in loaded[1]:
            symbols.add(module + ":" + name)

    reverse = defaultdict(set)

    for module, (path, tree, funcs) in parsed.items():
        aliases = {}

        for node in tree.body:
            if isinstance(node, ast.Import):
                for item in node.names:
                    aliases[
                        item.asname
                        or item.name.split(".")[0]
                    ] = item.name

            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    package = (
                        module
                        if path.name == "__init__.py"
                        else module.rpartition(".")[0]
                    )

                    bits = package.split(".") if package else []

                    bits = bits[
                        :max(0, len(bits) - (node.level - 1))
                    ]

                    imported_module = ".".join(
                        bits + (
                            [node.module]
                            if node.module else []
                        )
                    )
                else:
                    imported_module = node.module or ""

                for item in node.names:
                    if item.name != "*":
                        aliases[
                            item.asname or item.name
                        ] = (
                            imported_module
                            + ":"
                            + item.name
                        )

        for name, node in funcs:
            caller = module + ":" + name
            cls = name.rpartition(".")[0]

            for child in ast.walk(node):
                if not isinstance(child, ast.Call):
                    continue

                fn = child.func
                targets = []

                if isinstance(fn, ast.Name):
                    ident = fn.id

                    targets.extend([
                        module + ":" + ident,
                        aliases.get(ident, ""),
                    ])

                elif (
                    isinstance(fn, ast.Attribute)
                    and isinstance(fn.value, ast.Name)
                ):
                    ident = fn.value.id

                    if ident in ("self", "cls") and cls:
                        targets.append(
                            module + ":" + cls
                            + "." + fn.attr
                        )

                    imported = aliases.get(ident, "")

                    if imported and ":" not in imported:
                        targets.append(
                            imported + ":" + fn.attr
                        )

                    elif imported and ":" in imported:
                        base, symbol = imported.split(":", 1)

                        targets.append(
                            base + "." + symbol
                            + ":" + fn.attr
                        )

                for callee in targets:
                    if (
                        callee in symbols
                        and callee != caller
                    ):
                        reverse[callee].add(caller)

    payload = {
        name: sorted(callers)
        for name, callers in reverse.items()
    }

    OUT.write_text(
        json.dumps(
            payload,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    OUT.chmod(0o644)

    print(
        "Function nodes:", len(symbols),
        "reverse edges:",
        sum(map(len, payload.values())),
        flush=True,
    )


if __name__ == "__main__":
    main()
