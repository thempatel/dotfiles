local ensure_installed = {
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
  "regex",
  "scss",
  "tsx",
  "ninja",
  "python",
  "rust",
  "rst",
  "toml",
}

local M = {
  "nvim-treesitter/nvim-treesitter",
  branch = "main",
  build = ":TSUpdate",
  main = "nvim-treesitter",
  dependencies = {
    { "JoosepAlviste/nvim-ts-context-commentstring" },
    "andymass/vim-matchup",
  },
}

M.init = function()
  vim.api.nvim_create_autocmd("FileType", {
    callback = function()
      pcall(vim.treesitter.start)
      vim.bo.indentexpr = "v:lua.require'nvim-treesitter'.indentexpr()"
    end,
  })
end

M.config = function()
  local already_installed = require("nvim-treesitter.config").get_installed()
  local to_install = vim.iter(ensure_installed)
    :filter(function(parser)
      return not vim.tbl_contains(already_installed, parser)
    end)
    :totable()
  if #to_install > 0 then
    require("nvim-treesitter").install(to_install)
  end

  require("ts_context_commentstring").setup({
    enable_autocmd = false,
  })
  vim.g.matchup_matchparen_offscreen = { method = "popup" }
end

return M
