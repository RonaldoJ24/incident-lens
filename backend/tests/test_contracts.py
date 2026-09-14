import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from incident_lens.validation.contracts import ContractError, validate_document, validate_fixture


ROOT = Path(__file__).parents[2]


class ContractValidationTests(unittest.TestCase):
    def test_representative_fixture_covers_all_phase_zero_entities(self):
        count = validate_fixture(ROOT / "contracts/v1/examples/representative.json")
        self.assertEqual(count, 9)

    def test_stored_result_requires_a_prior_run(self):
        fixture = json.loads((ROOT / "contracts/v1/examples/representative.json").read_text())
        run = next(item for item in fixture["documents"] if item["entity"] == "run")
        run["payload"]["provenance"]["execution"] = "stored_result"
        with self.assertRaisesRegex(ContractError, "prior_run_id"):
            validate_document(run)

    def test_entity_must_match_payload_shape(self):
        fixture = json.loads((ROOT / "contracts/v1/examples/representative.json").read_text())
        run = next(item for item in fixture["documents"] if item["entity"] == "run")
        mismatch = dict(run)
        mismatch["entity"] = "session"
        with self.assertRaisesRegex(ContractError, "session missing"):
            validate_document(mismatch)

    def test_report_cannot_claim_repair(self):
        fixture = json.loads((ROOT / "contracts/v1/examples/representative.json").read_text())
        report = next(item for item in fixture["documents"] if item["entity"] == "report")
        report["payload"]["repair_claim"] = True
        with self.assertRaisesRegex(ContractError, "repair"):
            validate_document(report)

    def test_api_contract_exposes_investigation_retrieval_review_and_export(self):
        api = json.loads((ROOT / "contracts/v1/api.openapi.json").read_text())
        operations = {
            operation["operationId"]
            for path in api["paths"].values()
            for operation in path.values()
            if isinstance(operation, dict) and "operationId" in operation
        }
        self.assertTrue({"listFindings", "listEvidence", "listTimelineEvents", "reviewFinding", "exportReport", "runInvestigationWorkflow"} <= operations)

    def test_api_path_templates_have_required_string_parameters(self):
        api = json.loads((ROOT / "contracts/v1/api.openapi.json").read_text())
        for path, path_item in api["paths"].items():
            names = set(__import__("re").findall(r"\{([^}]+)\}", path))
            declared = {
                parameter["name"]
                for parameter in path_item.get("parameters", [])
                if "$ref" not in parameter
                for _ in [parameter]
            }
            for parameter in path_item.get("parameters", []):
                if "$ref" in parameter:
                    ref_name = parameter["$ref"].rsplit("/", 1)[-1]
                    parameter = api["components"]["parameters"][ref_name]
                self.assertEqual(parameter["in"], "path")
                self.assertTrue(parameter["required"])
                self.assertEqual(parameter["schema"], {"type": "string"})
                declared.add(parameter["name"])
            self.assertEqual(names, declared, path)


if __name__ == "__main__":
    unittest.main()
