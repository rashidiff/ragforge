"""Generate the initial TS model mirror from Python annotations, without importing the app.

This is source generation only: it never starts services, installs dependencies,
executes application code, or runs tests/type checks. OpenAPI export is separate.
"""
import argparse
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "backend/app/domain/schemas.py"
OUTPUT = ROOT / "frontend/src/lib/contracts.ts"


def typescript(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return {"str": "string", "UUID": "string", "datetime": "string", "int": "number",
                "float": "number", "bool": "boolean", "Any": "unknown"}.get(node.id, node.id)
    if isinstance(node, ast.Constant):
        import json
        return "null" if node.value is None else json.dumps(node.value)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return f"{typescript(node.left)} | {typescript(node.right)}"
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        if node.value.id == "list":
            return f"Array<{typescript(node.slice)}>"
        if node.value.id == "dict":
            key, value = node.slice.elts
            return f"Record<{typescript(key)}, {typescript(value)}>"
        if node.value.id == "Literal":
            values = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            return " | ".join(typescript(value) for value in values)
    raise ValueError(f"Unsupported public annotation: {ast.unparse(node)}. Extend the generator.")


def has_default(node: ast.AnnAssign) -> bool:
    if node.value is None:
        return False
    if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "Field":
        return any(keyword.arg in {"default", "default_factory"} for keyword in node.value.keywords)
    return True


def render(source: str) -> str:
    tree = ast.parse(source)
    models: dict[str, dict[str, tuple[str, bool]]] = {}
    for definition in tree.body:
        if not isinstance(definition, ast.ClassDef):
            continue
        bases = [base.id for base in definition.bases if isinstance(base, ast.Name)]
        if definition.name == "Contract":
            models["Contract"] = {}
            continue
        if not any(base in models for base in bases):
            continue
        fields = {}
        for base in bases:
            fields.update(models.get(base, {}))
        for node in definition.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                fields[node.target.id] = (typescript(node.annotation), has_default(node))
        models[definition.name] = fields
    lines = ["/** Generated from backend/app/domain/schemas.py by scripts/generate_contracts.py. */", ""]
    for name, fields in models.items():
        if name == "Contract":
            continue
        lines.append(f"export interface {name} {{")
        for field, (value, optional) in fields.items():
            lines.append(f"  {field}{'?' if optional else ''}: {value};")
        lines.extend(["}", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare generated source without writing")
    args = parser.parse_args()
    result = render(SOURCE.read_text(encoding="utf-8"))
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != result:
            raise SystemExit("TypeScript model mirror has drifted. Run scripts/generate_contracts.py.")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(result, encoding="utf-8")


if __name__ == "__main__":
    main()
