require('hs.application')
require('hs.chooser')
require('hs.fnutils')
require('hs.inspect')
require('hs.json')
require('hs.logger')
require('hs.osascript')
require('hs.spoons')
require('hs.task')
require('hs.window')

utils = require('utils')

hs.console.darkMode(true)

local this_script = hs.spoons.scriptPath()
local tabs_script = utils.path_join(utils.path_dir(this_script), 'tabs.js')

local obj = {
  log = hs.logger.new('Chooser', 'debug'),
}
obj.__index = obj

function obj:list_tabs(appName)
  local args = {
    cmd = 'list',
    appName = appName,
  }

  local cmd = tabs_script .. ' ' .. "'" .. hs.json.encode(args) .. "'"
  self.log.d(cmd)
  local output, status, exit_type, rc = hs.execute(cmd)

  if not status then
    self.log.e('list tabs failed')
    self.log.e('output: ' .. output)
    self.log.e('exit_type: ' .. exit_type)
    self.log.e('code: ' .. tostring(rc))
    return {}
  end

  return hs.json.decode(output)
end

function obj:select_tab(info)
  local args = {
    cmd = 'select',
  }
  for k, v in pairs(info) do
    args[k] = v
  end

  local cmd = tabs_script .. ' ' .. "'" .. hs.json.encode(args) .. "'"
  self.log.d(cmd)
  local output, status, exit_type, rc = hs.execute(cmd)

  if not status then
    self.log.e('select tab failed')
    self.log.e('output: ' .. output)
    self.log.e('exit_type: ' .. exit_type)
    self.log.e('code: ' .. tostring(rc))
    return
  end

  local app = hs.application.get(info.appName)
  if app then
    local wins = app:allWindows()
    for _, w in pairs(wins) do
      if w:title():find(info.title, 1, true) then
        w:focus()
        break
      end
    end
  else
    self.log.e("Couldn't find app: " .. info.appName)
  end
end

function obj:choices()
  self.log.i('fetching choices')
  local all_tabs = self:list_tabs('Google Chrome')
  local choices = {}
  if #all_tabs == 0 then
    self.log.i('Found 0 tabs')
    return choices
  end

  for _, tab in pairs(all_tabs) do
    table.insert(choices, {
      text = tab.title,
      subText = tab.url,
      appName = 'Google Chrome',
      title = tab.title,
      url = tab.url,
    })
  end

  return choices
end

obj.chooser = hs.chooser.new(function(choice)
  if choice then
    obj:select_tab(choice)
  end
  obj.chooser:hide()
end)

obj.chooser:choices(function()
  return obj:choices()
end)

obj.chooser:searchSubText(true)

hs.hotkey.bind({ 'cmd', 'shift' }, 'space', function()
  obj.chooser:query(nil)
  obj.chooser:refreshChoicesCallback(false)
  obj.chooser:show()
end)

return obj
