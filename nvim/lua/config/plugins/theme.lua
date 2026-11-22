return {
  "projekt0n/github-nvim-theme",
  priority = 1000,
  lazy = false,
  config = function()
    require("github-theme").setup({
      options = {
        transparent = false,
        terminal_colors = true,
        styles = {
          comments = "italic",
          keywords = "italic",
        },
      },
    })
    vim.cmd.colorscheme("github_dark_high_contrast")

    -- Diff colors as github.com draws them: a faint background on changed
    -- lines and a stronger one on changed words, with no foreground so syntax
    -- colors stay. Hex values are GitHub's green (#2ea043) and red (#f85149)
    -- at 15% and 40% opacity over this theme's background (#0a0c10).
    local add_line, add_word = "#0f2218", "#184724"
    local del_line, del_word = "#2e1619", "#692827"
    for group, bg in pairs({
      DiffAdd = add_line,
      DiffChange = add_line,
      DiffText = add_word,
      DiffDelete = del_line,
      GitSignsAddLn = add_line,
      GitSignsChangeLn = add_line,
      GitSignsAddInline = add_word,
      GitSignsChangeInline = add_word,
      GitSignsDeleteInline = del_word,
      GitSignsDeleteVirtLn = del_line,
      GitSignsDeleteVirtLnInline = del_word,
    }) do
      vim.api.nvim_set_hl(0, group, { bg = bg })
    end
  end,
}
