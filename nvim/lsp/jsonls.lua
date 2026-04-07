-- Install with: setup/02-lsp.sh (vscode-langservers-extracted via npm)
return {
  settings = {
    json = {
      schemas = require("schemastore").json.schemas(),
      format = {
        enable = true,
      },
      validate = { enable = true },
    },
  },
}
