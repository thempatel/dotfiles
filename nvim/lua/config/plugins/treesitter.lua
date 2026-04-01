local M = {
  "nvim-treesitter/nvim-treesitter",
  build = ":TSUpdate",
  event = { "BufReadPre", "BufNewFile" },
  dependencies = {
    { "JoosepAlviste/nvim-ts-context-commentstring" },
    "andymass/vim-matchup",
  },
}

M.opts = {
  auto_install = true,
  ensure_installed = {
    "c",
    "lua",
    "vim",
    "vimdoc",
    "query",
    "typescript",
    "javascript",
    "html",
    "http",
    "graphql",
    "css",
    "json",
    "yaml",
    "bash",
    "markdown",
    "markdown_inline",
    "dockerfile",
    "go",
    "java",
    "jsonc",
    "regex",
    "ruby",
    "scss",
    "tsx",
    "ninja",
    "python",
    "rust",
    "rst",
    "toml",
  },
}

M.config = function(_, opts)
  require("nvim-treesitter").setup(opts)
  require("ts_context_commentstring").setup({
    enable_autocmd = false,
  })
  vim.g.matchup_matchparen_offscreen = { method = "popup" }
end

return M
