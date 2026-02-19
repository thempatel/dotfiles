export LS_OPTIONS='--color=auto'
eval "$(dircolors -b)"
alias ls='ls $LS_OPTIONS'
alias ll='ls $LS_OPTIONS -l'
alias l='ls $LS_OPTIONS -lA'
alias ..='cd ..'


if [[ -f $HOME/.bash_env ]]; then
  source $HOME/.bash_env
fi

export PATH="/opt/sbox-scripts:$HOME/.local/bin:${PATH}"
export PATH="$HOME/.deno/bin:${PATH}"
export CLAUDE_CONFIG_DIR="$HOME/.claude"

sbox-bootstrap() {
  if [[ -f .nvmrc ]]; then
    echo "Found .nvmrc, installing node..."
    nvm install
  fi

  if [[ -f pnpm-lock.yaml ]]; then
    echo "Found pnpm-lock.yaml, installing pnpm..."
    npm install -g pnpm@latest-10
  fi

  if [[ -f .python-version ]]; then
    echo "Found .python-version, installing python..."
    uv python install
  fi

  if ! uv python find >/dev/null 2>&1; then
    echo "No global python found, installing default..."
    uv python install --default --preview
  fi
}
