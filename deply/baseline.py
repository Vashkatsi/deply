import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from deply.models.violation_identity import relationship_fingerprint


IDENTITY_FIELDS = ("rule_id", "source", "target", "source_layer", "target_layer", "dependency_type")


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate baseline key: {key}")
        result[key] = value
    return result


def _valid_element(value: Any, external: bool = False) -> bool:
    if not isinstance(value, dict):
        return False
    fields = {"module", "type"} if external else {"file", "name", "type"}
    return set(value) == fields and all(isinstance(value[key], str) and value[key] for key in fields)


def _validate_record(record: Any) -> None:
    if not isinstance(record, dict) or not all(field in record for field in IDENTITY_FIELDS):
        raise ValueError("Baseline violation is missing relationship identity")
    target = record["target"]
    external_target = isinstance(target, dict) and target.get("type") == "external_module"
    if (
        not isinstance(record["rule_id"], str) or not record["rule_id"]
        or not _valid_element(record["source"])
        or (target is not None and not _valid_element(target, external=external_target))
        or any(record[field] is not None and not isinstance(record[field], str)
               for field in ("source_layer", "target_layer", "dependency_type"))
        or any(not isinstance(record.get(field), str)
               for field in ("file", "element_name", "element_type", "message", "violation_type"))
        or any(type(record.get(field)) is not int or record[field] < 0 for field in ("line", "column"))
    ):
        raise ValueError("Invalid baseline violation diagnostic or identity")
    identity = {field: record[field] for field in IDENTITY_FIELDS}
    if record.get("fingerprint") != relationship_fingerprint(identity):
        raise ValueError("Baseline fingerprint does not match its relationship identity")


def load_baseline(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
    if (
        not isinstance(data, dict) or set(data) != {"schema_version", "violations"}
        or type(data["schema_version"]) is not int or data["schema_version"] != 1
        or not isinstance(data["violations"], list)
    ):
        raise ValueError("Expected a Deply baseline with schema_version 1 and violations")
    for record in data["violations"]:
        _validate_record(record)
    return data["violations"]


def write_baseline(path: Path, records: List[Dict[str, Any]]) -> None:
    payload = json.dumps({"schema_version": 1, "violations": records}, indent=2) + "\n"
    # Publish a complete file exclusively, including when another process creates the destination.
    with tempfile.TemporaryDirectory(prefix=".deply-baseline-", dir=path.absolute().parent) as directory:
        temporary_path = Path(directory) / "baseline.json"
        temporary_path.write_text(payload, encoding="utf-8")
        os.link(temporary_path, path)


def compare_baseline(
        current: List[Dict[str, Any]], accepted: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    current_fingerprints = {record["fingerprint"] for record in current}
    accepted_fingerprints = {record["fingerprint"] for record in accepted}
    return {
        "new": [record for record in current if record["fingerprint"] not in accepted_fingerprints],
        "existing": [record for record in current if record["fingerprint"] in accepted_fingerprints],
        "resolved": [record for record in accepted if record["fingerprint"] not in current_fingerprints],
    }
