# Third-party components

The release ZIP contains this project's source, not bundled Node, REA, pefix or NuGet binaries.

- Node.js 24.19.0 is downloaded from nodejs.org by setup. Its license and third-party notices are included in the downloaded distribution: https://github.com/nodejs/node/blob/v24.19.0/LICENSE
- REA 6.5.0 and its dependencies are installed through npm using package-lock.json. Their license files remain in node_modules. REA: https://github.com/morluto/rea
- The optional demo downloads SQLitePCLRaw.provider.e_sqlite3 packages from NuGet. Package contents and notices remain in demo-inputs. Upstream: https://github.com/ericsink/SQLitePCL.raw
- Development verification downloads pefix 1.0.2 from its official GitHub release and additional public NuGet fixtures. pefix: https://github.com/FeathBow/pefix

All target DLL analysis is static. Test inputs are not executed.
