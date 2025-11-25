require('hs.osascript')

local M = {}

function M.path_join(a, b)
  return a .. '/' .. b
end

function M.path_dir(path)
  return path:match('(.*)/')
end

function M.read_all(file)
  local f = assert(io.open(file, 'r'))
  local content = f:read('*all')
  f:close()
  return content
end

function M.template(str, args)
  return str:gsub('%%(%w+)%%', args)
end

function M.exec_js(tmpl, args)
  local script = M.template(tmpl, args)
  local status, body, raw_str = hs.osascript.javascript(script)
  if status and type(body) == 'string' then
    return status, hs.json.decode(body), raw_str
  end

  return status, body, raw_str
end

return M
