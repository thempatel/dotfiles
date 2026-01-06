#!/usr/bin/env dev-deno

import { Command } from 'commander';
import * as path from '@std/path';
import { parse as parseYaml } from '@std/yaml';

type Stowable = {
  source: string;
  target: string;
};

type StowConfig = {
  targets: Stowable[];
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

function resolveTilde(filePath: string): string {
  const home = Deno.env.get('HOME');
  if (!home) {
    throw new Error('HOME environment variable not set');
  }

  if (filePath === '~') {
    return home;
  }

  if (filePath.startsWith('~/')) {
    return path.join(home, filePath.slice(2));
  }

  return filePath;
}

function loadConfig(configPath: string): StowConfig {
  const content = Deno.readTextFileSync(configPath);
  const config = parseYaml(content) as StowConfig;

  if (!config.targets || !Array.isArray(config.targets)) {
    throw new Error('Config must have a "targets" array');
  }

  return config;
}

function getDefaultConfigPath(): string {
  const dotfilesHome = Deno.env.get('DOTFILES_HOME');
  if (!dotfilesHome) {
    throw new Error('DOTFILES_HOME environment variable not set and no config file provided');
  }
  return path.join(dotfilesHome, 'stow.yaml');
}

const STOW_BIN = getBin('stow');

function stow(
  root: string,
  source: string,
  target: string,
  adopt: boolean,
  del: boolean,
): void {
  const resolved = path.join(root, source);
  const resolvedTarget = resolveTilde(target);

  try {
    Deno.statSync(resolved);
  } catch {
    throw new Error(`source ${resolved} not found`);
  }

  try {
    Deno.statSync(resolvedTarget);
  } catch {
    Deno.mkdirSync(resolvedTarget, { recursive: true, mode: 0o755 });
  }

  const args = [
    '-v',
    '-R',
    '--dotfiles',
    '-t',
    path.resolve(resolvedTarget),
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
    cwd: root,
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
    .option('-c, --config <path>', 'path to stow.yaml config file')
    .option('--src <source>', 'source directory to stow')
    .option('--target <target>', 'target directory for stowing')
    .option('--del', 'delete existing links', false)
    .option('--adopt', 'adopt existing files into stow directory', false)
    .parse(Deno.args, { from: 'user' });

  const options = program.opts();

  const configPath = options.config || getDefaultConfigPath();
  const root = path.dirname(path.resolve(configPath));

  if (options.src) {
    if (!options.target) {
      throw new Error('target must be provided if src is provided');
    }
    return stow(root, options.src, options.target, options.adopt, options.del);
  }

  const config = loadConfig(configPath);

  for (const stowable of config.targets) {
    stow(root, stowable.source, stowable.target, options.adopt, options.del);
  }
}

main();
