return {
  "gregorias/toggle.nvim",
  dependencies = { "folke/which-key.nvim" },
  version = "1.0",
  event = "VeryLazy",
  config = function()
    ---@diagnostic disable: missing-fields
    local toggle = require("toggle")
    toggle.setup({
      -- toggle.nvim 1.0's which-key registry uses the deprecated v1 API, which
      -- doesn't create keymaps under which-key v3. Register them directly with
      -- vim.keymap.set; which-key still surfaces them via their descriptions.
      keymap_registry = require("toggle.keymap").plain_keymap_registry,
      keymaps = {
        toggle_option_prefix = "<leader>u",
        status_dashboard = "<leader>us",
      },
    })

    local hard_wrap_textwidth = 100
    toggle.register(
      "W",
      toggle.option.NotifyOnSetOption(toggle.option.OnOffOption({
        name = "hard wrap (tw=" .. hard_wrap_textwidth .. ")",
        get_state = function()
          return vim.bo.textwidth == hard_wrap_textwidth
        end,
        set_state = function(enabled)
          if enabled then
            vim.bo.textwidth = hard_wrap_textwidth
            vim.opt_local.formatoptions:append("t")
            vim.opt_local.formatoptions:append("c")
          else
            vim.bo.textwidth = 0
            vim.opt_local.formatoptions:remove("t")
            vim.opt_local.formatoptions:remove("c")
          end
        end,
      }))
    )

    local wk = require("which-key")
    wk.add({
      { "<leader>u", group = "Toggle", icon = "󰨚 " },
    })
  end,
}
