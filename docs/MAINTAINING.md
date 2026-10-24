# Maintain xldiff

This guide is for Fernando, the repository owner. Development, verification,
and package builds run locally. GitHub Actions stays disabled. The public
repository does not accept pull requests, issues, or discussions, and it makes
no support commitment. Keep [CONTRIBUTING.md](../CONTRIBUTING.md) consistent
with the actual repository controls.

## Make and verify a local change

1. Use a local branch for the change. Preserve unrelated work.
2. Make the smallest change that meets the intended behavior.
3. Update the documentation and changelog for changed behavior.
4. Run the local tests with invented workbooks.
5. Review the change and its failure cases before choosing a release version.

For a standard Python development environment, install the development extras
and run pytest from the repository root:

```sh
python -m pip install -e ".[dev]"
python -m pytest -q
```

The default fixture backend is openpyxl. Other maintainers and fork owners
can use this route without MOG. openpyxl and pytest are development dependencies,
not runtime dependencies.

On a host that requires MOG for workbook creation, use the optional backend:

```sh
XLDIFF_TEST_BACKEND=mog python -m pytest -q
python examples/demo.py demo-workbooks-mog --backend mog
```

MOG must already be installed and configured. `MOG_BIN` can select its executable.
If the host requires a script guard, set `MOG_GUARD_COMMAND` to the guard command,
including its interpreter and arguments. The generator splits that value with
Python's `shlex.split` and appends `--add` and the generated script path.
It does not invoke a shell. Shell operators and variable expansion do not work
inside that value. Quote command arguments that contain spaces.

The MOG generator uses a documented log exception for exact disposable fixtures.
An extra logging worksheet would change their expected contents. Do not apply
that fixture exception to ordinary workbook work. Follow the host's MOG rules.

## Prepare a versioned package locally

1. Choose an unused version. Update `pyproject.toml`, `src/xldiff/__init__.py`,
   `CHANGELOG.md`, and the README release links together.
2. Run the tests and review the regression cases. Check distinct same-version
   contents, exact copies, unreadable-only inputs, invalid options, and cache aliases.
3. Use a local environment with the build frontend installed. Run
   `python -m build` to create the wheel and source distribution in `dist/`.
4. Inspect both archives. Include the license, intended source, documentation,
   and invented example generator. Exclude private workbooks, local caches,
   credentials, backups, and unrelated files.
5. Create a fresh virtual environment. Install the exact wheel file from `dist/`.
   Confirm that the package declares no runtime dependencies.
6. Generate invented examples separately with a permitted backend. Run the
   installed `fingerprint`, `compare`, and `lineage` commands against them.
   Check text output, JSON, cache output, help, and the reported version.
7. Run an approved local security scan over the intended source, full retained
   history, metadata, and extracted package contents. Review each finding.
   Check for credentials, personal addresses, session links, and private data.
8. Generate SHA-256 checksums for the final wheel and source distribution.
   Write the two filenames and their hashes to `SHA256SUMS.txt`.
9. Save dated local verification results outside the public package. Stop if a
   required check fails or a security finding remains unresolved.

The initial public release uses these filenames:

```text
xldiff-0.1.1-py3-none-any.whl
xldiff-0.1.1.tar.gz
SHA256SUMS.txt
```

Keep private recovery material outside the repository and release assets.
Before an authorized history rewrite, make and verify a private recovery bundle.
Preserve the development sequence and historical file contents when removing
private metadata. Routine releases do not require a history rewrite.

GitHub can retain old commit pages after a rewrite. Before the first public
release, the original repository stays private and the cleaned history is
published into a separate repository under the public project name. Preserve
the original development steps; a new GitHub repository does not require an
empty Git history. See [GitHub's history cleanup limits](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).

An old checkout can reintroduce the removed metadata if its history is merged
into the public repository. Use a fresh clone of the public repository for
future work, or verify that an existing checkout has the cleaned history.
Keep any checkout of the original history connected only to the private
recovery repository. Do not merge the private recovery history into public work.

## Audit the repository controls

Before publication, inspect the repository settings and read them back after
any change. Record what you verified and when. Documentation alone does not
establish that a control is active.

- In **Settings**, under **General** and **Features**, disable pull requests,
  issues, discussions, wikis, and projects. GitHub documents the controls for
  [pull requests](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/disabling-pull-requests),
  [issues](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/disabling-issues),
  [discussions](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/enabling-or-disabling-github-discussions-for-a-repository),
  [wikis](https://docs.github.com/en/communities/documenting-your-project-with-wikis/disabling-wikis),
  and [projects](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/disabling-projects-in-a-repository).
- In **Settings**, under **Actions** and **General**, disable all Actions.
  Do not add release workflows, bots, or hosted build services.
  See [GitHub Actions settings](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository).
- Keep **Allow auto-merge** off. Check that branch rules do not require a merge
  queue, which can allow automatic merging independently of that setting.
  See [GitHub's auto-merge control](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-auto-merge-for-pull-requests-in-your-repository).
- Audit collaborators, pending invitations, installed apps, deploy keys,
  webhooks, and configured automation. Keep access owner-only unless Fernando
  explicitly changes that policy. See
  [personal repository permissions](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/permission-levels-for-a-personal-account-repository).
- Protect the default branch against deletion and force pushes, including by
  administrators. Normal owner updates remain possible; no automated status
  check or pull request is required for this owner-maintained workflow.
- For additional comment protection, set repository interaction limits to
  **Collaborators only** for six months. GitHub's interaction limit expires;
  review or renew it when needed. Its expiry does not re-enable the separately
  disabled pull requests, issues, or discussions. See
  [interaction limits](https://docs.github.com/en/rest/interactions/repos#set-interaction-restrictions-for-a-repository).

Repeat the audit after publication and before later releases. Keep Actions off
when opening another feature. A change to one setting does not authorize a
change to another.

## Publish only after an explicit decision

Local preparation does not authorize a push, a visibility change, or publication.
Present the verified version, exact commit and tag, package filenames, checksums,
scan results, and repository-control audit for the owner's decision.
Keep private identifiers out of public release notes.

After the owner authorizes the specific release:

1. Confirm that remote refs still match the reviewed state. Stop if they changed.
2. Push only the intended release commit and version tag.
3. Create a draft release for that tag. Attach the reviewed wheel, source
   distribution, and `SHA256SUMS.txt`. Review the notes and asset names.
4. Change repository visibility only if that action is explicitly authorized.
5. Publish the release. Do not create a release discussion.
6. Download the public assets without authentication. Verify their checksums.
7. Install the public wheel URL in a fresh environment. Check the version and
   commands against invented workbooks.
8. Read back the repository controls again. Record the public download and
   installation results.

See GitHub's official guide to
[managing releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository).
Version 0.1.1 uses
[this release page](https://github.com/Fergonz1993/xldiff/releases/tag/v0.1.1).

Do not upload to PyPI. `pip install xldiff` resolves to an unrelated project.
Keep the project name and distribute through versioned GitHub release assets.

If a published package needs a fix, publish a new version with new filenames,
checksums, and a new tag. Do not swap package assets or move the old tag.
Document the affected version and correction in the changelog. Update README
installation links to the new exact wheel URL. Release-note corrections can
clarify a defect, but they do not replace a corrected package.

## Open participation only by choice

External contributions remain closed until Fernando chooses otherwise.
Opening a channel creates incoming work. Choose only a channel that the owner
is prepared to review, and change one control at a time.

1. State what the channel accepts and whether any response is promised.
2. Update `CONTRIBUTING.md` and the README for that decision.
3. Enable only issues, only discussions, or pull requests restricted to
   **Collaborators only**, using the official controls linked above.
4. Read back the setting. Keep unrelated features and Actions disabled.
5. Review the incoming work before deciding whether to open another channel.
   Close the channel again if the owner no longer wants that work.

If choosing collaborators-only pull requests, review access before inviting
anyone. Collaborators in a personal repository receive write access, not merely
permission to submit a pull request. Agree on the scope first. An invited person
can decline, stop contributing, or maintain a separate MIT fork. An invitation
does not create a support duty or an obligation to accept their work.
