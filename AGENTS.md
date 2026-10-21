* Python scripts go into `py/`
* Shell scripts go into `sh/`
* TypeScript scripts go into `ts/`
* All scripts that are intended to be exposed are put into their respective type specific folder and then symlinked into `bin/` with the same name without an extension.
* Always use a uv shebang for python scripts: `#!/usr/bin/env -S uv run --no-config --script` (`--no-config` keeps uv from reading the cwd's `pyproject.toml`/`uv.toml`)
