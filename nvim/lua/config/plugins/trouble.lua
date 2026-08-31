return {
  "folke/trouble.nvim",
  dependencies = { "nvim-tree/nvim-web-devicons" },
  cmd = { "Trouble" },
  specs = {
    {
      "folke/snacks.nvim",
      opts = function(_, opts)
        return vim.tbl_deep_extend("force", opts or {}, {
          picker = {
            actions = require("trouble.sources.snacks").actions,
            win = {
              input = {
                keys = {
                  ["<c-t>"] = {
                    "trouble_open",
                    mode = { "n", "i" },
                  },
                },
              },
            },
          },
        })
      end,
    },
    {
      -- Same `<c-t>` handoff as the snacks picker above, so any fzf-lua result
      -- set can be reopened as a grouped, foldable Trouble list.
      "ibhagwan/fzf-lua",
      opts = function(_, opts)
        -- Has to mutate the defaults table rather than go through `opts`:
        -- an `actions.files` key in the setup options replaces fzf-lua's whole
        -- bind table instead of merging into it, which would take `enter` and
        -- the split/tab openers with it.
        require("fzf-lua.config").defaults.actions.files["ctrl-t"] =
          require("trouble.sources.fzf").actions.open
        return opts
      end,
    },
  },
  config = function()
    require("trouble").setup({})
  end,
}
