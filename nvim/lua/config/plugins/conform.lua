local SQL_DIALECTS = {
  "ansi", "bigquery", "clickhouse", "databricks", "db2", "duckdb",
  "exasol", "greenplum", "hive", "materialize", "mysql", "oracle",
  "postgres", "redshift", "snowflake", "soql", "sparksql", "sqlite",
  "starrocks", "teradata", "trino", "tsql", "vertica",
}

return {
  "stevearc/conform.nvim",
  opts = {
    formatters_by_ft = {
      sql = { "sqlfluff" },
    },
  },
  cmd = { "Format" },
  keys = {
    {
      "<leader>cf",
      function() require("conform").format({ async = true }) end,
      mode = { "n", "x" },
      desc = "Format Buffer",
    },
  },
  config = function(_, opts)
    require("conform").setup(opts)
    vim.api.nvim_create_user_command("Format", function(args)
      local dialect = args.fargs[1]
      if not dialect then
        require("conform").format({ async = true })
        return
      end
      if vim.bo.filetype ~= "sql" then
        vim.notify(
          ("Format: dialect arg (%q) only valid for sql buffers, got %s"):format(dialect, vim.bo.filetype),
          vim.log.levels.ERROR
        )
        return
      end
      if not vim.tbl_contains(SQL_DIALECTS, dialect) then
        vim.notify(("Format: unknown sqlfluff dialect %q"):format(dialect), vim.log.levels.ERROR)
        return
      end
      vim.cmd(("%%!sqlfluff fix --dialect %s - 2>/dev/null"):format(vim.fn.shellescape(dialect)))
    end, {
      nargs = "?",
      complete = function()
        return vim.bo.filetype == "sql" and SQL_DIALECTS or {}
      end,
      desc = "Format buffer (optional sqlfluff dialect for sql)",
    })
  end,
}
