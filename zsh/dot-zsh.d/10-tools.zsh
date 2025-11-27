export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="robbyrussell"
plugins=(git)
source $ZSH/oh-my-zsh.sh

if which atuin > /dev/null; then
  eval "$(atuin init zsh --disable-up-arrow)"
fi

FZF_GIT="$DOTFILES_HOME/vendor/fzf-git.sh"
if [[ -f $FZF_GIT ]]; then
  source $FZF_GIT
fi

Z_HOOK="$(brew --prefix)/etc/profile.d/z.sh"
if [[ -f $Z_HOOK ]]; then
  source $Z_HOOK
fi
