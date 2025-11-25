#!/usr/bin/env dev-deno

import { errFromStdErr, toString } from './lib/utils.ts';

function mergeBase() {
  const { stdout, stderr, success } = new Deno.Command('git', {
    args: ['merge-base', 'HEAD', 'main'],
  }).outputSync();

  if (!success) {
    throw errFromStdErr(stderr);
  }

  return toString(stdout).trim();
}

function branchesForBase(base: string): string[] {
  const { stdout, stderr, success } = new Deno.Command('git', {
    args: ['branch', '--contains', base],
  }).outputSync();

  if (!success) {
    throw errFromStdErr(stderr);
  }

  return toString(stdout).trim().split('\n');
}

const defaultBranch = 'main';
function getBase(branches: string[]): string {
  if (branches.length <= 1) {
    return defaultBranch;
  }

  const currBranchIdx = branches.findIndex((b) => b.startsWith('*'));
  if (currBranchIdx === branches.length - 1) {
    return defaultBranch;
  }

  const base = branches[currBranchIdx + 1];
  return base.replace(/^\*/, '').trim();
}

function main() {
  const baseCommit = mergeBase();
  const branches = branchesForBase(baseCommit);
  const base = getBase(branches);
  console.log(base);
}

main();
