local conditions = require("config.plugins.lualine.conditions")

local function diff_source()
  local gitsigns = vim.b.gitsigns_status_dict
  if gitsigns then
    return {
      added = gitsigns.added,
      modified = gitsigns.changed,
      removed = gitsigns.removed,
    }
  end
end

-- Use Comment highlight as a muted foreground color, works across themes.
local muted = { fg = "Comment", bg = "NONE" }

return {
  mode = {
    function()
      return " "
    end,
    padding = { left = 0, right = 0 },
    color = {},
    cond = nil,
  },
  branch = {
    "b:gitsigns_head",
    icon = "",
    color = muted,
    cond = conditions.hide_in_width,
  },
  diff = {
    "diff",
    source = diff_source,
    symbols = { added = "+", modified = "~", removed = "-" },
    color = muted,
    colored = false,
    cond = nil,
  },
  diagnostics = {
    "diagnostics",
    sources = { "nvim_diagnostic" },
    symbols = { error = " ", warn = " ", info = " ", hint = "󰌶 " },
    color = muted,
    cond = nil,
  },
  treesitter = {
    function()
      local b = vim.api.nvim_get_current_buf()
      if next(vim.treesitter.highlighter.active[b]) then
        return "  "
      end
      return ""
    end,
    color = muted,
    cond = conditions.hide_in_width,
  },
  lsp = {
    function(msg)
      msg = msg or "LS Inactive"
      local bufnr = vim.api.nvim_get_current_buf()
      local buf_clients = vim.lsp.get_clients({ bufnr = bufnr })
      if next(buf_clients) == nil then
        if type(msg) == "boolean" or #msg == 0 then
          return "LS Inactive"
        end
        return msg
      end
      local buf_client_names = {}

      for _, client in pairs(buf_clients) do
        if client.name ~= "null-ls" then
          table.insert(buf_client_names, client.name)
        end
      end

      local unique_client_names = vim.fn.sort(buf_client_names)
      unique_client_names = vim.fn.uniq(unique_client_names)
      return table.concat(unique_client_names, "  ")
    end,
    color = muted,
  },
  location = {
    "location",
    cond = conditions.hide_in_width,
    color = muted,
  },
  progress = {
    "progress",
    cond = conditions.hide_in_width,
    color = muted,
  },
  spaces = {
    function()
      local label = "Spaces: "
      if not vim.api.nvim_buf_get_option(0, "expandtab") then
        label = "Tab size: "
      end
      return label .. vim.api.nvim_buf_get_option(0, "shiftwidth") .. " "
    end,
    cond = conditions.hide_in_width,
    color = muted,
  },
  encoding = {
    "o:encoding",
    fmt = string.upper,
    color = muted,
    cond = conditions.hide_in_width,
  },
  filetype = {
    "filetype",
    cond = conditions.hide_in_width,
    color = muted,
  },
  scrollbar = {
    function()
      local current_line = vim.fn.line(".")
      local total_lines = vim.fn.line("$")
      local chars = { "_", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█" }
      local line_ratio = current_line / total_lines
      local index = math.ceil(line_ratio * #chars)
      return chars[index]
    end,
    padding = { left = 0, right = 0 },
    color = muted,
    cond = nil,
  },
}
