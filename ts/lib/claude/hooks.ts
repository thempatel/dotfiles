import * as z from '@zod/zod';

const BaseHook = z.object({
  session_id: z.string(),
  transcript_path: z.string(),
  cwd: z.string(),
  permission_mode: z.string(),
});

const StandardToolInput = z.object({
  tool_use_id: z.string(),
  tool_name: z.union([
    z.literal('Write'),
    z.literal('Edit'),
  ]),
  tool_input: z.object({
    file_path: z.string(),
    content: z.string(),
  }),
});

const BashToolInput = z.object({
  tool_use_id: z.string(),
  tool_name: z.literal('Bash'),
  tool_input: z.object({
    command: z.string(),
    description: z.string(),
  }).catchall(z.unknown()),
});

const ToolResponse = z.object({
  tool_response: z.record(z.string(), z.unknown()),
});

const ToolInput = z.discriminatedUnion('tool_name', [
  StandardToolInput,
  BashToolInput,
]);

const PreToolUseInput = BaseHook.extend({
  hook_event_name: z.literal('PreToolUse'),
}).and(ToolInput);
export type PreToolUseInputType = z.infer<typeof PreToolUseInput>;

const PostToolUseInput = BaseHook.extend({
  hook_event_name: z.literal('PostToolUse'),
}).and(ToolInput).and(ToolResponse);
export type PostToolUseInputType = z.infer<typeof PostToolUseInput>;

export const HookInput = z.union([
  PreToolUseInput,
  PostToolUseInput,
]);
export type HookInputType = z.infer<typeof HookInput>;
