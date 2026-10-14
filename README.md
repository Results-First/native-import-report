# Native Import Report

Compare the native-library import declarations in two compiled .NET DLLs without executing either DLL. Produces a Markdown report and JSON evidence with file hashes, metadata offsets, declaration counts and mapping flags.

**Free evaluation release.** This is a static declaration comparison, not a runtime compatibility or security verdict.

## Quick start

Requires Windows x64 and Python 3.10 or newer. Python 3.11 or newer is recommended for a new installation. No preinstalled Node, npm, REA, .NET SDK, account or API key is needed.

1. Download and extract the source ZIP from [Releases](https://github.com/Results-First/native-import-report/releases).
2. Open PowerShell in the extracted `native-import-report` directory.
3. Run:

```powershell
python setup.py
python demo.py
```

Setup installs a checksum-verified Node 24.19.0 and locked REA 6.5.0 dependencies inside this directory. It changes no global runtime. Internet is needed for setup and the first demo download. Later comparisons run locally.

The demo downloads two small, hash-pinned public SQLite provider packages, checks the real DLLs and prints the report path. Expected result: four added imports and one removed import. No private files are needed. Subsequent demo runs reuse the verified downloads.

## Compare your files

```powershell
python compare.py "C:\path\old.dll" "C:\path\new.dll" --out "C:\path\new-report"
```

Choose a new report directory for each run. Existing output directories are refused. Open `report.md` for the summary. `report.json` retains full declarations and raw REA output is saved beside it. Reports include local input paths, so review them before sharing.

Exit 0 means the comparison completed, including when changes were found. Exit 2 means incomplete analysis or an input/output error. Incomplete coverage is never presented as a clean comparison. If setup fails, inspect `.runtime/npm-install.stderr.txt` and rerun `python setup.py`. No uninstall is needed to retry.

## What the report means

Matching uses exact native library and entry-point names. Duplicate declaration counts and mapping-flag distributions are preserved. A native library name change appears as removed and added imports, not proof that the underlying functions disappeared.

This tool does **not** verify native exports, managed signatures, ABI compatibility, actual calls or runtime loading. It cannot detect a native export disappearing when the managed declarations stay unchanged. Build-local metadata tokens are not treated as identities across versions.

## Real-package verification

| Package pair | Old/new declarations | Added/removed unique imports |
| --- | --- | --- |
| SQLitePCLRaw.provider.e_sqlite3 2.1.11 to 3.0.3 | 149 / 152 | 4 / 1 |
| SkiaSharp 2.88.9 to 3.119.0 | 923 / 887 | 66 / 102 |
| LibGit2Sharp 0.30.0 to 0.31.0 | 369 / 371 | 353 / 353 |
| Newtonsoft.Json 13.0.1 to 13.0.3 | 0 / 0 | 0 / 0 |

Inventories are independently compared against pefix 1.0.2. LibGit2Sharp changes its native library name from `git2-a418d9d` to `git2-3f4182d`, explaining the large pair count. Targets are not executed.

[Windows CI](https://github.com/Results-First/native-import-report/actions/workflows/verify.yml) runs the checks on Python 3.11 and 3.13, including isolated ZIP installation, the public demo and offline repair. See the run results for the current status.

For development, clone the repository, run setup, then:

```powershell
python test_setup.py
python test_compare.py
python verify_packages.py
python build_release.py
python verify_portable.py
```

Tests download public fixtures and a checksum-pinned independent verifier. No sibling workspace or pre-existing cache is required. Offline tests set dead proxies and npm offline mode. They are not an OS-level network sandbox.

## Evaluation feedback

Please [open an issue](https://github.com/Results-First/native-import-report/issues) with Windows/Python versions, the command used and the outcome. Do not attach private DLLs, credentials or unreviewed reports. For usefulness feedback: did a reported change affect an upgrade decision, and how did this compare with your existing method?

## License

Free to use for evaluation under [LICENSE](LICENSE). This is an evaluation license, not an unrestricted open-source license. Downloaded dependencies retain their own licenses. See [THIRD-PARTY.md](THIRD-PARTY.md).
