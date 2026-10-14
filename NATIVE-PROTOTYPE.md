# Native import/export checker prototype

Checks whether a compiled .NET DLL's declared native function names appear in a native library you explicitly supply. Targets are inspected without execution. Included in the v0.2 free evaluation source release, alongside the original declaration comparison. This is an evaluation tool with the limitations listed below.

## Run it

Requires Windows x64 with **CPython 3.11**. Internet is needed for initial setup and public examples. No paid account, .NET SDK, preinstalled Node, or sibling project is required. Setup installs the pinned Node/REA runtime and checksum-verified LIEF wheel locally.

```powershell
python setup_native.py
python demo_native.py
```

The default example downloads hash-verified Wasmtime 48.0.2 and checks its macOS ARM64 library. It produces a report under `demo-reports` and exits **3**, because it finds the real missing name. This is the expected demo result.

For a matching example:

```powershell
python demo_native.py --case sqlite
```

Other examples: `wasmtime-x64`, `skiasharp`, `libgit2`, and `skiasharp-mixed`.

For your own files:

```powershell
python check_native.py "C:\input\Managed.dll" "C:\input\Native.dll" --module "exact-declared-module-name" --out "C:\output\new-report"
```

`--module` must be the exact module name recorded in the managed DLL, such as `wasmtime`, `libSkiaSharp`, or `e_sqlite3`. It is an explicit pairing assertion, not a discovered runtime path. Unmatched modules are listed as unresolved. Output directories must be new. Reports include local file paths, so review them before sharing.

## Results

- **found:** the exact exported name is present. This does not verify a function signature or successful call.
- **missing:** the name is absent from this supplied library's supported export inventory. This does not prove a running application selects this library or reaches that call.
- **unresolved:** the module has no supplied mapping, lookup needs unsupported rules, or an export forwards elsewhere.

Exit **0** means all declarations were matched by name. Exit **3** means missing names were found with no unresolved declarations. Exit **2** means incomplete analysis or an error. If both missing and unresolved entries exist, exit 2 takes precedence and the report retains both. A clean-looking partial mapping is never presented as a complete result.

Supports AMD64 Windows PE and thin macOS ARM64/x64 Mach-O native files. ELF, fat Mach-O, PE x86/ARM64, ordinals, forwarded destinations, and full Windows suffix-probing semantics are outside this prototype. A/W-only candidates are unresolved. Mach-O re-exporting libraries prevent a conclusive absence result. Empty export inventories and parser diagnostics fail closed. Files are limited to 256 MiB. Parsing runs in a separate process with a timeout, not a security sandbox.

Runtime dependency search, custom resolvers, platform reachability, ABI/signature matching, and native function execution are not checked. The checker may list imports that are unused on the chosen OS. It does not claim the full application is compatible.

## Verification performed on 2026-10-14

| Real artifacts | Found declarations | Missing declarations | Unresolved declarations | Result |
| --- | ---: | ---: | ---: | --- |
| Wasmtime 48.0.2, macOS ARM64 | 197 | 1 | 0 | Reported Mach-port name mismatch detected |
| Wasmtime 48.0.2, macOS x64 | 197 | 1 | 0 | Same mismatch detected |
| SkiaSharp 3.119.0 + matching Windows native assets | 877 | 0 | 10 | Selected library matches; other modules unresolved |
| SQLite provider/native library 2.1.11 | 149 | 0 | 0 | All declared names found |
| LibGit2Sharp 0.31.0 + NativeBinaries 2.0.323 | 369 | 0 | 2 | Selected library matches; other modules unresolved |
| SkiaSharp 3.119.0 + deliberately older 2.88.9 native assets | 811 | 66 | 10 | Wrong-version names detected; other modules unresolved |

Counts preserve duplicate declarations. Wasmtime's 198 declarations represent 197 unique pairs. The SkiaSharp mixed-version pairing is deliberately constructed from real released packages, not claimed as a user's reproduced incident.

Independent pefix inventories agree with all managed inputs. Independent pefile (PE) and macholib (Mach-O) exported-name sets agree with LIEF for every native input. Expected missing names were independently recomputed from those inventories. Eight tests cover exact matching, suffix ambiguity, forwarders, ordinals, re-export uncertainty, malformed input, wrong mapping and output preservation.

A fresh source-only folder, without a copied runtime, dependencies, or fixture cache, completed setup and both the SQLite and Wasmtime examples. Python itself was supplied by this Windows machine. No operator reproduction is needed to establish these reported CLI results; testing on other machines remains outstanding.

Repeat verification:

```powershell
python test_native.py
python verify_native.py
python verify_native_portable.py
```

Durable evidence:

- `evidence/native-20261014T184004562285Z/verification.json` and per-case reports/raw parser output.
- `evidence/native-portable-20261014T184125094185Z/verification.json` with setup/example logs.
- `evidence/native-packages/` retains pinned package files and extracted artifact provenance.

## Readiness

The Windows GitHub Actions workflow runs the native checker on Python 3.11, all six real-package cases, lookup/failure tests, and installation from the source ZIP. Check the linked repository's Actions results for the release commit. Local historical evidence paths above are not bundled. Broader format support is not promised by this evaluation. Paid demand remains unverified.

The Ops dashboard on port 8008 responded healthy during verification. It contains no matching native-checker entry, so no dashboard readiness score is being used or changed.
