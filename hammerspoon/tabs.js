#!/usr/bin/env osascript -l JavaScript
const webkit = ["Safari", "Webkit", "Orion"];
const chromium = ["Google Chrome", "Chromium"];
const validApps = new Set([...webkit, ...chromium]);

function _throw(msg) {
  let line;
  try {
    throw new Error();
  } catch (e) {
    const lineNo = e.line;
    if (lineNo !== undefined) {
      line = lineNo;
    }
  }

  throw new Error(`tabs.js:${line} - ${msg}`);
}

function isWebKit(appName) {
  return webkit.includes(appName);
}

function forEachTab(app, cb) {
  const appIsWebKit = isWebKit(app.name());
  const tabTitles = appIsWebKit
    ? app.windows.tabs.name()
    : app.windows.tabs.title();
  const tabUrls = app.windows.tabs.url();

  for (let winIdx = 0; winIdx < app.windows.length; winIdx++) {
    const tabNum = tabUrls[winIdx].length;

    for (let tabIdx = 0; tabIdx < tabNum; tabIdx++) {
      const url = tabUrls[winIdx][tabIdx] || "";
      const title = tabTitles[winIdx][tabIdx] || "unknown";
      if (cb({ url, title, winIdx, tabIdx })) {
        return;
      }
    }
  }
}

function list(app) {
  const tabs = new Map();
  const appName = app.name();
  forEachTab(app, ({ url, title }) => {
    tabs.set(url, {
      title,
      url,
      appName,
    });
  });
  return JSON.stringify(Array.from(tabs.values()));
}

function selectWebKit(app, rest) {
  const { url } = rest;
  forEachTab(app, ({ url: tabUrl, winIdx, tabIdx }) => {
    if (tabUrl.includes(url)) {
      const window = app.windows[winIdx];
      window.currentTab = window.tabs[tabIdx];
      return true;
    }
  });
}

function selectChromium(app, rest) {
  const { url } = rest;

  forEachTab(app, ({ url: tabUrl, tabIdx, winIdx }) => {
    if (tabUrl.includes(url)) {
      const window = app.windows[winIdx];
      window.activeTabIndex = tabIdx + 1;
      return true;
    }
  });
}

function run(args) {
  const { cmd, appName, ...rest } = JSON.parse(args[0]);

  const app = Application(appName);
  if (!app.running()) {
    _throw(`app ${appName} not running`);
  }
  app.includeStandardAdditions = true;
  switch (cmd) {
    case "list":
      return list(app);
    case "select": {
      if (isWebKit(appName)) {
        return selectWebKit(app, rest);
      } else {
        return selectChromium(app, rest);
      }
    }
    default:
      _throw(`unknown command: ${cmd}`);
  }
}
