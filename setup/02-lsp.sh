#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
LSP_DIR="$ROOT_DIR/lsp"
BIN_DIR="$LSP_DIR/bin"

mkdir -p "$BIN_DIR"

echo "==> Installing npm LSP servers"
npm install --prefix "$LSP_DIR"

# Symlink only the LSP server binaries (relative paths)
ln -sf ../node_modules/.bin/kulala-ls "$BIN_DIR/kulala-ls"
ln -sf ../node_modules/.bin/bash-language-server "$BIN_DIR/bash-language-server"
ln -sf ../node_modules/.bin/yaml-language-server "$BIN_DIR/yaml-language-server"
ln -sf ../node_modules/.bin/tsgo "$BIN_DIR/tsgo"
ln -sf ../node_modules/.bin/tsserver "$BIN_DIR/tsserver"
ln -sf ../node_modules/.bin/vscode-json-language-server "$BIN_DIR/vscode-json-language-server"
ln -sf ../node_modules/.bin/vscode-html-language-server "$BIN_DIR/vscode-html-language-server"

echo "==> Installing gopls"
GOBIN="$BIN_DIR" go install golang.org/x/tools/gopls@latest

echo ""
echo "==> Done. Installed to $BIN_DIR:"
ls "$BIN_DIR"
