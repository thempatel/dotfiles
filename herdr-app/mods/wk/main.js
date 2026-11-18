// Start an agent in a worktree with `wk --app`: wk reuses a free worktree of the
// project (one whose space has only a fresh agent, then one with no space) or
// makes a new one, and opens it with `hd --app`. The projects are the folders in
// $CODE_ROOT; type to filter them or type a repo's path. ↑/↓ picks, Tab moves to
// the agent's message, Enter opens, Esc leaves.

import { View, div } from "gpui-kit";
import { v_flex, h_flex, InputState, Input } from "gpui-base";
import { exec, home, notify, theme, props, closeOverlay } from "herdr";

const ROWS = 12;

// The folders wk's own picker lists, minus wk's worktrees folder.
const PROJECTS = `cd "\${CODE_ROOT:-$HOME/src}" && for d in */; do [ "$d" = worktrees/ ] || echo "$PWD/\${d%/}"; done`;

function tilde(path) {
  const h = home();
  return path === h ? "~" : path.startsWith(h + "/") ? "~" + path.slice(h.length) : path;
}

function untilde(path) {
  return path === "~" || path.startsWith("~/") ? home() + path.slice(1) : path;
}

export default class Wk extends View {
  init(_props, cx) {
    this.dirs = [];
    this.filter = "";
    this.at = 0;
    this.top = 0;
    this.busy = false;
    this.error = "";
    this.inPrompt = false;
    this.folder = InputState.new({ placeholder: "Project…" });
    this.folder.on("change", (_e, cx) => {
      this.filter = this.folder.value();
      this.at = 0;
      cx.notify();
    });
    this.folder.on("submit", (_e, cx) => this.open(cx));
    this.prompt = InputState.new({ placeholder: "First message for the agent (optional)" });
    this.prompt.on("submit", (_e, cx) => this.open(cx));
    this.prompt.on("focus", (_e, cx) => { this.inPrompt = true; cx.notify(); });
    this.prompt.on("blur", (_e, cx) => { this.inPrompt = false; cx.notify(); });
    this.folder.focus();
    // The popup can take the keyboard after init; focus again once it has.
    cx.timer.after(600, () => (this.inPrompt ? this.prompt : this.folder).focus());
    this.handle = cx.focus_handle();
    cx.spawn(async (cx) => {
      try {
        const r = await exec("sh", ["-c", PROJECTS]);
        if (r.code === 0) this.dirs = r.stdout.split("\n").filter(Boolean);
        else this.error = r.stderr.trim() || "could not list projects";
      } catch (e) {
        this.error = String(e);
      }
      cx.notify();
    });
  }

  close() {
    closeOverlay(props().overlay);
  }

  rows() {
    const typed = this.filter.trim();
    const words = typed.toLowerCase().split(/\s+/).filter(Boolean);
    const found = this.dirs.filter((d) => {
      const shown = tilde(d).toLowerCase();
      return words.every((w) => shown.includes(w));
    });
    const path = untilde(typed).replace(/(.)\/+$/, "$1");
    if (/^[~/]/.test(typed) && !found.includes(path)) found.unshift(path);
    return found;
  }

  open(cx) {
    const dir = this.rows()[this.at];
    if (!dir || this.busy) return;
    const message = this.prompt.value().trim();
    const args = ["--app", dir, "--prompt", message];
    this.busy = true;
    this.error = "";
    cx.notify();
    cx.spawn(async (cx) => {
      try {
        // wk fetches the default branch first, so allow for a slow network.
        const r = await exec("wk", args, { timeout: 180_000 });
        if (r.code === 0) {
          // hd still exits 0 when it couldn't hand the message to the agent. The
          // rest of stderr is git's progress output.
          const warning = r.stderr.split("\n").filter((l) => l.startsWith("hd:")).join("\n");
          if (warning) notify({ title: "wk", body: warning, level: "warning" });
          return this.close();
        }
        this.error = r.stderr.trim() || r.stdout.trim() || `wk exited with ${r.code}`;
      } catch (e) {
        this.error = String(e);
      }
      this.busy = false;
      cx.notify();
    });
  }

  key(e, cx, count) {
    if (e.key === "escape") return this.close();
    if (e.key === "tab") (this.inPrompt ? this.folder : this.prompt).focus();
    else if (e.key === "down" && count) this.at = (this.at + 1) % count;
    else if (e.key === "up" && count) this.at = (this.at + count - 1) % count;
    else return;
    cx.stop_propagation();
    cx.notify();
  }

  render() {
    const t = theme();
    const rows = this.rows();
    this.at = Math.max(0, Math.min(this.at, rows.length - 1));
    if (this.at < this.top) this.top = this.at;
    if (this.at >= this.top + ROWS) this.top = this.at - ROWS + 1;
    this.top = Math.max(0, Math.min(this.top, rows.length - ROWS));

    const field = (state, focused) =>
      h_flex().h(36).flex_none().px(10).items_center().rounded(9).border_1()
        .border_color(focused ? t.accent : t.input).bg(t.background)
        .child(Input.new(state).flex_1().h_full().text_size(12.8).text_color(t.foreground));

    const row = (dir, i) =>
      h_flex().id(`wk-${i}`).mx(4).px(10).h(30).flex_none().items_center().rounded(7).cursor_pointer()
        .when(i === this.at, (el) => el.bg(t.hover))
        .hover((s) => s.bg(t.hover))
        .on_click((_e, cx) => { this.at = i; this.open(cx); })
        .child(div().flex_1().truncate().text_color(i === this.at ? t.foreground : t.muted).child(tilde(dir)));

    return v_flex().id("wk").track_focus(this.handle)
      .on_key_down((e, cx) => this.key(e, cx, rows.length))
      .w_full().min_h(0).p(18).gap(10).bg(t.popover).text_size(13).text_color(t.foreground)
      .child(h_flex().items_center()
        .child(div().flex_1().text_size(15).font_semibold().child(this.busy ? "Opening…" : "Worktree agent"))
        .child(div().text_size(11).text_color(t.dim).child("Tab: message · Esc")))
      .child(field(this.folder, !this.inPrompt))
      .child(field(this.prompt, this.inPrompt))
      .when(Boolean(this.error), (el) => el.child(div().text_size(12).text_color(t.blocked).child(this.error)))
      .child(v_flex().children(rows.slice(this.top, this.top + ROWS).map((d, i) => row(d, this.top + i))))
      .when(rows.length === 0 && !this.error, (el) => el.child(div().px(14).text_color(t.dim).child("No projects match")));
  }
}
