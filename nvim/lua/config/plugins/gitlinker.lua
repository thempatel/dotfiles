return {
  "linrongbin16/gitlinker.nvim",
  dependencies = "nvim-lua/plenary.nvim",
  config = function()
    require("gitlinker").setup({})
  end,
  keys = {
    {
      "<leader>gyl",
      "<cmd>GitLink<cr>",
      desc = "Copy line URL",
      mode = { "n", "v" },
    },
    {
      "<leader>gyf",
      function()
        require("gitlinker").link({
          router_type = "browse",
          router = function(lk)
            local url = require("gitlinker")._browse(lk)
            if url then
              return url:gsub("#.*$", "")
            end
          end,
        })
      end,
      desc = "Copy file URL",
      mode = { "n" },
    },
    {
      "<leader>gB",
      "<cmd>GitLink! blame_default_branch<cr>",
      desc = "GitHub Blame",
      mode = { "v", "n" },
    },
  },
}
