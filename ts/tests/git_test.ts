import { assertSnapshot } from '@std/testing/snapshot';
import * as path from '@std/path';
import { parseGitNumStat } from '../lib/git.ts';

Deno.test('parseGitNumStat', async (t) => {
  const dataDir = path.join(path.dirname(path.fromFileUrl(import.meta.url)), 'data');
  const numstatContent = await Deno.readTextFile(path.join(dataDir, 'numstat.txt'));
  const lines = numstatContent.trim().split('\n');

  const result = parseGitNumStat(lines);

  await assertSnapshot(t, result);
});
