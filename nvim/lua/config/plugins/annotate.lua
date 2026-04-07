local annotations = {}

local state_dir = vim.fn.stdpath("state") .. "/annotations"

local function session_key()
  local name = vim.fn.getcwd():gsub("[\\/:]+", "%%")
  if vim.fs.root(0, ".git") then
    local branch = vim.fn.systemlist("git branch --show-current")[1]
    if vim.v.shell_error == 0 and branch and branch ~= "main" and branch ~= "master" then
      name = name .. "%%" .. branch:gsub("[\\/:]+", "%%")
    end
  end
  return state_dir .. "/" .. name .. ".json"
end

local function save_annotations()
  if #annotations == 0 then
    local path = session_key()
    if vim.fn.filereadable(path) == 1 then
      vim.fn.delete(path)
    end
    return
  end
  vim.fn.mkdir(state_dir, "p")
  vim.fn.writefile({ vim.fn.json_encode(annotations) }, session_key())
end

local function load_annotations()
  local path = session_key()
  if vim.fn.filereadable(path) == 0 then
    return
  end
  local content = vim.fn.readfile(path)
  if #content > 0 then
    local ok, data = pcall(vim.fn.json_decode, content[1])
    if ok and type(data) == "table" then
      annotations = data
    end
  end
end

local function open_annotation_buf(header, callback)
  local buf = vim.api.nvim_create_buf(false, true)
  vim.bo[buf].buftype = "acwrite"
  vim.bo[buf].filetype = "markdown"
  vim.api.nvim_buf_set_name(buf, "annotation://" .. header)
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, { "// " .. header, "" })

  local win = vim.api.nvim_open_win(buf, true, {
    relative = "editor",
    width = math.floor(vim.o.columns * 0.6),
    height = math.floor(vim.o.lines * 0.4),
    col = math.floor(vim.o.columns * 0.2),
    row = math.floor(vim.o.lines * 0.2),
    style = "minimal",
    border = "rounded",
    title = " Annotate ",
    title_pos = "center",
  })

  vim.api.nvim_win_set_cursor(win, { 2, 0 })
  vim.cmd("startinsert")

  local group = vim.api.nvim_create_augroup("annotate_buf_" .. buf, { clear = true })

  vim.api.nvim_create_autocmd("BufWriteCmd", {
    group = group,
    buffer = buf,
    callback = function()
      local lines = vim.api.nvim_buf_get_lines(buf, 1, -1, false)
      -- trim trailing empty lines
      while #lines > 0 and lines[#lines] == "" do
        table.remove(lines)
      end
      if #lines > 0 then
        callback(table.concat(lines, "\n"))
      end
      vim.bo[buf].modified = false
      vim.api.nvim_win_close(win, true)
      vim.api.nvim_buf_delete(buf, { force = true })
    end,
  })

  vim.api.nvim_create_autocmd("WinClosed", {
    group = group,
    buffer = buf,
    callback = function()
      vim.api.nvim_del_augroup_by_id(group)
      if vim.api.nvim_buf_is_valid(buf) then
        vim.api.nvim_buf_delete(buf, { force = true })
      end
    end,
  })
end

local function add_annotation()
  local file = vim.fn.expand("%:.")
  local line = vim.fn.line(".")
  local header = file .. ":" .. line

  open_annotation_buf(header, function(comment)
    table.insert(annotations, { file = file, line = line, comment = comment })
    vim.notify(string.format("Annotation added (%d total)", #annotations))
  end)
end

local function add_annotation_visual()
  vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<Esc>", true, false, true), "x", false)
  local file = vim.fn.expand("%:.")
  local start_line = vim.fn.line("'<")
  local end_line = vim.fn.line("'>")
  local header = start_line == end_line
    and file .. ":" .. start_line
    or file .. ":" .. start_line .. "-" .. end_line

  open_annotation_buf(header, function(comment)
    table.insert(annotations, {
      file = file,
      line = start_line,
      end_line = end_line ~= start_line and end_line or nil,
      comment = comment,
    })
    vim.notify(string.format("Annotation added (%d total)", #annotations))
  end)
end

local function format_annotations()
  if #annotations == 0 then
    return "No annotations."
  end

  local parts = {}
  for _, a in ipairs(annotations) do
    local ref = a.end_line and string.format("%s:%d-%d", a.file, a.line, a.end_line)
      or string.format("%s:%d", a.file, a.line)
    table.insert(parts, string.format("// %s\n%s", ref, a.comment))
  end
  return table.concat(parts, "\n\n")
end

local function show_annotations()
  if #annotations == 0 then
    vim.notify("No annotations.")
    return
  end

  local items = {}
  for _, a in ipairs(annotations) do
    table.insert(items, {
      filename = a.file,
      lnum = a.line,
      text = a.comment,
    })
  end
  vim.fn.setqflist(items, "r")
  vim.cmd("copen")
end

local function copy_annotations()
  local content = format_annotations()
  vim.fn.setreg("+", content)
  vim.notify(string.format("Copied %d annotations to clipboard", #annotations))
end

local function clear_annotations()
  annotations = {}
  save_annotations()
  vim.notify("Annotations cleared")
end

vim.keymap.set("n", "<leader>ca", add_annotation, { desc = "Annotate line" })
vim.keymap.set("x", "<leader>ca", add_annotation_visual, { desc = "Annotate selection" })
vim.keymap.set("n", "<leader>cl", show_annotations, { desc = "Show annotations" })
vim.keymap.set("n", "<leader>cy", copy_annotations, { desc = "Copy annotations" })
vim.keymap.set("n", "<leader>cd", clear_annotations, { desc = "Clear annotations" })

local group = vim.api.nvim_create_augroup("annotate_persistence", { clear = true })
vim.api.nvim_create_autocmd("User", {
  group = group,
  pattern = "PersistenceSavePre",
  callback = save_annotations,
})
vim.api.nvim_create_autocmd("User", {
  group = group,
  pattern = "PersistenceLoadPost",
  callback = load_annotations,
})

load_annotations()

return {}
