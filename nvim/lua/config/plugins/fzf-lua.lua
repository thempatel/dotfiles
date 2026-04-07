return {
  "ibhagwan/fzf-lua",
  dependencies = { "nvim-tree/nvim-web-devicons" },
  cmd = "FzfLua",
  keys = {
    { "<leader>ff", "<cmd>FzfLua lsp_document_symbols<cr>", desc = "LSP Document Symbols" },
    { "<leader>fF", "<cmd>FzfLua lsp_workspace_symbols<cr>", desc = "LSP Workspace Symbols" },
    {
      "<leader>fg",
      function()
        require("fzf-lua").grep({
          search = "",
          rg_opts = table.concat({
            "--column",
            "--line-number",
            "--no-heading",
            "--color=always",
            "--smart-case",
            "--max-columns=4096",
            "-g '!{node_modules,.git,.direnv,dist,third-party}/'",
            "-g '!tsconfig.tsbuildinfo'",
            "-g '!yarn.lock'",
            "-g '!*.lock'",
            "-g '!*-lock.json'",
            "--hidden",
            "--trim",
          }, " "),
        })
      end,
      desc = "Grep",
    },
    {
      "<leader>*",
      function()
        require("fzf-lua").grep_cword()
      end,
      desc = "Grep Word Under Cursor",
    },
    { "<leader>fh", "<cmd>FzfLua helptags<cr>", desc = "Help Pages" },
    { "<leader>fb", "<cmd>FzfLua buffers<cr>", desc = "Buffers" },
    { "<leader>fc", "<cmd>FzfLua command_history<cr>", desc = "Command History" },
    { "<leader>fr", "<cmd>FzfLua resume<cr>", desc = "Resume" },
    { "<leader>fs", "<cmd>FzfLua git_status<cr>", desc = "Git Status" },
    {
      "<leader>fp",
      function()
        require("fzf-lua").files({
          fd_opts = "--type f --hidden --no-ignore --exclude node_modules --exclude .git --exclude .direnv --exclude dist --exclude third-party",
        })
      end,
      desc = "Find Files",
    },
  },
  opts = {
    defaults = {
      formatter = "path.filename_first",
    },
    winopts = {
      height = 0.7,
      width = 0.9,
      border = "rounded",
      preview = {
        layout = "horizontal",
        horizontal = "right:45%",
      },
    },
    fzf_opts = {
      ["--layout"] = "reverse",
    },
    keymap = {
      fzf = {
        ["ctrl-q"] = "select-all+accept",
      },
    },
  },
}
