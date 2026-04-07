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

  require("mini.surround").setup({})
end

return M
