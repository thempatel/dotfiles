local annotations = {}

local function add_annotation()
  local file = vim.fn.expand("%:.")
  local line = vim.fn.line(".")
  local line_text = vim.api.nvim_get_current_line():gsub("^%s+", "")

  vim.ui.input({ prompt = "Comment: " }, function(comment)
    if not comment or comment == "" then
      return
    end
    table.insert(annotations, {
      file = file,
      line = line,
      text = line_text,
      comment = comment,
    })
    vim.notify(string.format("Annotation added (%d total)", #annotations))
  end)
end

local function add_annotation_visual()
  local file = vim.fn.expand("%:.")
  local start_line = vim.fn.line("'<")
  local end_line = vim.fn.line("'>")
  local lines = vim.api.nvim_buf_get_lines(0, start_line - 1, end_line, false)
  local text = table.concat(lines, "\n")

  vim.ui.input({ prompt = "Comment: " }, function(comment)
    if not comment or comment == "" then
      return
    end
    table.insert(annotations, {
      file = file,
      line = start_line,
      end_line = end_line ~= start_line and end_line or nil,
      text = text,
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
    table.insert(parts, string.format("// %s\n%s\n%s", ref, a.comment, a.text))
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
  vim.notify("Annotations cleared")
end

vim.keymap.set("n", "<leader>ca", add_annotation, { desc = "Annotate line" })
vim.keymap.set("v", "<leader>ca", add_annotation_visual, { desc = "Annotate selection" })
vim.keymap.set("n", "<leader>cA", show_annotations, { desc = "Show annotations" })
vim.keymap.set("n", "<leader>cy", copy_annotations, { desc = "Copy annotations" })
vim.keymap.set("n", "<leader>cX", clear_annotations, { desc = "Clear annotations" })

return {}
