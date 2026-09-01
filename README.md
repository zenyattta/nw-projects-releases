# NW Projects Releases

Official update distribution repository for NW Projects.

This repository contains release metadata and Windows release assets only. Application source is maintained separately.

## Trusted release publishing

Releases are published only by the default-branch
[`Publish trusted release`](.github/workflows/publish-trusted-release.yml) workflow. The
repository owner manually supplies the numeric successful run ID from the private
`zenyattta/nw-projects` `Build Windows release` workflow. The publisher reads and
validates that exact run, its annotated source tag, artifact digest and checksums, and
release notes without checking out or executing private source code.

Configure the repository secret `SOURCE_REPO_TOKEN` as a fine-grained personal access
token scoped only to `zenyattta/nw-projects`, with:

- **Actions: Read**
- **Contents: Read**
- **Metadata: Read** (implicit)

It must have no write permissions. A short-lived GitHub App installation token with
the same read-only scope can replace it later. Do not configure or use a
`RELEASES_REPO_TOKEN`; the isolated `public-release` job publishes to this repository
with its own `GITHUB_TOKEN`, limited to `actions: read` and `contents: write`.

The `public-release` environment is a named publication boundary, but no environment
protection policy is assumed on the current plan. Publisher authorization therefore
also requires the exact repository, owner actor and triggering actor, first run
attempt, and the workflow's `main` ref. Production updater deployment remains blocked
until a public **v1.1.8** release exists here and is marked **Latest**. Do not deploy
the updater against v1.1.7.
