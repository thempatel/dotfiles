---
paths:
  - "**/*.py"
---

* Always use `typer` for clis
* All scripts should support short `-h` flag for `--help`:
```py
  app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})
```

* Always use UV shebang for clis
* Imports always go at the top and not within functions/conditionals
