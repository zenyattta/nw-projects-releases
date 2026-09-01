from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / ".github" / "workflows" / "publish-trusted-release.yml"
VALIDATOR = ROOT / ".github" / "workflows" / "validate-trusted-publisher.yml"
SHA_PIN = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        parsed = yaml.load(handle, Loader=yaml.BaseLoader)
    require(isinstance(parsed, dict), f"{path} must contain a YAML mapping")
    return parsed


def parse_powershell(scripts: list[str]) -> None:
    parser = r"""
param([Parameter(Mandatory)][string]$Path)
$tokens = $null
$errors = $null
[Management.Automation.Language.Parser]::ParseFile(
  $Path,
  [ref]$tokens,
  [ref]$errors
) | Out-Null
if ($errors.Count -ne 0) {
  $errors | ForEach-Object { [Console]::Error.WriteLine($_.Message) }
  exit 1
}
"""
    with tempfile.TemporaryDirectory() as temporary:
        temp = Path(temporary)
        parser_path = temp / "parse.ps1"
        parser_path.write_text(parser, encoding="utf-8")
        for index, script in enumerate(scripts):
            script_path = temp / f"embedded-{index}.ps1"
            script_path.write_text(script, encoding="utf-8")
            subprocess.run(
                [
                    "pwsh",
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-File",
                    str(parser_path),
                    str(script_path),
                ],
                check=True,
            )


publisher = load_yaml(PUBLISHER)
validator = load_yaml(VALIDATOR)
publisher_text = PUBLISHER.read_text(encoding="utf-8")

require(set(publisher["on"]) == {"workflow_dispatch"}, "publisher must be manual-only")
source_input = publisher["on"]["workflow_dispatch"]["inputs"]["source_run_id"]
require(source_input["required"] == "true", "source_run_id must be required")
require(source_input["type"] == "string", "source_run_id must be validated as a string")
require(publisher["permissions"] == {}, "publisher top-level permissions must be empty")
require(
    publisher["concurrency"]["cancel-in-progress"] == "false",
    "publisher runs must not cancel each other",
)

jobs = publisher["jobs"]
require(
    set(jobs) == {
        "reject-untrusted-context",
        "authorize-context",
        "validate-source",
        "publish",
    },
    "publisher must retain the four-job trust boundary",
)

context_terms = (
    "github.event_name == 'workflow_dispatch'",
    "github.repository == 'zenyattta/nw-projects-releases'",
    "github.actor == 'zenyattta'",
    "github.triggering_actor == 'zenyattta'",
    "github.ref == 'refs/heads/main'",
    "github.ref_name == 'main'",
    "github.event.repository.default_branch == 'main'",
    "github.run_attempt == 1",
    "github.workflow_ref == 'zenyattta/nw-projects-releases/.github/workflows/"
    "publish-trusted-release.yml@refs/heads/main'",
)
for job_name in ("authorize-context", "validate-source", "publish"):
    condition = jobs[job_name]["if"]
    for term in context_terms:
        require(term in condition, f"{job_name} is missing context condition: {term}")
reject_condition = jobs["reject-untrusted-context"]["if"]
for term in context_terms:
    require(term in reject_condition, f"reject job is missing context condition: {term}")

require(jobs["authorize-context"]["permissions"] == {}, "authorize job must have no permissions")
require(jobs["validate-source"]["permissions"] == {}, "source validation must have no target permissions")
require(
    jobs["publish"]["permissions"] == {"actions": "read", "contents": "write"},
    "publish permissions must be exactly actions:read and contents:write",
)
require(jobs["publish"]["environment"] == "public-release", "publish environment changed")

source_secret_expression = "${{ secrets.SOURCE_REPO_TOKEN }}"
require(
    publisher_text.count(source_secret_expression) == 1,
    "SOURCE_REPO_TOKEN secret expression must occur in exactly one step",
)
require("RELEASES_REPO_TOKEN" not in publisher_text, "legacy write token is forbidden")
require("${{ github.token }}" in publisher_text, "publish job must use github.token")
require(
    source_secret_expression in str(jobs["validate-source"]),
    "SOURCE_REPO_TOKEN must be confined to source validation",
)
for job_name in ("reject-untrusted-context", "authorize-context", "publish"):
    require(
        "SOURCE_REPO_TOKEN" not in str(jobs[job_name]),
        f"SOURCE_REPO_TOKEN leaked into {job_name}",
    )

require("actions/checkout" not in publisher_text, "publisher must not check out source code")
for workflow in (publisher, validator):
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if "uses" in step:
                require(SHA_PIN.fullmatch(step["uses"]) is not None, f"action is not SHA-pinned: {step['uses']}")

validate_script = jobs["validate-source"]["steps"][0]["run"]
publish_script = jobs["publish"]["steps"][1]["run"]
for required_fragment in (
    "actions/runs/$sourceRunId",
    "Build Windows release",
    ".github/workflows/release.yml",
    "git/ref/heads/master",
    "git/ref/tags/$encodedTag",
    "git/matching-refs/tags/",
    "actions/runs/$sourceRunId/artifacts",
    "actions/artifacts/$artifactId/zip",
    "sha256:[0-9a-f]{64}",
    "workflow_run.id",
    "workflow_run.head_sha",
    "contents/.github/release-notes.md?ref=$headSha",
    "## NW Projects $tag",
    "[IO.Compression.ZipFile]::OpenRead",
    "ReparsePoint",
):
    require(required_fragment in validate_script, f"source validation lost contract: {required_fragment}")

for required_fragment in (
    "visibility 'public'",
    "default_branch 'main'",
    '$uri = "$apiRoot/repos/$targetRepo"',
    "IsNullOrEmpty($Path)",
    "git/ref/heads/main",
    "git/matching-refs/tags/$encodedTag",
    "releases?per_page=100&page=$releasePage",
    "published or draft target release already exists",
    "refs/tags/$env:RELEASE_TAG",
    "--verify-tag",
    "--latest",
    "gh release create",
    "git/refs/tags/$encodedTag",
    "ReparsePoint",
):
    require(required_fragment in publish_script, f"publish validation lost contract: {required_fragment}")

embedded_scripts = []
for job in jobs.values():
    for step in job.get("steps", []):
        if step.get("shell") == "pwsh":
            embedded_scripts.append(step["run"])
require(len(embedded_scripts) == 4, "expected four embedded PowerShell scripts")
parse_powershell(embedded_scripts)

print("Trusted publisher YAML, PowerShell, permissions, and token boundaries are valid.")
