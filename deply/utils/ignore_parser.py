import tokenize
from io import BytesIO
from pathlib import Path

ALL_SUPPRESSION_RULES = "*"


def parse_ignore_comments(file_path: Path, file_bytes: bytes = None) -> dict:
    ignore_map = {"file": set(), "lines": {}}
    try:
        if file_bytes is None:
            file_bytes = file_path.read_bytes()
    except Exception:
        return ignore_map

    tokens = tokenize.tokenize(BytesIO(file_bytes).readline)
    for token in tokens:
        if token.type == tokenize.COMMENT:
            comment = token.string.strip()
            # Process file-level suppression
            if comment.startswith("# deply:ignore-file"):
                remainder = comment[len("# deply:ignore-file"):].strip()
                if remainder.startswith(":"):
                    rule_spec = remainder[1:].strip()
                    if rule_spec:
                        rules = {r.strip().upper() for r in rule_spec.split(",") if r.strip()}
                        ignore_map["file"].update(rules)
                    else:
                        ignore_map["file"].add(ALL_SUPPRESSION_RULES)
                else:
                    ignore_map["file"].add(ALL_SUPPRESSION_RULES)
            # Process line-level suppression
            elif "# deply:ignore" in comment:
                index = comment.find("# deply:ignore")
                if index != -1:
                    remainder = comment[len("# deply:ignore"):].strip()
                    if remainder.startswith(":"):
                        rule_spec = remainder[1:].strip()
                        rules = {r.strip().upper() for r in rule_spec.split(",") if r.strip()}
                    else:
                        rules = {ALL_SUPPRESSION_RULES}
                    line_number = token.start[0]
                    ignore_map["lines"].setdefault(line_number, set()).update(rules)
    return ignore_map
