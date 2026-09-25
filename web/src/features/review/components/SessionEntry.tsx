import type { AgentSession } from '@/api/types';
import { Disclosure } from '@/components/ui/Disclosure';
import { Pre } from '@/components/ui/Pre';

const SubTitle = ({ children }: { children: string }) => <div className="text-13 text-gold">{children}</div>;

/** 一个座位的完整会话：私人笔记、system prompt、逐条消息 */
export function SessionEntry({ session: s }: { session: AgentSession }) {
  const meta =
    `${s.backend_cn || s.backend || ''}${s.model ? ` / ${s.model}` : ''}` +
    ` · 离场原因：${s.release_reason_cn || s.release_reason || '—'}` +
    (s.memory_uri ? ` · memory 卷：${s.memory_uri}` : '');

  return (
    <>
      <div className="pt-3.5 font-mono text-12 text-dim">{meta}</div>
      {s.notes && (
        <div>
          <SubTitle>私人笔记本（只有它自己看得到）</SubTitle>
          <Pre>{s.notes}</Pre>
        </div>
      )}
      {s.system_prompt && (
        <Disclosure summary="system prompt（整局逐字不变）">
          <Pre>{s.system_prompt}</Pre>
        </Disclosure>
      )}
      {(s.messages ?? []).map((m, i) => (
        <div key={i}>
          <SubTitle>{`#${i + 1} ${m.role}`}</SubTitle>
          <Pre>{typeof m.content === 'string' ? m.content : JSON.stringify(m.content, null, 2)}</Pre>
        </div>
      ))}
    </>
  );
}
