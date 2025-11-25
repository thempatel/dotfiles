# Config Load order

source: https://superuser.com/questions/1840395/complete-overview-of-bash-and-zsh-startup-files-sourcing-order

* etcEnv = "/etc/zsh/zshenv"
* etcProfile = "/etc/zsh/zprofile"
* etcRc = "/etc/zsh/zshrc"
* etcLogin = "/etc/zsh/zlogin"
* etcLogout = "/etc/zsh/zlogout"
* homeEnv = "~/.zshenv"
* homeProfile = "~/.zprofile"
* homeRc = "~/.zshrc"
* homeLogin = "~/.zlogin"
* homeLogout = "~/.zlogout"
* systemEtcProfile = "/etc/profile"

### login, interactive
```
interactive
  --> etcEnv --> homeEnv
  --> etcProfile --> systemEtcProfile --> homeProfile
  --> etcRc --> homeRc
  --> etcLogin --> homeLogin
  -->|on logout| homeLogout --> etcLogout
```

### login, non-interactive
```
nonInteractive
  --> etcEnv --> homeEnv
  --> etcProfile --> systemEtcProfile --> homeProfile
  --> etcLogin --> homeLogin
  -->|on logout| homeLogout --> etcLogout
```

### non-login, interactive
```
interactive --> etcEnv --> homeEnv
  --> etcRc --> homeRc
```

### non-login, non-interactive
```
nonInteractive --> etcEnv --> homeEnv
```
