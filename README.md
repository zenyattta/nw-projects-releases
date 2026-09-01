# NW Projects Releases

Official update distribution repository for NW Projects.

This repository contains release metadata and Windows release assets only. Application source is maintained separately.

## Publisher contract

Releases are published manually by `.github/workflows/publish-release.yml` from this repository's trusted `main` branch. The publisher accepts a source tag and source Actions run ID, then verifies the private `zenyattta/nw-projects` run, annotated tag, current `master` commit, required artifact digest, archive shape, and binary checksums before creating a draft Release.

The source workflow must be named `Build Windows release` at `.github/workflows/release.yml`. A successful, first-attempt `push` run for annotated tag `vX.Y.Z` must upload exactly one unexpired artifact named `NW-Projects-X.Y.Z-win-x64`. Its ZIP must contain exactly:

- `NW-Projects-Setup-X.Y.Z-win-x64.exe`
- `NW-Projects-X.Y.Z-win-x64.exe`
- `SHA256SUMS.txt`

Release notes are read from `.github/release-notes.md` at the verified source commit. The file must be nonempty UTF-8 text whose first line is exactly `## NW Projects vX.Y.Z` for the verified source tag. The source workflow must not hold credentials for this repository.

## Required configuration

1. Enable **immutable releases** in this repository's Settings before publishing. GitHub does not currently document an API field that exposes this repository setting before a Release exists, so the workflow verifies `immutable: true` immediately after publication and otherwise fails without deleting or moving the tag.
2. Create the `source-release` environment and add `SOURCE_REPO_TOKEN` as an environment secret. It must be a fine-grained token scoped only to private repository `zenyattta/nw-projects`, with **Actions: read** and **Contents: read** and no write permissions.
3. Restrict the environment to the `main` deployment branch. Only `zenyattta` may dispatch and re-run the workflow; both the original actor and triggering actor are checked before the source token is made available to a step.

Publishing remains blocked until the source workflow follows the artifact contract, the environment secret is configured, and immutable releases are enabled.

Every public release tag is an annotated tag whose object targets seed commit `15fb9d69643afc63ef302c640f285919de6d15ec`. Consequently, GitHub-generated source archives contain only this README and never publisher workflow history or private application source. Existing destination tags and Releases are rejected. If a run fails after creating its tag, do not force, move, or delete the tag; fix the issue and publish a new SemVer.
