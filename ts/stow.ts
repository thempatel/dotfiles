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
    throw new Error(
      'DOTFILES_HOME environment variable not set and no config file provided',
    );
  }
  return path.join(dotfilesHome, 'stow.yaml');
}

function getTargetForSource(config: StowConfig, source: string): string {
  const found = config.targets.find((t) => t.source === source);
  if (!found) {
    throw new Error(
      `No target found for source "${source}" in config. Provide one via --target`,
    );
  }
  return found.target;
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
    .option('-s, --src <source>', 'source directory to stow')
    .option('-t, --target <target>', 'target directory for stowing')
    .option('-d, --delete', 'delete existing links', false)
    .option('-a, --adopt', 'adopt existing files into stow directory', false)
    .parse(Deno.args, { from: 'user' });

  const options = program.opts();

  const configPath = options.config || getDefaultConfigPath();
  const root = path.dirname(path.resolve(configPath));

  const config = loadConfig(configPath);

  if (options.src) {
    const target = options.target || getTargetForSource(config, options.src);
    return stow(root, options.src, target, options.adopt, options.delete);
  }

  for (const stowable of config.targets) {
    stow(root, stowable.source, stowable.target, options.adopt, options.del);
  }
}

main();
