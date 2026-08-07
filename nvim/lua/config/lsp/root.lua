local M = {}

local VCS = { ".git", ".hg", ".svn", ".jj" }

local function has_marker(dir, markers)
  for _, m in ipairs(markers) do
    if vim.uv.fs_stat(dir .. "/" .. m) then
      return true
    end
  end
  return false
end

--- Outermost directory containing one of `markers`, bounded by the enclosing
--- VCS root. A language server costs a whole program's worth of memory, so we
--- want one per checkout, not one per package. Falls back to the nearest match
--- when the file is not in a checkout (nothing to bound the walk) or when the
--- nearest marker already sits outside it.
function M.widest(fname, markers)
  local nearest = vim.fs.root(fname, markers)
  if not nearest then
    return nil
  end

  local repo = vim.fs.root(fname, VCS)
  -- relpath is nil for a sibling, so this also rejects a marker that resolved
  -- above the checkout (a stray package.json in $HOME, say).
  if not repo or not vim.fs.relpath(repo, nearest) then
    return nearest
  end

  local widest, dir = nearest, nearest
  while dir ~= repo do
    local parent = vim.fs.dirname(dir)
    if parent == dir then
      break -- filesystem root without meeting repo
    end
    dir = parent
    if has_marker(dir, markers) then
      widest = dir
    end
  end
  return widest
end

--- Prefer a root an already-running `name` client is rooted at. Neovim's
--- default reuse check compares workspace-folder URIs literally, so handing
--- back that client's exact root is what makes it reuse rather than spawn.
--- Only sees clients in this Neovim instance.
function M.shared(name, fname, markers)
  for _, client in ipairs(vim.lsp.get_clients({ name = name })) do
    local root = client.config.root_dir
    if root and vim.fs.relpath(root, fname) then
      return root
    end
  end
  return M.widest(fname, markers)
end

return M
