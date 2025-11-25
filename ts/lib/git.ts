import { runCommand } from './utils.ts';

type Stat = {
  unknown: string;
} | {
  add: number;
  del: number;
  file: string;
};

type NumStats = {
  sha: string;
  stats: Stat[];
};

export function parseGitNumStat(lines: string[]): NumStats | undefined {
  if (!lines.length) {
    return;
  }

  const toRet: NumStats = {
    sha: lines[0].trim(),
    stats: [],
  };

  for (const [i, line] of lines.entries()) {
    if (!line || i === 0) {
      continue;
    }

    const parts = line.split(/\s+/);
    if (parts.length < 3) {
      toRet.stats.push({
        unknown: line,
      });
      continue;
    }

    const add = parts[0];
    const del = parts[1];
    const file = parts[2];
    toRet.stats.push({
      add: parseInt(add),
      del: parseInt(del),
      file,
    });
  }

  return toRet;
}

export async function gitNumStatHead(
  cwd?: string,
): Promise<NumStats | undefined> {
  const { stdout, success, stderr } = await runCommand('git', {
    args: ['show', '-n1', '--pretty=format:"%H"', '--numstat', 'HEAD'],
    cwd,
  });

  if (!success) {
    throw new Error(`${stderr}`);
  }

  const output = stdout.trim();
  return output ? parseGitNumStat(output.split('\n')) : undefined;
}

export async function fetchUntrackedFiles(): Promise<string[]> {
  const { stdout, success } = await runCommand('git', {
    args: ['ls-files', '--others', '--exclude-standard'],
  });

  if (!success) {
    return [];
  }

  const output = stdout.trim();
  return output ? output.split('\n') : [];
}

export async function stageFiles(filePaths: string[]) {
  const cmd = new Deno.Command('git', {
    args: ['add', ...filePaths],
    stdout: 'piped',
    stderr: 'piped',
  });
  await cmd.output();
}

export async function getGitRoot(cwd?: string): Promise<string | undefined> {
  const { stdout, success } = await runCommand('git', {
    args: ['rev-parse', '--show-toplevel'],
    cwd,
  });

  if (!success) {
    return undefined;
  }

  const output = stdout.trim();
  return output || undefined;
}
