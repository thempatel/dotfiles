return {
  filetypes = { "rust" },
  root_markers = { "Cargo.toml", "rust-project.json" },
  settings = {
    ["rust-analyzer"] = {
      checkOnSave = {
        command = "clippy",
      },
    },
  },
}
