---
title: Controlled public release of xldiff
date: 2026-10-24
artifact_contract: ce-unified-plan/v1
execution: code
product_contract_source: ce-plan-bootstrap
---

# Controlled public release of xldiff

## Goal

Release xldiff under its existing name and MIT license, with a usable download,
accurate instructions, preserved development history, and outside contributions
disabled. The owner can continue development without running a support queue.

## Product contract

- R1. Keep the repository name, command name, and MIT license.
- R2. Preserve the existing development sequence. Remove personal email addresses
  and session links from commit and tag metadata after making a private backup.
- R3. Publish no credentials, client workbooks, or private working files.
- R4. Keep pull requests, issues, discussions, wiki, projects, automated merging,
  and GitHub Actions disabled. Do not add bots, hosted services, or paid tools.
- R5. Provide a Python wheel and source archive on a tagged GitHub release.
  Explain that the unrelated PyPI package named xldiff is not this project.
- R6. Explain installation, the three commands, interpretation, limitations,
  maintenance, updates, and how to enable selected contributions later.
- R7. Preserve distinct workbook contents even when filenames contain the same
  version number. Unreadable workbooks require review, not a discard suggestion.
- R8. Refuse a cache destination that could overwrite an input workbook.

Non-goals: a graphical app, a new formula engine, a PyPI upload, automatic file
deletion, broad parser refactoring, and accepting external support requests.

## Planning contract

The user authorized preparation and public release. Work on a release branch
until verification is complete. Save a Git bundle outside the repository before
history changes. The original six commits contain code, synthetic tests, and
documentation; the completed history scan found no credentials or client files.

Use a GitHub release rather than PyPI because PyPI's xldiff name belongs to an
unrelated project. Preserve the six development commits with sanitized metadata
instead of replacing them with an empty history. GitHub can retain old commit
pages after a rewrite, so retain the original repository privately under a new
private name and create a separate repository at the public xldiff name. Push
only the sanitized history to that new repository. Keep the release process local;
GitHub Actions stays disabled. Defaults for similarity are conventions, not a
statistical guarantee that a workbook is safe to discard.

## Implementation units

### U1. Release policy and recovery

Files: CONTRIBUTING.md, docs/MAINTAINING.md, this plan.
Save and verify the private Git bundle. Apply repository controls and record
read-back evidence. Review the plan for coherence and feasibility.

### U2. Workbook selection and output safety

Files: src/xldiff/lineage.py, src/xldiff/cli.py, tests/test_lineage.py,
tests/test_cli.py, tests/conftest.py.
Use exact-byte identity before collapsing same-version files. Mark unreadable
inputs for review. Validate selection options and prevent the optional JSON cache
from overwriting workbook input. Keep the existing comparison algorithm.
Prove these cases with regression tests and synthetic fixtures.

### U3. Distribution and documentation

Files: pyproject.toml, src/xldiff/__init__.py, README.md, CHANGELOG.md,
examples/demo.py, docs/MAINTAINING.md, CONTRIBUTING.md, .gitignore.
Release version 0.1.1 as an experimental command-line tool for Python 3.11+.
Build the wheel and source archive. Keep runtime dependencies empty. Include a
reproducible synthetic example without checked-in workbook data. Keep any local
MOG test backend optional so other users can run tests without MOG.

### U4. Verify, sanitize, and publish

Run the tests using MOG-generated disposable workbook fixtures on this host.
Exact fixture shapes exclude a logging worksheet; use MOG's documented
mogLog(false, reason) exception for these fixtures only. Preserve ordinary test
generation for contributors who do not have this local tool.
Install the built wheel into a fresh environment and run its commands on
synthetic workbooks. Review the final code and distribution contents. Sanitize
all retained commit and annotated-tag metadata, then verify unchanged historical
trees. Verify that the original remote has not changed, preserve it privately,
and push only the intended sanitized branch and tags to the new repository.
Disable contribution features and Actions on the new repository before pushing.
Verify GitHub controls again before changing visibility. Publish the tagged
release, assets, checksums, and tested installation command. Confirm public
downloads without authentication. Leave the original backup private.

## Verification contract

- All existing and new tests pass with synthetic fixtures.
- Two different files with the same version token both remain represented.
- Exact duplicate copies can still form one version.
- Unreadable inputs remain visible as review-required, including an all-invalid
  folder, and retain the nonzero exit status.
- Invalid keep/pivot options fail as usage errors. Cache paths cannot overwrite
  any input, including aliases to an existing file.
- A fresh environment installs the wheel and runs fingerprint, compare, lineage,
  help, and version without third-party runtime libraries.
- Wheel and source archive contain only intended public files and license.
- Sanitized history has the same historical trees, preserves commit order, and
  contains no original email address or session link in retained metadata.
- A secret scan of the final history and package contents has no unresolved match.
- The public release and assets are reachable unauthenticated; repository settings
  still reject pull requests and disable issues, discussions, and Actions.

## Failure and recovery

Before publication, stop if tests, scans, packaging, or control verification fail.
Do not publish a partial release. If remote refs changed during preparation,
stop the push and reconcile the new work. Keep the private bundle as the recovery
source for the original commits. A later discovered release defect is handled by
fixing the code and publishing a new version; do not silently replace an asset.

## Definition of done

The repository and versioned download are public, the documented installation
works, private metadata is removed from retained history, owner controls are
verified, and the owner has a short guide to maintenance and gradual reopening.

## Sources

- Existing source and tests in the original six-commit development history.
- GitHub: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/disabling-pull-requests
- GitHub API: https://docs.github.com/en/rest/repos/repos#update-a-repository
- History cleanup limits: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
- Existing unrelated distribution: https://pypi.org/project/xldiff/
