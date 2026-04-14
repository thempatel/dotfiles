* Python scripts go into `py/`
* Shell scripts go into `sh/`
* TypeScript scripts go into `ts/`
* All scripts that are intended to be exposed are put into their respective type specific folder and then symlinked into `bin/` with the same name without an extension.
* Always use a uv shebang for python scripts
