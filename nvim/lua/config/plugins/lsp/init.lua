return {
  "neovim/nvim-lspconfig",
  event = { "LspAttach", "InsertEnter", "BufWinEnter", "BufNewFile" },
  dependencies = {
    { "saghen/blink.cmp", event = { "InsertEnter", "CmdlineEnter" } },
    { "b0o/schemastore.nvim", event = "InsertEnter" },
  },
  config = function()
    require("config.plugins.lsp.servers").setup()
    require("lspconfig.ui.windows").default_options.border = "rounded"

    vim.keymap.set("n", "<leader>lr", "<cmd>LspRestart all<CR>", { silent = true, desc = "Restart All Servers" })
  end,
}
