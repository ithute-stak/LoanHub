"""Guard against retry storms and misleading Python tracebacks on GitHub HTTP errors."""
from pathlib import Path


def test_release_selection_requires_valid_github_response():
    script = (Path(__file__).parents[3] / "scripts" / "deploy-production-manual.sh").read_text()
    assert 'if ! runs_json="$(api_get ' in script
    assert 'if ! candidates="$(printf' in script
    assert 'done <<< "$candidates"' in script
    assert 'GitHub release API unavailable. Deployment stopped' in script
    assert 'GitHub release API returned invalid JSON. Deployment stopped.' in script
    assert 'if ! status="$(compare_release "$current_release" "$candidate")"' in script
    assert 'Unable to verify release ancestry. Deployment stopped.' in script


def test_comparison_checks_http_response_before_json_parse():
    script = (Path(__file__).parents[3] / "scripts" / "deploy-production-manual.sh").read_text()
    assert 'if ! response="$(api_get ' in script
    assert 'GitHub comparison API unavailable. Refusing unverified release.' in script
