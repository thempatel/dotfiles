#!/usr/bin/env dev-deno
import {
  HookInput,
  PostToolUseInputType,
  PreToolUseInputType,
} from '@/lib/claude/hooks.ts';
import * as path from '@std/path';
import { exists } from '@std/fs';
import { getGitRoot, gitNumStatHead } from '@/lib/git.ts';

let ROOT = Deno.env.get('DOTFILES_HOME');
if (!ROOT) {
  ROOT = new Array(2).fill(null).reduce(
    (p) => path.dirname(p),
    path.fromFileUrl(import.meta.url),
  );
}

const HOOKS_DATA_DIR = path.join(ROOT!, 'var', 'hooks_data');

function niceJson(out: unknown) {
  return JSON.stringify(out, null, 2);
}

function track(hookInput: unknown, saveDir: string) {
  const filePath = path.join(saveDir, 'input.json');
  Deno.writeTextFileSync(filePath, niceJson(hookInput));
}

async function preToolUseHook(input: PreToolUseInputType) {
}

async function postToolUseHook(input: PostToolUseInputType) {
  if (input.tool_name !== 'Bash') {
    return;
  }

  const command = input.tool_input.command;
  if (!command.includes('git commit')) {
    return;
  }

  const repoRoot = await getGitRoot(input.cwd);
  const numStat = await gitNumStatHead(input.cwd);

  const filePath = path.join(saveDir, 'edits.json');
  const trackingData = {
    repoRoot,
    ...numStat,
  };
  Deno.writeTextFileSync(filePath, niceJson(trackingData));
}

async function main() {
  const input = await new Response(Deno.stdin.readable).json();

  track(input, saveDir);

  const hookInput = HookInput.safeParse(input);

  if (!hookInput.success) {
    throw new Error(`Failed to parse: ${hookInput.error}`);
  }

  switch (hookInput.data.hook_event_name) {
    case 'PreToolUse':
      await preToolUseHook(hookInput.data);
    case 'PostToolUse':
      await postToolUseHook(hookInput.data);
      break;
    default:
      break;
  }
}

main().then(() => {
  Deno.exit(0);
}).catch((e) => {
  console.log(e);
  Deno.exit(1);
});
