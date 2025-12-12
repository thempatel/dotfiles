#!/usr/bin/env dev-deno

import { Command } from 'commander';
import * as path from '@std/path';

type Stowable = {
  source: string;
  target: string;
};

function getBin(name: string): string {
  const command = new Deno.Command('which', {
    args: [name],
  }).outputSync();

  if (!command.success) {
    throw new Error(`${name} not on path`);
  }

  return new TextDecoder().decode(command.stdout).trim();
}

const STOW_BIN = getBin('stow');
const ROOT = new Array(2).fill(null).reduce(
  (p) => path.dirname(p),
  path.fromFileUrl(import.meta.url),
);

const home = Deno.env.get('HOME');
if (!home) {
  throw new Error('HOME environment variable not set');
}

const targets: Stowable[] = [
  {
    source: 'zsh',
    target: home,
  },
  {
    source: 'atuin',
    target: path.join(home, '.config', 'atuin'),
  },
  {
    source: 'git',
    target: path.join(home, '.config', 'git'),
  },
  {
    source: 'zed',
    target: path.join(home, '.config', 'zed'),
  },
  {
    source: 'ripgrep',
    target: path.join(home, '.config', 'ripgrep'),
  },
  {
    source: 'vim',
    target: home,
  },
  {
    source: 'claude',
    target: path.join(home, '.claude'),
  },
  {
    source: 'lazygit',
    target: path.join(home, 'Library', 'Application Support', 'lazygit'),
  },
  {
    source: 'tmux',
    target: home,
  },
];

function stow(
  source: string,
  target: string,
  adopt: boolean,
  del: boolean,
): void {
  const resolved = path.join(ROOT, source);
  try {
    Deno.statSync(resolved);
  } catch {
    throw new Error(`source ${resolved} not found`);
  }

  try {
    Deno.statSync(target);
  } catch {
    Deno.mkdirSync(target, { recursive: true, mode: 0o755 });
  }

  const args = [
    '-v',
    '-R',
    '--dotfiles',
    '-t',
    path.resolve(target),
    source,
  ];

  if (adopt) {
    args.splice(3, 0, '--adopt');
  }

  if (del) {
    args.splice(1, 1, '-D');
  }

  const command = new Deno.Command(STOW_BIN, {
    args,
    cwd: ROOT,
    stdout: 'inherit',
    stderr: 'inherit',
  });

  const { success } = command.outputSync();
  if (!success) {
    throw new Error(`stow failed`);
  }
}

function main() {
  const program = new Command();

  program
    .name('stow')
    .description('Manage dotfiles with GNU Stow')
    .option('--src <source>', 'source directory to stow')
    .option('--target <target>', 'target directory for stowing')
    .option('--del', 'delete existing links', false)
    .option('--adopt', 'adopt existing files into stow directory', false)
    .parse(Deno.args, { from: 'user' });

  const options = program.opts();

  if (options.src) {
    if (!options.target) {
      throw new Error('target must be provided if src is provided');
    }
    return stow(options.src, options.target, options.adopt, options.del);
  }

  for (const stowable of targets) {
    stow(stowable.source, stowable.target, options.adopt, options.del);
  }
}

main();
