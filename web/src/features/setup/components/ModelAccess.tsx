import { Disclosure } from '@/components/ui/Disclosure';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';

import type { SetupState } from '../model';
import type { SetupAction } from '../useSetupForm';

interface ModelAccessProps {
  state: SetupState;
  dispatch: (a: SetupAction) => void;
}

/** 自带 provider 的三件套：网关地址 + API Key（或密钥所在的环境变量名） */
export function ModelAccess({ state, dispatch }: ModelAccessProps) {
  return (
    <Disclosure summary="模型接入（网关地址 / API Key）" bodyClassName="flex flex-col gap-3.5">
      <Field label="OpenAI 兼容网关地址" help="留空则用服务端的 OPENAI_BASE_URL">
        <Input
          placeholder="https://my-gateway/v1"
          value={state.baseUrl}
          onChange={(e) => dispatch({ type: 'set', field: 'baseUrl', value: e.target.value })}
        />
      </Field>
      <Field
        label="API Key"
        help={
          <>
            直接填密钥。<b>不会写进会话库</b>，也不会回传给页面；留空则用服务端环境变量
          </>
        }
      >
        <Input
          type="password"
          placeholder="sk-..."
          autoComplete="off"
          value={state.apiKey}
          onChange={(e) => dispatch({ type: 'set', field: 'apiKey', value: e.target.value })}
        />
      </Field>
      <Field
        label="密钥环境变量名（可选）"
        help={
          <>
            不想直接填密钥时，改成填一个<b>变量名</b>，运行时去那里取
          </>
        }
      >
        <Input
          placeholder="OPENAI_API_KEY"
          value={state.apiKeyEnv}
          onChange={(e) => dispatch({ type: 'set', field: 'apiKeyEnv', value: e.target.value })}
        />
      </Field>
    </Disclosure>
  );
}
