local root = require("config.lsp.root")
local MARKERS = { "tsconfig.json", "jsconfig.json", "package.json" }

return {
  -- TypeScript 7's native LSP is the `tsc` binary (`setup/02-lsp.sh` puts it on
  -- PATH). Pin to it rather than lspconfig's default project-local lookup: a
  -- project's own `tsc` may be classic TS <7, which doesn't support `--lsp`.
  cmd = { "tsc", "--lsp", "--stdio" },
  -- The TS7 server is a Go binary. Unbounded, its heap has reached 19 GB here
  -- and taken the machine down. Soft limit: the GC works harder instead of the
  -- process ballooning.
  cmd_env = { GOMEMLIMIT = "6GiB" },
  filetypes = { "typescript", "javascript", "javascriptreact", "typescriptreact" },
  root_dir = function(bufnr, on_dir)
    local fname = vim.api.nvim_buf_get_name(bufnr)
    -- Deno projects are owned by denols; don't double-attach here.
    if vim.fs.root(fname, { "deno.json", "deno.jsonc" }) then
      return
    end
    -- Anchor to the outermost project in the checkout so one server covers all
    -- of a monorepo's packages instead of one per package.
    on_dir(root.shared("tsgo", fname, MARKERS) or vim.fs.dirname(fname))
  end,
}
