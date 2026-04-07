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
    {
      "<leader>gyp",
      function()
        local path = vim.fn.expand("%:.")
        local line = vim.fn.line(".")
        local ref = path .. ":" .. line
        vim.fn.setreg("+", ref)
        vim.notify(ref, vim.log.levels.INFO, { title = "Copied" })
      end,
      desc = "Copy path:line",
      mode = { "n" },
    },
    {
      "<leader>gyp",
      function()
        local path = vim.fn.expand("%:.")
        local start_line = vim.fn.line("'<")
        local end_line = vim.fn.line("'>")
        local ref = start_line == end_line
          and path .. ":" .. start_line
          or path .. ":" .. start_line .. "-" .. end_line
        vim.fn.setreg("+", ref)
        vim.notify(ref, vim.log.levels.INFO, { title = "Copied" })
      end,
      desc = "Copy path:line",
      mode = { "v" },
    },
  },
}
