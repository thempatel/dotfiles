-- Review the current branch in normal buffers: gitsigns diffs every buffer
-- against the commit the branch split off from, so the LSP keeps working.
local M = {}

local enabled = false

-- The commit where HEAD split off the remote default branch, i.e. the base
-- GitHub uses for a PR diff.
local function merge_base()
  for _, ref in ipairs({ "origin/HEAD", "origin/main", "origin/master" }) do
    local out = vim.system({ "git", "merge-base", ref, "HEAD" }, { text = true }):wait()
    if out.code == 0 then
      return vim.trim(out.stdout)
    end
  end
  vim.notify("review: no origin/HEAD, origin/main or origin/master to diff against", vim.log.levels.ERROR)
end

function M.toggle()
  local gs = require("gitsigns")
  local msg = "review: off"
  if enabled then
    gs.reset_base(true)
  else
    local base = merge_base()
    if not base then
      return
    end
    gs.change_base(base, true)
    msg = "review: diffing against " .. base:sub(1, 8)
  end
  enabled = not enabled
  gs.toggle_linehl(enabled)
  gs.toggle_word_diff(enabled)
  gs.toggle_deleted(enabled)
  vim.notify(msg)
end

function M.files()
  local base = merge_base()
  if base then
    require("fzf-lua").git_diff({ ref = base })
  end
end

return M
