---
paths:
  - "**/*.py"
---

* Always use `typer` for clis
  * Unless the command has subcommands, prefer `typer.run(main)` over `@app.command`
* Always use UV shebang for clis
* Imports always go at the top and not within functions/conditionals
