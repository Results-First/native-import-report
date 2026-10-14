# Third-party components

The release ZIP contains this project's source, not bundled Node, REA, pefix or NuGet binaries.

- Node.js 24.19.0 is downloaded from nodejs.org by setup. Its license and third-party notices are included in the downloaded distribution: https://github.com/nodejs/node/blob/v24.19.0/LICENSE
- REA 6.5.0 and its dependencies are installed through npm using package-lock.json. Their license files remain in node_modules. REA: https://github.com/morluto/rea
- The optional demo downloads SQLitePCLRaw.provider.e_sqlite3 packages from NuGet. Package contents and notices remain in demo-inputs. Upstream: https://github.com/ericsink/SQLitePCL.raw
- Development verification downloads pefix 1.0.2 from its official GitHub release and additional public NuGet fixtures. pefix: https://github.com/FeathBow/pefix

All target DLL analysis is static. Test inputs are not executed.

The local native-check prototype additionally downloads LIEF 0.17.3 (Apache-2.0) from PyPI into `.native-tools`, verified against a pinned wheel SHA-256. Upstream license: https://github.com/lief-project/LIEF/blob/0.17.3/LICENSE. Its verification uses pefile 2024.8.26 (MIT), macholib 1.16.3 (MIT), and altgraph 0.17.4 (MIT) installed into `.test-tools/native-oracle`. Public Wasmtime, SkiaSharp, SQLitePCLRaw, and LibGit2Sharp NuGet packages retain their upstream notices in the original archives under `evidence/native-packages`. These dependencies and fixtures are not bundled in this project's source.
