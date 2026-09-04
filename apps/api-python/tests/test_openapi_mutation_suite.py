"""Phase 2 Semantic OpenAPI Mutation Gate Suite.

Verifies that compare_openapi and the CLI fail closed (return non-zero, detect exact problem)
for each mutation in the required matrix:
1. ci_level: integer -> string
2. drop minimum or maximum
3. add nullable
4. drop required field
5. expand device_class enum
6. change 400 error body to {detail} or inject 422
7. drop signed-query or bearer security alternative
8. add forbidden response field
9. delete /ready from generated operations
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from jplearn_api.main import create_app
from jplearn_api.openapi_diff import compare_openapi, load_handwritten_spec
from jplearn_api.settings import Settings


@pytest.fixture
def baseline_specs() -> tuple[dict[str, Any], dict[str, Any]]:
    handwritten = load_handwritten_spec()
    settings = Settings(
        database_url="postgresql://jplearn_test:jplearn_test@127.0.0.1:5432/jplearn_test",
        jwt_secret="test-secret-at-least-32-bytes-long-for-pyjwt-security",
        openapi_ui=False,
    )
    generated = create_app(settings).openapi()
    # Baseline must be clean
    problems = compare_openapi(handwritten, generated)
    assert not problems, f"Baseline specs have discrepancies before mutation:\n{problems}"
    return handwritten, generated


def test_mutation_1_ci_level_integer_to_string(baseline_specs) -> None:
    handwritten, generated = baseline_specs
    mutated = copy.deepcopy(generated)

    # Mutate ci_level in CatalogItemPublic from integer to string
    mutated["components"]["schemas"]["CatalogItemPublic"]["properties"]["ci_level"]["type"] = "string"

    problems = compare_openapi(handwritten, mutated)
    assert any("type mismatch: generated 'string' != handwritten 'integer'" in p for p in problems)


def test_mutation_2_drop_minimum_or_maximum(baseline_specs) -> None:
    handwritten, generated = baseline_specs

    # Drop minimum from current_ci_level in LearnerProgressPublic
    mutated1 = copy.deepcopy(generated)
    mutated1["components"]["schemas"]["LearnerProgressPublic"]["properties"]["current_ci_level"].pop("minimum", None)
    problems1 = compare_openapi(handwritten, mutated1)
    assert any("missing minimum (expected 0)" in p for p in problems1)

    # Drop maximum from current_ci_level in LearnerProgressPublic
    mutated2 = copy.deepcopy(generated)
    mutated2["components"]["schemas"]["LearnerProgressPublic"]["properties"]["current_ci_level"].pop("maximum", None)
    problems2 = compare_openapi(handwritten, mutated2)
    assert any("missing maximum (expected 4)" in p for p in problems2)



def test_mutation_3_add_nullable(baseline_specs) -> None:
    handwritten, generated = baseline_specs
    mutated = copy.deepcopy(generated)

    # Make topic_id nullable in CatalogItemPublic schema
    mutated["components"]["schemas"]["CatalogItemPublic"]["properties"]["topic_id"]["nullable"] = True

    problems = compare_openapi(handwritten, mutated)
    assert any("nullable mismatch: generated True != handwritten False" in p for p in problems)


def test_mutation_4_drop_required_field(baseline_specs) -> None:
    handwritten, generated = baseline_specs
    mutated = copy.deepcopy(generated)

    # Drop 'duration_seconds' from CatalogItemPublic required list
    mutated["components"]["schemas"]["CatalogItemPublic"]["required"].remove("duration_seconds")

    problems = compare_openapi(handwritten, mutated)
    assert any("missing required fields" in p and "duration_seconds" in p for p in problems)


def test_mutation_5_expand_device_class_enum(baseline_specs) -> None:
    handwritten, generated = baseline_specs
    mutated = copy.deepcopy(generated)

    # Expand device_class enum in SessionStartBody
    mutated["components"]["schemas"]["SessionStartBody"]["properties"]["device_class"]["enum"].append("android_tv")

    problems = compare_openapi(handwritten, mutated)
    assert any("enum mismatch" in p for p in problems)


def test_mutation_6_inject_422_or_detail_error_body(baseline_specs) -> None:
    handwritten, generated = baseline_specs
    mutated = copy.deepcopy(generated)

    # Inject 422 into /auth/login
    mutated["paths"]["/auth/login"]["post"]["responses"]["422"] = {
        "description": "Validation Error",
        "content": {"application/json": {"schema": {"type": "object", "properties": {"detail": {"type": "array"}}}}},
    }

    problems = compare_openapi(handwritten, mutated)
    assert any("extra responses ['422'] not in contract" in p for p in problems)


def test_mutation_7_drop_security_alternative(baseline_specs) -> None:
    handwritten, generated = baseline_specs
    mutated = copy.deepcopy(generated)

    # Change /me from [{bearerAuth: []}] to [] (public)
    mutated["paths"]["/me"]["get"]["security"] = []

    problems = compare_openapi(handwritten, mutated)
    assert any("security mismatch" in p for p in problems)


def test_mutation_8_add_forbidden_response_field(baseline_specs) -> None:
    handwritten, generated = baseline_specs
    mutated = copy.deepcopy(generated)

    # Add extra forbidden property to Flags response
    mutated["components"]["schemas"]["Flags"]["properties"]["leaked_internal_metric"] = {"type": "string"}

    problems = compare_openapi(handwritten, mutated)
    assert any("extra property 'leaked_internal_metric' not in contract" in p for p in problems)


def test_mutation_9_delete_ready_operation(baseline_specs) -> None:
    handwritten, generated = baseline_specs
    mutated = copy.deepcopy(generated)

    # Remove /ready path
    del mutated["paths"]["/ready"]

    problems = compare_openapi(handwritten, mutated)
    assert any("missing required GET /ready" in p for p in problems)


def test_mutation_gate_cli_fails_closed(monkeypatch: pytest.MonkeyPatch, baseline_specs) -> None:
    """Proves that the CLI entrypoint exits non-zero on contract mismatches."""
    from jplearn_api import openapi_diff

    handwritten, generated = baseline_specs
    mutated = copy.deepcopy(generated)
    del mutated["paths"]["/ready"]

    # Monkeypatch create_app to return mutated spec
    class FakeApp:
        def openapi(self):
            return mutated

    monkeypatch.setattr("jplearn_api.main.create_app", lambda settings: FakeApp())

    exit_code = openapi_diff.main([])
    assert exit_code == 1, "CLI must return non-zero exit code on contract failure"
