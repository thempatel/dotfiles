local M = {
  "nvim-mini/mini.nvim",
  version = false,
  dependencies = {
    "JoosepAlviste/nvim-ts-context-commentstring",
  },
  event = "BufReadPre",
}

function M.config()
  require("mini.comment").setup({
    options = {
      custom_commentstring = function()
        if vim.bo.filetype == "minifiles" then
          return
        end
        return require("ts_context_commentstring.internal").calculate_commentstring() or vim.bo.commentstring
      end,
    },
  })

  require("mini.jump").setup({})
  require("mini.move").setup({
    mappings = {
      left = "H",
      right = "L",
      down = "J",
      up = "K",
      line_left = "",
      line_right = "",
      line_down = "",
      line_up = "",
    },
  })
  require("mini.surround").setup({})

  local spec_treesitter = require("mini.ai").gen_spec.treesitter
  require("mini.ai").setup({
    n_lines = 500,
    search_method = "cover_or_next",
    custom_textobjects = {
      F = spec_treesitter({ a = "@function_declaration.outer", i = "@function_declaration.inner" }),
    },
    o = spec_treesitter({
      a = { "@block.outer", "@conditional.outer", "@loop.outer" },
      i = { "@block.inner", "@conditional.inner", "@loop.inner" },
    }),
    f = spec_treesitter({ a = "@function.outer", i = "@function.inner" }),
  })
end

return M
