local M = {
  "folke/which-key.nvim",
  event = "VeryLazy",
}

M.config = function()
  local wk = require("which-key")

  wk.setup({
    preset = "helix",
    icons = {
      breadcrumb = "»",
      separator = "→",
      group = "",
      mappings = false,
      rules = false,
    },
    win = {
      padding = { 1, 1 },
    },
    triggers = {
      { "<auto>", mode = "nistc" },
      { "<leader>", mode = "x" },
    },
    sort = { "alphanum", "mod" },
    disable = {
      ft = { "minifiles" },
    },
    notify = false,
    show_help = false,
    show_keys = false,
    plugins = {
      marks = false,
      registers = false,
      presets = {
        operators = false,
        motions = false,
        text_objects = false,
        windows = false,
        nav = false,
        z = false,
        g = false,
      },
    },
  })
  local opts = {
    mode = "n",
    prefix = "<leader>",
    buffer = nil,
    silent = true,
    noremap = true,
    nowait = false,
  }
  wk.add({
    { "<leader>*", hidden = true, nowait = false, remap = false },
    { "<leader><Tab>", group = "Tabs", icon = "󰆍 ", nowait = false, remap = false },
    { "<leader>b", group = "Buffers", icon = "󰉋 ", nowait = false, remap = false },
    { "<leader>c", group = "Code", icon = "󰅲 ", nowait = false, remap = false },
    { "<leader>f", group = "Find", icon = "󰍉 ", nowait = false, remap = false },
    { "<leader>g", group = "Git", icon = "󰊢 ", nowait = false, remap = false },
    { "<leader>gy", group = "Copy URLs", icon = "󰌷 ", nowait = false, remap = false },
    { "<leader>h", group = "Gitsigns", icon = "󰊕 ", nowait = false, remap = false },
    { "<leader>l", group = "LSP", icon = "󰚵 ", nowait = false, remap = false },
    { "<leader>p", group = "Panes", icon = " ", nowait = false, remap = false },
    { "<leader>pr", "<C-w>l", desc = "Move Right", nowait = false, remap = false },
    { "<leader>pl", "<C-w>h", desc = "Move Left", nowait = false, remap = false },
    { "<leader>pc", group = "Create", nowait = false, remap = false },
    { "<leader>pcr", "<cmd>vsplit<cr><C-w>l", desc = "Split Right", nowait = false, remap = false },
    { "<leader>pcl", "<cmd>vsplit<cr>", desc = "Split Left", nowait = false, remap = false },
    { "<leader>pd", group = "Close", nowait = false, remap = false },
    { "<leader>pdr", "<C-w>l<cmd>q<cr>", desc = "Close Right", nowait = false, remap = false },
    { "<leader>pdl", "<C-w>h<cmd>q<cr>", desc = "Close Left", nowait = false, remap = false },
    { "<leader>t", "<cmd>terminal<cr>", desc = "Terminal", icon = " ", nowait = false, remap = false },
  }, opts)

  -- Hide g-prefix keymaps we don't need in which-key
  wk.add({
    { "gc", hidden = true },
    { "gj", hidden = true },
    { "gO", hidden = true },
    { "gx", hidden = true },
    { "gY", hidden = true },
    { "ge", hidden = true },
    { "gh", hidden = true },
    { "gH", hidden = true },
    { "gra", hidden = true },
    { "gri", hidden = true },
    { "grn", hidden = true },
    { "grr", hidden = true },
    { "grt", hidden = true },
    { "grx", hidden = true },
    { "g%", hidden = true },
    { "g[", hidden = true },
    { "g]", hidden = true },
  })
end

return M
