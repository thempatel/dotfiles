local cache = {}

local function parse_filetypes(filepath)
  local lines = vim.fn.readfile(filepath)
  local rules = {}
  for _, line in ipairs(lines) do
    line = vim.trim(line)
    if line ~= "" and not line:match("^#") then
      local pattern, ft = line:match("^(.+):%s*(.+)$")
      if pattern and ft then
        table.insert(rules, { pattern = vim.trim(pattern), filetype = vim.trim(ft) })
      end
    end
  end
  return rules
end

local function matches(relative_path, pattern)
  -- Patterns without / match against basename only (like .gitignore)
  -- Patterns with / match against the full relative path
  local target
  if pattern:find("/") then
    target = relative_path
  else
    target = vim.fn.fnamemodify(relative_path, ":t")
  end
  local regex = vim.fn.glob2regpat(pattern)
  return vim.fn.match(target, regex) ~= -1
end

vim.api.nvim_create_autocmd({ "BufReadPost", "BufNewFile" }, {
  group = vim.api.nvim_create_augroup("ProjectFiletypes", { clear = true }),
  callback = function(args)
    local bufpath = vim.api.nvim_buf_get_name(args.buf)
    if bufpath == "" then
      return
    end

    local root = vim.fs.root(args.buf, ".git")
    if not root then
      return
    end

    if cache[root] == nil then
      local ft_file = root .. "/.filetypes"
      if vim.fn.filereadable(ft_file) == 1 then
        cache[root] = parse_filetypes(ft_file)
      else
        cache[root] = false
      end
    end

    if not cache[root] then
      return
    end

    local abs_path = vim.fn.resolve(bufpath)
    local rel_path = abs_path:sub(#root + 2)

    for _, rule in ipairs(cache[root]) do
      if matches(rel_path, rule.pattern) then
        vim.bo[args.buf].filetype = rule.filetype
        return
      end
    end
  end,
})
