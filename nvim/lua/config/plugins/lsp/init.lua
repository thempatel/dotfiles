return {
  "neovim/nvim-lspconfig",
  event = { "LspAttach", "InsertEnter", "BufWinEnter", "BufNewFile" },
  dependencies = {
    { "saghen/blink.cmp", event = { "InsertEnter", "CmdlineEnter" } },
  },
  config = function()
    require("config.plugins.lsp.servers").setup()
    require("lspconfig.ui.windows").default_options.border = "rounded"

    vim.keymap.set("n", "<leader>lr", "<cmd>lsp restart<CR>", { silent = true, desc = "Restart All Servers" })
  end,
}
