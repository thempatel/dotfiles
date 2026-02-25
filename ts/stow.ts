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

type RegisteredProject = {
  name: string;
  configPath: string;
  root: string;
  config: StowConfig;
};

const REGISTRY_DIR = path.join(Deno.env.get('HOME')!, '.config', 'mystow');

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

function getConfigPath(): string {
  const localConfig = path.join(Deno.cwd(), 'stow.yaml');
  try {
    Deno.statSync(localConfig);
    return localConfig;
  } catch {
    return getDefaultConfigPath();
  }
}

const STOW_BIN = getBin('stow');

function stow(
  root: string,
  source: string,
  target: string,
  adopt: boolean,
  del: boolean,
  dryRun = false,
  pipe = false,
): Deno.CommandOutput {
  // GNU stow only accepts single-level package names, so for multi-level
  // sources like "configs/ssh", use the parent as cwd and basename as package
  const stowDir = path.join(root, path.dirname(source));
  const pkg = path.basename(source);
  const resolved = path.join(stowDir, pkg);
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
    pkg,
  ];

  if (dryRun) {
    args.unshift('-n');
  }

  if (adopt) {
    args.splice(dryRun ? 4 : 3, 0, '--adopt');
  }

  if (del) {
    const idx = args.indexOf('-R');
    args.splice(idx, 1, '-D');
  }

  const stdio = pipe ? 'piped' as const : 'inherit' as const;
  const command = new Deno.Command(STOW_BIN, {
    args,
    cwd: stowDir,
    stdout: stdio,
    stderr: stdio,
  });

  const result = command.outputSync();
  if (!result.success) {
    throw new Error(`stow failed`);
  }
  return result;
}

function registerProject(configPath: string, name?: string): void {
  const resolved = path.resolve(configPath);

  // Validate the config loads properly
  loadConfig(resolved);

  const projectName = name || path.basename(path.dirname(resolved));

  Deno.mkdirSync(REGISTRY_DIR, { recursive: true });

  const linkPath = path.join(REGISTRY_DIR, projectName);

  // Remove existing symlink if present
  try {
    Deno.lstatSync(linkPath);
    Deno.removeSync(linkPath);
  } catch {
    // doesn't exist, that's fine
  }

  Deno.symlinkSync(resolved, linkPath);
  console.log(`Registered "${projectName}" -> ${resolved}`);
}

function listRegisteredProjects(): RegisteredProject[] {
  try {
    Deno.statSync(REGISTRY_DIR);
  } catch {
    return [];
  }

  const projects: RegisteredProject[] = [];

  for (const entry of Deno.readDirSync(REGISTRY_DIR)) {
    const linkPath = path.join(REGISTRY_DIR, entry.name);
    try {
      const configPath = Deno.readLinkSync(linkPath);
      // Validate symlink target exists
      Deno.statSync(configPath);
      const config = loadConfig(configPath);
      projects.push({
        name: entry.name,
        configPath,
        root: path.dirname(configPath),
        config,
      });
    } catch {
      console.warn(`Warning: stale registry entry "${entry.name}", skipping`);
    }
  }

  projects.sort((a, b) => a.name.localeCompare(b.name));
  return projects;
}

function isStowed(root: string, stowable: Stowable): boolean {
  // Dry-run a restow: stow emits UNLINK lines for already-stowed items
  try {
    const result = stow(
      root,
      stowable.source,
      stowable.target,
      false,
      false,
      true,
      true,
    );
    const output = new TextDecoder().decode(result.stderr);
    return output.includes('UNLINK:');
  } catch {
    return false;
  }
}

async function interactiveMode(
  projects: RegisteredProject[],
): Promise<void> {
  const { checkbox } = await import('@inquirer/prompts');

  if (projects.length === 0) {
    console.log(
      'No registered projects. Use "stow! register" to register a project.',
    );
    return;
  }

  let selectedProjects: RegisteredProject[];
  if (projects.length === 1) {
    selectedProjects = projects;
  } else {
    try {
      const selectedNames: string[] = await checkbox({
        message: 'Select projects to manage',
        choices: projects.map((p) => ({
          name: p.name,
          value: p.name,
        })),
      });

      selectedProjects = projects.filter((p) => selectedNames.includes(p.name));
    } catch (e) {
      if (e instanceof Error && e.name === 'ExitPromptError') {
        return;
      }
      throw e;
    }

    if (selectedProjects.length === 0) {
      console.log('No projects selected.');
      return;
    }
  }

  for (const project of selectedProjects) {
    const stowStates = project.config.targets.map((t) => ({
      stowable: t,
      wasStowed: isStowed(project.root, t),
    }));

    let selected: string[];
    try {
      selected = await checkbox({
        message: `[${project.name}] Toggle items`,
        choices: stowStates.map(({ stowable, wasStowed }) => ({
          name: `${stowable.source} -> ${stowable.target}`,
          value: stowable.source,
          checked: wasStowed,
        })),
      });
    } catch (e) {
      if (e instanceof Error && e.name === 'ExitPromptError') {
        return;
      }
      throw e;
    }

    for (const { stowable, wasStowed } of stowStates) {
      const nowSelected = selected.includes(stowable.source);

      if (!wasStowed && nowSelected) {
        console.log(`Stowing ${stowable.source}...`);
        stow(project.root, stowable.source, stowable.target, false, false);
      } else if (wasStowed && !nowSelected) {
        console.log(`Unstowing ${stowable.source}...`);
        stow(project.root, stowable.source, stowable.target, false, true);
      }
    }
  }
}

function projectFromConfig(configPath: string): RegisteredProject {
  const resolved = path.resolve(configPath);
  const config = loadConfig(resolved);
  return {
    name: path.basename(path.dirname(resolved)),
    configPath: resolved,
    root: path.dirname(resolved),
    config,
  };
}

async function main() {
  const program = new Command();

  program
    .name('stow!')
    .description('Manage dotfiles with GNU Stow')
    .option('-c, --config <path>', 'path to stow.yaml config file')
    .option('-y, --yes', 'non-interactive mode, stow all targets', false)
    .option('-d, --delete', 'delete existing links', false)
    .option('-a, --adopt', 'adopt existing files into stow directory', false)
    .action(async () => {
      const opts = program.opts<{
        config?: string;
        yes: boolean;
        delete: boolean;
        adopt: boolean;
      }>();

      // -c narrows to a single project, otherwise use all registered projects
      const projects = opts.config
        ? [projectFromConfig(opts.config)]
        : listRegisteredProjects();

      if (opts.yes) {
        for (const project of projects) {
          for (const t of project.config.targets) {
            stow(project.root, t.source, t.target, opts.adopt, opts.delete);
          }
        }
        return;
      }

      await interactiveMode(projects);
    });

  // register subcommand
  program
    .command('register [name]')
    .description('Register a project in the stow registry')
    .option('-c, --config <path>', 'path to stow.yaml config file')
    .action((name: string | undefined, opts: { config?: string }) => {
      const configPath = opts.config || getConfigPath();
      registerProject(configPath, name);
    });

  await program.parseAsync(Deno.args, { from: 'user' });
}

await main();
