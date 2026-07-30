# PyFlare OS default .bashrc
[ -z "$PS1" ] && return

# Prompt
PS1='\[\033[01;36m\]\u@pyflare\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '

# Aliases
alias ls='ls --color=auto'
alias ll='ls -alF'
alias la='ls -A'
alias grep='grep --color=auto'
alias df='df -h'
alias du='du -h'
alias ..='cd ..'
alias ...='cd ../..'

# PyFlare
export PYFLARE_HOME="/opt/pyflare"
export PATH="/opt/pyflare/bin:$PATH"
