local keymap = vim.keymap.set

-- Store relative line number jumps in the jumplist.
keymap("n", "j", [[(v:count > 1 ? 'm`' . v:count : '') . 'gj']], { expr = true, silent = true })
keymap("n", "k", [[(v:count > 1 ? 'm`' . v:count : '') . 'gk']], { expr = true, silent = true })

keymap({ "i", "n" }, "<esc>", "<cmd>noh<cr><esc>", { desc = "Escape and clear hlsearch" })
-- keymap({ "n" }, "<CR>", "viw", { desc = "Select word under cursor" })

-- save and quit
keymap("n", "<leader><Tab>d", ":tabclose<CR>", { silent = true, desc = "Close Tab" })
keymap("n", "<leader><Tab>n", ":tabnext<CR>", { silent = true, desc = "Next Tab" })
keymap("n", "<leader><Tab>p", ":tabprevious<CR>", { silent = true, desc = "Previous Tab" })

-- Yank and paste use the system clipboard; deletes/changes stay in vim's own
-- registers (clipboard is unset), so they never clobber the clipboard.
-- (y/Y route to the "+ register via the sticky-yank maps in autocmd.lua.)
keymap("n", "p", '"+p', { silent = true })
keymap("n", "P", '"+P', { silent = true })
-- v_P pastes over the selection without overwriting the clipboard.
keymap("x", "p", '"+P', { silent = true })
keymap("x", "P", '"+P', { silent = true })
keymap("n", "n", "nzzzv", { silent = true })
keymap("n", "N", "Nzzzv", { silent = true })
keymap("v", "<", "<gv", { silent = true, desc = "Indent Less" })
keymap("v", ">", ">gv", { silent = true, desc = "Indent More" })




-- disable Ex mode, I always enter in it by mistake
keymap("n", "Q", "<Nop>", { silent = true })

-- buffers
keymap("n", "<leader><leader>", "<C-^>", { silent = true, desc = "Last Buffer" })
keymap("n", "<leader>bn", "<cmd>enew<cr>", { silent = true, desc = "New File" })
keymap("n", "<leader>bq", "<cmd>q<cr>", { silent = true, desc = "Quit File" })
keymap("n", "<leader>bo", function()
  local current_buffer = vim.api.nvim_get_current_buf()

  for _, bufnr in ipairs(vim.api.nvim_list_bufs()) do
    if bufnr ~= current_buffer then
      vim.api.nvim_buf_delete(bufnr, {})
    end
  end
end, { desc = "Close Other Buffers" })
keymap("n", "<leader>bw", "<cmd>w<cr>", { silent = true, desc = "Write File" })
keymap("n", "<leader>o", function()
  local buf = vim.api.nvim_get_current_buf()
  local name = vim.api.nvim_buf_get_name(buf)
  if name ~= "" and vim.fn.filereadable(name) == 1 then
    require("oil").open(vim.fn.fnamemodify(name, ":h"))
  end
end, { silent = true, desc = "Oil (buffer dir)" })
keymap("n", "<leader>bW", "<cmd>wa<cr>", { silent = true, desc = "Write All Files" })
keymap("n", "<leader>bQ", "<cmd>qa!<cr>", { silent = true, desc = "Quit nvim" })

if vim.opt.diff:get() then
  keymap("n", "<leader>1", ":diffget LOCAL<CR>", { silent = true, desc = "Take Local" })
  keymap("n", "<leader>2", ":diffget BASE<CR>", { silent = true, desc = "Take Base" })
  keymap("n", "<leader>3", ":diffget REMOTE<CR>", { silent = true, desc = "Take Remote" })
end

keymap("n", "<leader>lj", "<cmd>%!jq<cr>", { silent = true, desc = "[JSON] Format" })
keymap("n", "<leader>lJ", "<cmd>%!jq -c<cr>", { silent = true, desc = "[JSON] Compact Format" })



keymap("n", "<F10>", function()
  if vim.o.conceallevel > 0 then
    vim.o.conceallevel = 0
  else
    vim.o.conceallevel = 2
  end
end, { silent = true, desc = "" })

keymap("n", "<F11>", function()
  if vim.o.concealcursor == "n" then
    vim.o.concealcursor = ""
  else
    vim.o.concealcursor = "n"
  end
end, { silent = true, desc = "" })

vim.g.tmux_resizer_resize_count = 2
vim.g.tmux_resizer_vertical_resize_count = 2
vim.g.tmux_resizer_no_mappings = 1
keymap("n", "<C-M-k>", "<cmd>:TmuxResizeUp<CR>", { silent = true })
keymap("n", "<C-M-j>", "<cmd>:TmuxResizeDown<CR>", { silent = true })
keymap("n", "<C-M-h>", "<cmd>:TmuxResizeLeft<CR>", { silent = true })
keymap("n", "<C-M-l>", "<cmd>:TmuxResizeRight<CR>", { silent = true })
