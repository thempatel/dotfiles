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
  end,
}
