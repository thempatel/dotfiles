local M = {}

-- Servers whose footprint justifies reaping. A tsgo server holds a whole
-- program in memory and has reached 19 GB here; several of them left running
-- across days is enough to wedge the machine on its own.
local NAMES = { "tsgo" }
local IDLE_MS = 45 * 60 * 1000
local CHECK_MS = 10 * 60 * 1000

local last_active = vim.uv.now()
local reaped = false

local function reap()
  for _, name in ipairs(NAMES) do
    for _, client in ipairs(vim.lsp.get_clients({ name = name })) do
      client:stop(true)
      reaped = true
    end
  end
end

--- Stop servers nothing is using any more. Neovim does not stop a client when
--- its last buffer detaches, so once the buffer cap evicts the last file of a
--- project the server would otherwise sit there with a whole program resident.
--- Deliberately not flagged as `reaped`: there are no buffers left to re-attach,
--- and opening a new one starts a fresh client through `FileType` anyway.
local function reap_orphans()
  for _, name in ipairs(NAMES) do
    for _, client in ipairs(vim.lsp.get_clients({ name = name })) do
      -- `initialized` skips the window between spawn and first attach, where a
      -- healthy client legitimately has no buffers yet.
      if client.initialized and next(client.attached_buffers) == nil then
        client:stop(true)
      end
    end
  end
end

--- Re-attach whatever we stopped. `FileType` is the only trigger that starts a
--- client, so replaying it over every buffer is what brings the server back;
--- this is the same call `vim.lsp.enable()` uses to pick up existing buffers.
local function rearm()
  reaped = false
  vim.cmd.doautoall("nvim.lsp.enable FileType")
end

function M.setup()
  vim.api.nvim_create_autocmd({ "FocusGained", "BufEnter", "CursorMoved", "CursorMovedI" }, {
    group = vim.api.nvim_create_augroup("lsp-reaper", { clear = true }),
    callback = function()
      last_active = vim.uv.now()
      if reaped then
        rearm()
      end
    end,
  })

  local timer = assert(vim.uv.new_timer())
  timer:start(
    CHECK_MS,
    CHECK_MS,
    vim.schedule_wrap(function()
      if reaped then
        return
      end
      if vim.uv.now() - last_active >= IDLE_MS then
        reap()
      else
        reap_orphans()
      end
    end)
  )
end

return M
