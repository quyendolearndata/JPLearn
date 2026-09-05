"""Phase 2 & Hardening Regression Semantic OpenAPI Mutation Gate Suite.

Verifies that compare_openapi and the CLI fail closed (return non-zero, detect exact problem)
for each mutation in the required matrix per ADR-003, ADR-005, and R-01:
1. ci_level: integer -> string
2. drop minimum or maximum
3. add nullable
4. drop required field
5. expand device_class enum (and case sensitivity)
6. change 400 error body to {detail} while keeping status 400
7. drop signedQuery or bearerAuth security alternative on media/HLS
8. add forbidden response field
9. delete /ready from generated operations
10. extra required query parameter
11. missing 'type' in schema
12. undefined $ref
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from jplearn_api import openapi_diff
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


def _run_cli_mutant(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mutated_spec: dict[str, Any],
) -> tuple[int, str]:
    class FakeApp:
        def openapi(self):
            return mutated_spec

    monkeypatch.setattr("jplearn_api.main.create_app", lambda settings: FakeApp())
    exit_code = openapi_diff.main([])
    captured = capsys.readouterr()
    return exit_code, captured.out


def test_baseline_cli_exits_zero(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = openapi_diff.main([])
    captured = capsys.readouterr()
    assert exit_code == 0, f"Expected clean baseline exit 0, got {exit_code}:\n{captured.out}"
    assert captured.out == ""


def test_mutation_1_ci_level_integer_to_string(baseline_specs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    handwritten, generated = baseline_specs
    mutated = copy.deepcopy(generated)

    # Mutate ci_level in CatalogItemPublic from integer to string
    mutated["components"]["schemas"]["CatalogItemPublic"]["properties"]["ci_level"]["type"] = "string"

    problems = compare_openapi(handwritten, mutated)
    assert any("type mismatch: generated 'string' != handwritten 'integer'" in p for p in problems)

    code, out = _run_cli_mutant(monkeypatch, capsys, mutated)
    assert code == 1
    assert "type mismatch" in out


def test_mutation_2_drop_minimum_or_maximum(baseline_specs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    handwritten, generated = baseline_specs

    # Drop minimum from current_ci_level in LearnerProgressPublic
    mutated1 = copy.deepcopy(generated)
    mutated1["components"]["schemas"]["LearnerProgressPublic"]["properties"]["current_ci_level"].pop("minimum", None)
    problems1 = compare_openapi(handwritten, mutated1)
    assert any("missing minimum (expected 0)" in p for p in problems1)

    code, out = _run_cli_mutant(monkeypatch, capsys, mutated1)
    assert code == 1
    assert "missing minimum" in out

    # Drop maximum from current_ci_level in LearnerProgressPublic
    mutated2 = copy.deepcopy(generated)
    mutated2["components"]["schemas"]["LearnerProgressPublic"]["properties"]["current_ci_level"].pop("maximum", None)
    problems2 = compare_openapi(handwritten, mutated2)
    assert any("missing maximum (expected 4)" in p for p in problems2)

    code2, out2 = _run_cli_mutant(monkeypatch, capsys, mutated2)
    assert code2 == 1
    assert "missing maximum" in out2


def test_mutation_3_add_nullable(baseline_specs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    handwritten, generated = baseline_specs
    mutated = copy.deepcopy(generated)

    # Make topic_id nullable in CatalogItemPublic schema
    mutated["components"]["schemas"]["CatalogItemPublic"]["properties"]["topic_id"]["nullable"] = True

    problems = compare_openapi(handwritten, mutated)
    assert any("nullable mismatch: generated True != handwritten False" in p for p in problems)

    code, out = _run_cli_mutant(monkeypatch, capsys, mutated)
    assert code == 1
    assert "nullable mismatch" in out


def test_mutation_4_drop_required_field(baseline_specs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    handwritten, generated = baseline_specs
    mutated = copy.deepcopy(generated)

    # Drop 'duration_seconds' from CatalogItemPublic required list
    mutated["components"]["schemas"]["CatalogItemPublic"]["required"].remove("duration_seconds")

    problems = compare_openapi(handwritten, mutated)
    assert any("missing required fields" in p and "duration_seconds" in p for p in problems)

    code, out = _run_cli_mutant(monkeypatch, capsys, mutated)
    assert code == 1
    assert "missing required fields" in out


def test_mutation_5_expand_device_class_enum_and_case(baseline_specs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    handwritten, generated = baseline_specs
    mutated = copy.deepcopy(generated)

    # Expand device_class enum in SessionStartBody
    mutated["components"]["schemas"]["SessionStartBody"]["properties"]["device_class"]["enum"].append("android_tv")

    problems = compare_openapi(handwritten, mutated)
    assert any("enum mismatch" in p for p in problems)

    code, out = _run_cli_mutant(monkeypatch, capsys, mutated)
    assert code == 1
    assert "enum mismatch" in out

    # Test case sensitivity: "WEB" instead of "web"
    mutated_case = copy.deepcopy(generated)
    mutated_case["components"]["schemas"]["SessionStartBody"]["properties"]["device_class"]["enum"] = ["WEB", "phone", "ipad"]
    problems_case = compare_openapi(handwritten, mutated_case)
    assert any("enum mismatch" in p for p in problems_case)


def test_mutation_6_change_400_body_to_detail(baseline_specs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """R-01: Change 400 error body to {detail} while keeping status 400."""
    handwritten, generated = baseline_specs
    mutated = copy.deepcopy(generated)

    # Mutate 400 response on POST /sessions/{id}/end to {detail: string}
    mutated["paths"]["/sessions/{id}/end"]["post"]["responses"]["400"] = {
        "description": "Bad Request",
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["detail"],
                    "properties": {"detail": {"type": "string"}},
                }
            }
        },
    }

    problems = compare_openapi(handwritten, mutated)
    assert any("missing required fields" in p and ("statusCode" in p or "message" in p) for p in problems)

    code, out = _run_cli_mutant(monkeypatch, capsys, mutated)
    assert code == 1
    assert "missing required fields" in out


def test_mutation_7_drop_security_alternative_on_media(baseline_specs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """R-01: Drop individual security alternatives directly on media/HLS endpoints."""
    handwritten, generated = baseline_specs

    # 7a: Drop signedQuery from GET /media/{id} (leaving only bearerAuth)
    mutated1 = copy.deepcopy(generated)
    mutated1["paths"]["/media/{id}"]["get"]["security"] = [{"bearerAuth": []}]
    problems1 = compare_openapi(handwritten, mutated1)
    assert any("GET /media/{id} security mismatch" in p for p in problems1)
    code1, out1 = _run_cli_mutant(monkeypatch, capsys, mutated1)
    assert code1 == 1
    assert "security mismatch" in out1

    # 7b: Drop bearerAuth from GET /media/{id} (leaving only signedQuery)
    mutated2 = copy.deepcopy(generated)
    mutated2["paths"]["/media/{id}"]["get"]["security"] = [{"signedQuery": []}]
    problems2 = compare_openapi(handwritten, mutated2)
    assert any("GET /media/{id} security mismatch" in p for p in problems2)
    code2, out2 = _run_cli_mutant(monkeypatch, capsys, mutated2)
    assert code2 == 1
    assert "security mismatch" in out2

    # 7c: Drop all security on GET /media/{id}/hls/{file}
    mutated3 = copy.deepcopy(generated)
    mutated3["paths"]["/media/{id}/hls/{file}"]["get"]["security"] = []
    problems3 = compare_openapi(handwritten, mutated3)
    assert any("GET /media/{id}/hls/{file} security mismatch" in p for p in problems3)
    code3, out3 = _run_cli_mutant(monkeypatch, capsys, mutated3)
    assert code3 == 1
    assert "security mismatch" in out3


def test_mutation_8_add_forbidden_response_field(baseline_specs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    handwritten, generated = baseline_specs
    mutated = copy.deepcopy(generated)

    # Add extra forbidden property to Flags response
    mutated["components"]["schemas"]["Flags"]["properties"]["leaked_internal_metric"] = {"type": "string"}

    problems = compare_openapi(handwritten, mutated)
    assert any("extra property 'leaked_internal_metric' not in contract" in p for p in problems)

    code, out = _run_cli_mutant(monkeypatch, capsys, mutated)
    assert code == 1
    assert "extra property" in out


def test_mutation_9_delete_ready_operation(baseline_specs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    handwritten, generated = baseline_specs
    mutated = copy.deepcopy(generated)

    # Remove /ready path
    del mutated["paths"]["/ready"]

    problems = compare_openapi(handwritten, mutated)
    assert any("missing required GET /ready" in p for p in problems)

    code, out = _run_cli_mutant(monkeypatch, capsys, mutated)
    assert code == 1
    assert "missing required GET /ready" in out


def test_mutation_10_extra_required_query_parameter(baseline_specs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """R-01: Extra required query parameter must fail."""
    handwritten, generated = baseline_specs
    mutated = copy.deepcopy(generated)

    # Inject extra required query parameter into GET /catalog
    mutated["paths"]["/catalog"]["get"]["parameters"].append({
        "name": "unexpected_filter",
        "in": "query",
        "required": True,
        "schema": {"type": "string"},
    })

    problems = compare_openapi(handwritten, mutated)
    assert any("extra required query parameter 'unexpected_filter' not in contract" in p for p in problems)

    code, out = _run_cli_mutant(monkeypatch, capsys, mutated)
    assert code == 1
    assert "extra required query parameter" in out


def test_mutation_11_missing_type_in_schema(baseline_specs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """R-01: Missing type in schema must fail."""
    handwritten, generated = baseline_specs
    mutated = copy.deepcopy(generated)

    # Delete type from ci_level in CatalogItemPublic
    del mutated["components"]["schemas"]["CatalogItemPublic"]["properties"]["ci_level"]["type"]

    problems = compare_openapi(handwritten, mutated)
    assert any("missing 'type' in generated schema" in p for p in problems)

    code, out = _run_cli_mutant(monkeypatch, capsys, mutated)
    assert code == 1
    assert "missing 'type'" in out


def test_mutation_12_undefined_ref_fails(baseline_specs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """R-01: Undefined $ref must report error."""
    handwritten, generated = baseline_specs
    mutated = copy.deepcopy(generated)

    # Point User to undefined schema ref
    mutated["components"]["schemas"]["AuthSession"]["properties"]["user"] = {
        "$ref": "#/components/schemas/NonExistentUserSchema"
    }

    problems = compare_openapi(handwritten, mutated)
    assert any("undefined $ref" in p and "NonExistentUserSchema" in p for p in problems)

    code, out = _run_cli_mutant(monkeypatch, capsys, mutated)
    assert code == 1
    assert "undefined $ref" in out


def test_mutation_13_password_min_length_100_fails(baseline_specs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """R-01: Increasing password minLength from 10 to 100 must fail."""
    handwritten, generated = baseline_specs
    mutated = copy.deepcopy(generated)

    mutated["components"]["schemas"]["RegisterBody"]["properties"]["password"]["minLength"] = 100

    problems = compare_openapi(handwritten, mutated)
    assert any("minLength mismatch: generated 100 != handwritten 10" in p for p in problems)

    code, out = _run_cli_mutant(monkeypatch, capsys, mutated)
    assert code == 1
    assert "minLength mismatch" in out


def test_mutation_14_password_min_length_1_fails(baseline_specs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """R-01: Decreasing password minLength from 10 to 1 must fail."""
    handwritten, generated = baseline_specs
    mutated = copy.deepcopy(generated)

    mutated["components"]["schemas"]["RegisterBody"]["properties"]["password"]["minLength"] = 1

    problems = compare_openapi(handwritten, mutated)
    assert any("minLength mismatch: generated 1 != handwritten 10" in p for p in problems)

    code, out = _run_cli_mutant(monkeypatch, capsys, mutated)
    assert code == 1
    assert "minLength mismatch" in out


def test_mutation_15_password_min_length_dropped_fails(baseline_specs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """R-01: Dropping password minLength must fail."""
    handwritten, generated = baseline_specs
    mutated = copy.deepcopy(generated)

    del mutated["components"]["schemas"]["RegisterBody"]["properties"]["password"]["minLength"]

    problems = compare_openapi(handwritten, mutated)
    assert any("missing minLength (expected 10)" in p for p in problems)

    code, out = _run_cli_mutant(monkeypatch, capsys, mutated)
    assert code == 1
    assert "missing minLength" in out


def test_mutation_16_max_length_variations_fail(baseline_specs) -> None:
    """R-01: MaxLength increased, decreased, dropped, or unexpectedly added must fail."""
    from jplearn_api.openapi_diff import compare_schemas

    h_spec = {}
    g_spec = {}

    h_schema = {"type": "string", "maxLength": 100}

    # 1. Increased maxLength
    g_increased = {"type": "string", "maxLength": 200}
    p1 = compare_schemas(h_spec, g_spec, h_schema, g_increased, "ctx")
    assert any("maxLength mismatch: generated 200 != handwritten 100" in p for p in p1)

    # 2. Decreased maxLength
    g_decreased = {"type": "string", "maxLength": 50}
    p2 = compare_schemas(h_spec, g_spec, h_schema, g_decreased, "ctx")
    assert any("maxLength mismatch: generated 50 != handwritten 100" in p for p in p2)

    # 3. Dropped maxLength
    g_dropped = {"type": "string"}
    p3 = compare_schemas(h_spec, g_spec, h_schema, g_dropped, "ctx")
    assert any("missing maxLength (expected 100)" in p for p in p3)

    # 4. Unexpected maxLength added
    h_no_max = {"type": "string"}
    g_added = {"type": "string", "maxLength": 100}
    p4 = compare_schemas(h_spec, g_spec, h_no_max, g_added, "ctx")
    assert any("unexpected maxLength in generated schema: 100" in p for p in p4)


def test_mutation_17_unexpected_min_length_added_fails(baseline_specs) -> None:
    """R-01: Unexpected minLength added when not in contract must fail."""
    from jplearn_api.openapi_diff import compare_schemas

    h_spec, g_spec = {}, {}
    h_schema = {"type": "string"}
    g_schema = {"type": "string", "minLength": 5}

    problems = compare_schemas(h_spec, g_spec, h_schema, g_schema, "ctx")
    assert any("unexpected minLength in generated schema: 5" in p for p in problems)


def test_mutation_18_enum_type_bool_vs_int_fails(baseline_specs) -> None:
    """R-01: Enum distinguishing bool and int types (e.g. [True] vs [1])."""
    from jplearn_api.openapi_diff import compare_schemas

    h_spec, g_spec = {}, {}
    h_schema = {"enum": [True]}
    g_schema = {"enum": [1]}

    problems = compare_schemas(h_spec, g_spec, h_schema, g_schema, "ctx")
    assert any("enum mismatch" in p for p in problems)

