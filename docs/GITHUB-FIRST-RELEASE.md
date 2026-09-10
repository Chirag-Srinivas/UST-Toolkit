# First GitHub release — simple guide

## The three pieces

- **Repository:** the online project folder containing readable source and help.
- **Commit:** a recorded snapshot of that folder.
- **Release:** a named download page linked to a particular code snapshot.

Your GitHub account is `Chirag-Srinivas`. The private repository is
`Chirag-Srinivas/UST-Toolkit`. Source and documentation are uploaded, and the
[prepared toolkit prerelease](https://github.com/Chirag-Srinivas/UST-Toolkit/releases/tag/v1.0.0-prepared)
provides the exact runtime bundle and checksum. Follow the
[download guide](RUNTIME-DOWNLOAD.md) to use it without rebuilding Java.

You will have one repository called `UST-Toolkit`, with two downloads described
on its release page: a fresh toolkit ZIP and a frozen MSc research ZIP.
No further development is promised. Users can still read and reuse the code
under its published licence.

## Publishing after the local release review

1. Completed: create the **private** `UST-Toolkit` repository.
2. Completed: upload the prepared source and documentation and provide the
   exact runtime bundle as a prerelease download.
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
