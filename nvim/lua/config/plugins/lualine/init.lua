local M = {
  "nvim-lualine/lualine.nvim",
  dependencies = {
    "folke/noice.nvim",
  },
  event = "VeryLazy",
}

M.config = function()
  local components = require("config.plugins.lualine.components")

  require("lualine").setup({
    options = {
      theme = "auto",
      globalstatus = true,
      component_separators = "",
      section_separators = "",
      disabled_filetypes = { "dashboard", "Outline", "alpha" },
      icons_enabled = true,
    },
    tabline = {},
    extensions = {},
    sections = {
      lualine_a = {
        {
          "tabs",
          mode = 1,
          cond = function()
            return #vim.api.nvim_list_tabpages() > 1
          end,
        },
      },
      lualine_b = {
        components.diff,
      },
      lualine_c = {
        {
          require("noice").api.status.search.get,
          cond = require("noice").api.status.search.has,
          color = { fg = "#f0a275" },
        },
      },
      lualine_x = {
        components.treesitter,
        components.lsp,
      },
      lualine_y = {},
      lualine_z = {
        components.location,
        components.scrollbar,
      },
    },
  })
end

return M
