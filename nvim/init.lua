vim.g.mapleader = " "
vim.g.do_filetype_lua = 1
vim.g.vim_json_conceal = false
vim.g.loaded_netrw = 1
vim.g.loaded_netrwPlugin = 1
vim.g.projects_dir = vim.env.HOME .. "/src"
require("config.lazy")
require("config.options")
require("config.keymaps")
require("config.autocmd")
require("config.winbar")
