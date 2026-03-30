vim.keymap.set("i", "t", require("config.langs.javascript").add_async, { buffer = true })
vim.keymap.set("n", "<leader>k", require("config.langs.javascript").goto_exported_symbol, { buffer = true })
