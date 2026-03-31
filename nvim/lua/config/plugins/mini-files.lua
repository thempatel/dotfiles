return {
  "echasnovski/mini.files",
  dependencies = { "folke/which-key.nvim" },
  version = "*",
  keys = {
    {
      "<leader>e",
      function()
        local MiniFiles = require("mini.files")
        if not MiniFiles.close() then
          MiniFiles.open(vim.api.nvim_buf_get_name(0), false)
        end
      end,
      desc = "Files",
    },
  },
  init = function()
    local wk = require("which-key")
    wk.add({
      { "<leader>e", desc = "Files", icon = " ", mode = "n" },
    })

    local function open_files(data)
      local directory = vim.fn.isdirectory(data.file) == 1
      if not directory then
        return
      end
      vim.cmd.cd(data.file)
      require("mini.files").open(vim.api.nvim_buf_get_name(0), false)
    end
    vim.api.nvim_create_autocmd({ "VimEnter" }, { callback = open_files })

    vim.api.nvim_create_autocmd("User", {
      pattern = "MiniFilesWindowUpdate",
      callback = function(args)
        vim.wo[args.data.win_id].number = true
        vim.wo[args.data.win_id].relativenumber = true
      end,
    })
  end,
  config = function()
    require("mini.files").setup({
      windows = {
        preview = false,
        max_number = math.huge,
        width_focus = 30,
        width_nofocus = 20,
        width_preview = 25,
      },
      mappings = {
        synchronize = "<leader>bw",
      },
      use_as_default_explorer = true,
    })

    vim.api.nvim_create_autocmd("User", {
      pattern = "MiniFilesActionRename",
      callback = function(event)
        require("config.plugins.lsp.handlers").on_rename(event.data.from, event.data.to)
      end,
    })
  end,
}
