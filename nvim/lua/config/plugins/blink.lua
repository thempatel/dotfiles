return {
  {
    "saghen/blink.cmp",
    event = { "InsertEnter", "CmdlineEnter" },
    version = "*",
    dependencies = {
      {
        "saghen/blink.compat",
        event = { "InsertEnter", "CmdlineEnter" },
        opts = {},
      },
    },
    opts = function(_, opts)
      opts.appearance = {
        use_nvim_cmp_as_default = false,
        nerd_font_variant = "mono",
      }

      opts.completion = {
        accept = {
          auto_brackets = {
            enabled = true,
          },
        },
        menu = {
          border = "rounded",
          draw = {
            gap = 2,
            columns = {
              { "kind_icon", gap = 1 },
              { "label", "label_description", gap = 1 },
              { "source_name", gap = 1 },
            },
            components = {
              source_name = {
                text = function(ctx)
                  return "[" .. ctx.source_name .. "]"
                end,
              },
            },
          },
          winhighlight = "Normal:Normal,FloatBorder:FloatBorder,CursorLine:BlinkCmpMenuSelection,Search:None",
        },
        documentation = {
          window = {
            border = "rounded",
            winblend = 0,
          },
          auto_show = true,
          auto_show_delay_ms = 200,
        },
        ghost_text = {
          enabled = vim.g.ai_cmp,
        },
      }

      opts.sources = vim.tbl_deep_extend("force", opts.sources or {}, {
        default = { "lsp", "path", "buffer" },
        providers = {
          lsp = {
            name = "lsp",
            enabled = true,
            module = "blink.cmp.sources.lsp",
            score_offset = 90,
          },
          path = {
            name = "Path",
            module = "blink.cmp.sources.path",
            score_offset = 3,
            fallbacks = { "buffer" },
            opts = {
              trailing_slash = false,
              label_trailing_slash = true,
              get_cwd = function(context)
                return vim.fn.expand(("#%d:p:h"):format(context.bufnr))
              end,
              show_hidden_files_by_default = true,
            },
          },
          buffer = {
            name = "Buffer",
            enabled = true,
            max_items = 3,
            module = "blink.cmp.sources.buffer",
            min_keyword_length = 4,
          },
          lazydev = {
            name = "LazyDev",
            module = "lazydev.integrations.blink",
            score_offset = 100,
          },
        },
      })

      opts.keymap = {
        preset = "default",
        ["<C-y>"] = { "select_and_accept" },

        ["<Up>"] = { "select_prev", "fallback" },
        ["<Down>"] = { "select_next", "fallback" },
        ["<C-p>"] = { "select_prev", "fallback" },
        ["<C-n>"] = { "select_next", "show", "fallback" },

        ["<C-b>"] = { "scroll_documentation_up", "fallback" },
        ["<C-f>"] = { "scroll_documentation_down", "fallback" },

        ["<C-space>"] = { "show", "show_documentation", "hide_documentation" },
        ["<C-e>"] = { "hide", "fallback" },
        ["<Tab>"] = {},
        ["<S-Tab>"] = {},
      }

      return opts
    end,
  },
}
