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

-- Shows a file deleted since {base} in a read-only scratch buffer holding its
-- content at {base}.
local function open_deleted(base, root, relpath)
  local name = ("review://%s/%s"):format(base:sub(1, 8), relpath)
  local buf = vim.fn.bufnr(name)
  if buf == -1 then
    local out = vim.system({ "git", "show", base .. ":" .. relpath }, { cwd = root, text = true }):wait()
    if out.code ~= 0 then
      vim.notify("review: " .. vim.trim(out.stderr), vim.log.levels.ERROR)
      return
    end
    local lines = vim.split(out.stdout, "\n", { plain = true })
    if lines[#lines] == "" then
      table.remove(lines)
    end
    buf = vim.api.nvim_create_buf(true, true)
    vim.api.nvim_buf_set_name(buf, name)
    vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)
    vim.bo[buf].modifiable = false
    vim.bo[buf].filetype = vim.filetype.match({ filename = relpath, buf = buf }) or ""
  end
  vim.api.nvim_set_current_buf(buf)
end

function M.files()
  local base = merge_base()
  if base then
    local fzf = require("fzf-lua")
    fzf.git_diff({
      ref = base,
      actions = {
        ["enter"] = function(selected, opts)
          local existing = {}
          for _, entry in ipairs(selected) do
            local abs = vim.fs.abspath(fzf.path.entry_to_file(entry, opts).path)
            if vim.uv.fs_stat(abs) then
              table.insert(existing, entry)
            else
              open_deleted(base, opts.cwd, assert(vim.fs.relpath(opts.cwd, abs)))
            end
          end
          if #existing > 0 then
            fzf.actions.file_edit_or_qf(existing, opts)
          end
        end,
      },
      -- The preview reads the path from the entry's last field, which
      -- `path.filename_first` splits into "name<tab>dir".
      formatter = false,
      -- `--` lets git diff files deleted from the working tree.
      preview = "git diff {ref} -- {file}",
    })
  end
end

return M
