const decoder = new TextDecoder();

export function toString(bytes: Uint8Array<ArrayBuffer>): string {
  return decoder.decode(bytes);
}

export function errFromStdErr(stderr: Uint8Array<ArrayBuffer>): Error {
  return new Error(`${toString(stderr)}`);
}

export async function runCommand(
  command: string | URL,
  options?: Omit<Deno.CommandOptions, 'stdout' | 'stderr'>,
): Promise<Deno.CommandStatus & { stdout: string; stderr: string }> {
  const cmd = new Deno.Command(command, {
    ...options,
    stdout: 'piped',
    stderr: 'piped',
  });

  const { stdout, stderr, ...rest } = await cmd.output();

  return {
    ...rest,
    stdout: toString(stdout),
    stderr: toString(stderr),
  };
}

export async function highlightFile(filePath: string): Promise<string> {
  try {
    const cmd = new Deno.Command('bat', {
      args: [
        '--color=always',
        '--style=plain',
        filePath,
      ],
      stdout: 'piped',
      stderr: 'piped',
    });

    const { stdout, success } = await cmd.output();

    if (!success) {
      // Fallback to plain text if bat fails
      return await Deno.readTextFile(filePath);
    }

    return toString(stdout);
  } catch {
    // Fallback to plain text if bat is not available
    return await Deno.readTextFile(filePath);
  }
}
