import type { Options, Snapshot } from '@/api/types';

export const OPTIONS: Options = {
  boards: {
    '9': {
      name: '9 人：预女猎',
      wolves: 3,
      gods: 3,
      villagers: 3,
      roles: { WEREWOLF: 3, SEER: 1, VILLAGER: 3 },
    },
    '12': {
      name: '12 人：预女猎白',
      wolves: 4,
      gods: 4,
      villagers: 4,
      roles: { WEREWOLF: 4, SEER: 1, WITCH: 1, HUNTER: 1, IDIOT: 1, VILLAGER: 4 },
    },
  },
  backends: {
    heuristic: { label: '规则 bot' },
    claude: {
      label: 'Claude',
      needs_key: 'ANTHROPIC_API_KEY',
      models: { opus: { label: 'Opus' }, sonnet: { label: 'Sonnet' } },
    },
    openai: {
      label: 'OpenAI',
      needs_key: 'OPENAI_API_KEY',
      custom_model: true,
      models: { gpt: { label: 'GPT' } },
    },
  },
  keys_present: { claude: false, openai: true },
  efforts: ['low', 'medium', 'high', 'xhigh', 'max'],
  deployments: { inprocess: '同进程 —— 最快，调试用', docker: 'Docker —— 每个座位一个容器' },
  defaults: { n_players: 12, max_speech_chars: 450, max_iterations: 3, deployment: 'inprocess' },
};

export function snapshot(over: Partial<Snapshot> = {}): Snapshot {
  return {
    id: 'abc123def456',
    status: 'running',
    day: 1,
    phase: 'NIGHT_WOLF',
    phase_cn: '狼人行动',
    current: { seat: 3, action_type: 'wolf_kill', action_cn: '刀人' },
    players: Array.from({ length: 9 }, (_, i) => ({
      seat: i + 1,
      alive: true,
      is_sheriff: false,
      agent: '规则 bot',
    })),
    ...over,
  };
}
