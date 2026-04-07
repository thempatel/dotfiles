local M = {}

M.setup = function()
  local handlers = require("config.plugins.lsp.handlers")

  vim.lsp.enable("kulala_ls") -- setup/02-lsp.sh
  vim.lsp.enable("tsgo") -- setup/02-lsp.sh
  vim.lsp.enable("ty") -- mise
  vim.lsp.enable("rust_analyzer") -- mise
  vim.lsp.enable("lua_ls") -- mise
  vim.lsp.enable("jsonls") -- setup/02-lsp.sh
  vim.lsp.enable("yamlls") -- setup/02-lsp.sh
  vim.lsp.enable("html") -- setup/02-lsp.sh
  vim.lsp.enable("gopls") -- setup/02-lsp.sh
  vim.lsp.enable("bashls") -- setup/02-lsp.sh

  vim.lsp.config("*", {
    capabilities = handlers.capabilities(),
  })

  vim.api.nvim_create_autocmd("LspAttach", {
    group = vim.api.nvim_create_augroup("lsp-attach", { clear = true }),
    callback = function(event)
      local client = vim.lsp.get_client_by_id(event.data.client_id)
      handlers.on_attach(client, event.buf)

      if client ~= nil and client.name == "gopls" then
        vim.api.nvim_create_autocmd("BufWritePre", {
          pattern = { "*.go" },
          callback = function()
            local params = vim.lsp.util.make_range_params(nil, "utf-16")
            ---@diagnostic disable-next-line: inject-field
            params.context = { only = { "source.organizeImports" } }
            local result = vim.lsp.buf_request_sync(0, "textDocument/codeAction", params, 3000)
            for _, res in pairs(result or {}) do
              for _, r in pairs(res.result or {}) do
                if r.edit then
                  vim.lsp.util.apply_workspace_edit(r.edit, "utf-16")
                else
                  vim.lsp.buf.execute_command(r.command)
                end
              end
            end
          end,
        })
      end
    end,
  })
end

return M
