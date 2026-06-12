return {
  filetypes = { "typescript", "javascript", "javascriptreact", "typescriptreact" },
  root_dir = function(bufnr, on_dir)
    local fname = vim.api.nvim_buf_get_name(bufnr)
    -- Deno projects are owned by denols; don't double-attach here.
    if vim.fs.root(fname, { "deno.json", "deno.jsonc" }) then
      return
    end
    -- Anchor to the project so go-to-definition resolves across files
    -- instead of running single-file and jumping to type stubs.
    on_dir(vim.fs.root(fname, { "tsconfig.json", "jsconfig.json", "package.json", ".git" }) or vim.fs.dirname(fname))
  end,
}
