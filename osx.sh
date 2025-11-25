#!/usr/bin/env bash

sudo -v

# Screenshots
SCREENSHOT_LOC=$HOME/Documents/screenshots
mkdir -p $SCREENSHOT_LOC
defaults write com.apple.screencapture location $SCREENSHOT_LOC
# Remove screenshot from screenshot filename
defaults write com.apple.screencapture name ""
# Disable shadows in full window screenshots
defaults write com.apple.screencapture disable-shadow -bool true

# Finder
# Show special folders
sudo chflags nohidden ~/Library
sudo chflags nohidden /Volumes

# Global
# Disable auto-correct
defaults write NSGlobalDomain NSAutomaticSpellingCorrectionEnabled -bool false

# Dock
FOLDER_OPTS="--view=auto --display=stack --sort=datemodified"
dockutil \
  --no-restart \
  --add $SCREENSHOT_LOC \
  --replacing=Screenshots \
  --label=Screenshots \
  --after=Downloads \
  $FOLDER_OPTS

# Restart
killall SystemUIServer
killall Dock
