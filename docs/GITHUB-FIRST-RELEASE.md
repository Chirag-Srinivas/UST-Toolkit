# First GitHub release — simple guide

## The three pieces

- **Repository:** the online project folder containing readable source and help.
- **Commit:** a recorded snapshot of that folder.
- **Release:** a named download page linked to a particular code snapshot.

Your GitHub account is `Chirag-Srinivas`. The planned repository is
`Chirag-Srinivas/UST-Toolkit` (not yet created).

You will have one repository called `UST-Toolkit`, with two downloads described
on its release page: a fresh toolkit ZIP and a frozen MSc research ZIP.
No further development is promised. Users can still read and reuse the code
under its published licence.

## Publishing after the local release review

1. Sign in to GitHub and create a new **private**, empty repository named
   `UST-Toolkit`. Leave GitHub's README, .gitignore and licence additions off,
   because this local folder already supplies the prepared files.
2. Connect the prepared local repository to that repository. GitHub Desktop
   can handle the upload, or Codex can help after you supply the repository URL.
3. Review the uploaded files and resolve the release checklist. No research
   ZIP, private machine settings or dependency folders belong in Git history.
4. Make the repository public when the reviewed code and licences are ready.
5. Create a release named `UST 1.0.0 — toolkit and frozen MSc study`, tied to a
   fixed code snapshot. Attach the fresh toolkit ZIP and checksum file.
6. Link the complete research ZIP from a suitable research archive/file host.
   GitHub release attachments must each be smaller than 2 GiB, while this study
   exceeds that size. A second repository does not remove that restriction.
7. Put both download links prominently in the README and release notes.

The large archive can remain one ZIP at an external host. Splitting it into
several parts is another option, but is less convenient for your readers.

Do not share passwords or access tokens in this conversation. Use GitHub's
normal sign-in flow when account access is needed.

Official introduction: https://docs.github.com/en/get-started/using-github/hello-world
Release limits: https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases
