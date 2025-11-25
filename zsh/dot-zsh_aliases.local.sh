# dotfiles
alias reload!="exec $SHELL"
alias speedtest="networkQuality -v -s"

# git
alias d="git commit -m ."
alias p="git push"
alias a="git add -u"
alias ad="a && d"
alias dp="d && p"
alias adp="a && d && p"
alias gpfl="git push --force-with-lease --force-if-includes"
alias firstcommit="git commit -m 'init'  && gpsup"
alias s='git status'
alias lg='lazygit'

# proxyman
alias pm='proxyman-cli proxy'
