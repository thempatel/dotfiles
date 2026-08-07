-- Cap how many buffers stay open, evicting least-recently-used first.
-- `hidden` is on, so buffers otherwise accumulate for the life of the session:
-- a day of jumping around a monorepo leaves hundreds listed, which makes the
-- buffer list unnavigable and keeps a language server pinned to every project
-- ever visited.

local MAX = 24

--- Vim already tracks recency: `getbufinfo()` carries a `lastused` timestamp,
--- so there is no bookkeeping to maintain here.
local function prune()
  local visible = {}
  for _, win in ipairs(vim.api.nvim_list_wins()) do
    visible[vim.api.nvim_win_get_buf(win)] = true
  end

  local listed = vim.fn.getbufinfo({ buflisted = 1 })
  local excess = #listed - MAX
  if excess <= 0 then
    return
  end

  local victims = {}
  for _, buf in ipairs(listed) do
    -- Never evict something on screen or with unsaved changes; `buftype` skips
    -- terminals, quickfix and oil buffers, which are not files to reopen.
    if not visible[buf.bufnr] and not vim.bo[buf.bufnr].modified and vim.bo[buf.bufnr].buftype == "" then
      victims[#victims + 1] = buf
    end
  end

  table.sort(victims, function(a, b)
    return a.lastused < b.lastused
  end)

  for i = 1, math.min(excess, #victims) do
    vim.api.nvim_buf_delete(victims[i].bufnr, {})
  end
end

vim.api.nvim_create_autocmd("BufEnter", {
  group = vim.api.nvim_create_augroup("buffer-cap", { clear = true }),
  callback = prune,
})
