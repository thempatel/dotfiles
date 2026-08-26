local root = require("config.lsp.root")
local MARKERS = { "tsconfig.json", "jsconfig.json", "package.json" }

-- The TS7 server is a Go binary. Unbounded, its heap has reached 19 GB here
-- and taken the machine down. Soft limit: the GC works harder instead of the
-- process ballooning. Survives the node wrapper that `@typescript/native-preview`
-- shims through, so it applies to a project-local `tsgo` too.
local ENV = { GOMEMLIMIT = "6GiB" }

--- Binary to serve `dir` with, most project-specific first. A checkout's own
--- compiler is what its build and CI use, so its diagnostics are the ones worth
--- trusting; the pinned one only covers checkouts that ship neither.
--- Every candidate is an absolute path: a bare `tsc` is resolved through PATH at
--- spawn time, and a project whose direnv prepends `node_modules/.bin` (or any
--- other PATH mangling) then hands over classic TypeScript, which has no `--lsp`
--- and exits 1.
local function resolve(dir)
  local candidates = {}
  if dir then
    -- `@typescript/native-preview` installs the native compiler as `tsgo` and
    -- never as `tsc`; a sibling `node_modules/.bin/tsc` in the same project can
    -- still be classic TS. Look for this one first.
    table.insert(candidates, dir .. "/node_modules/.bin/tsgo")
    table.insert(candidates, dir .. "/node_modules/.bin/tsc")
  end
  table.insert(candidates, vim.g.projects_dir .. "/dotfiles/lsp/bin/tsc") -- setup/02-lsp.sh

  for _, path in ipairs(candidates) do
    if vim.fn.executable(path) == 1 then
      return path
    end
  end
end

-- Named `ts7`, not `tsgo`: Neovim merges every `lsp/<name>.lua` on the
-- runtimepath and later entries win, so an lspconfig-shipped `lsp/tsgo.lua`
-- would clobber everything below it -- including `cmd`. A name lspconfig does
-- not ship leaves this file alone.
return {
  -- A function rather than a command list because the binary varies per project.
  -- Note that `cmd_env`/`cmd_cwd` are only honoured for the list form, so the
  -- memory limit has to be handed to `rpc.start` here or it silently stops
  -- applying.
  cmd = function(dispatchers, config)
    local path = resolve((config or {}).root_dir)
    -- `config` is the table the client keeps, so this is readable afterwards as
    -- `client.config.cmd_resolved` -- worth having, since which binary won
    -- decides which diagnostics you get.
    if config then
      config.cmd_resolved = path
    end
    return vim.lsp.rpc.start({ path, "--lsp", "--stdio" }, dispatchers, { env = ENV })
  end,
  filetypes = { "typescript", "javascript", "javascriptreact", "typescriptreact" },
  root_dir = function(bufnr, on_dir)
    local fname = vim.api.nvim_buf_get_name(bufnr)
    -- Deno projects are owned by denols; don't double-attach here.
    if vim.fs.root(fname, { "deno.json", "deno.jsonc" }) then
      return
    end
    -- Anchor to the outermost project in the checkout so one server covers all
    -- of a monorepo's packages instead of one per package.
    on_dir(root.shared("ts7", fname, MARKERS) or vim.fs.dirname(fname))
  end,
}
