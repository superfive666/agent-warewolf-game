import { useState } from 'react';

import type { ActionPayload, PendingAction } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { Disclosure } from '@/components/ui/Disclosure';

import { FormFieldInput } from './FormFieldInput';
import { buildAction, formProblems, initialValues, type FormValues } from './model';

interface ActionFormProps {
  pending: PendingAction;
  onSubmit: (requestId: number, action: ActionPayload) => Promise<void>;
}

/** 轮到你了：按服务端给的表单描述渲染，提交后交引擎校验。父组件用 request_id 当 key，换一条待办就重置 */
export function ActionForm({ pending, onSubmit }: ActionFormProps) {
  const form = pending.form;
  const [values, setValues] = useState<FormValues>(() => (form ? initialValues(form) : {}));
  const [submitting, setSubmitting] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  if (!form) return null;

  const main = form.fields.filter((f) => !f.advanced);
  const more = form.fields.filter((f) => f.advanced);
  const field = (f: (typeof form.fields)[number]) => (
    <FormFieldInput
      key={f.name}
      field={f}
      value={values[f.name]}
      onChange={(v) => setValues((old) => ({ ...old, [f.name]: v }))}
    />
  );

  async function submit() {
    if (!form) return;
    const problems = formProblems(form, values);
    if (problems.length) {
      setProblem(problems.join('；'));
      return;
    }
    setSubmitting(true);
    setProblem(null);
    try {
      await onSubmit(pending.request_id, buildAction(form, values));
    } catch (e) {
      setProblem(`提交失败：${e instanceof Error ? e.message : String(e)}`);
      setSubmitting(false);
    }
  }

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <div className="flex flex-col gap-1">
        <b className="font-serif text-20 text-gold-hi">轮到你了 ·「{form.action_cn}」</b>
        <p className="m-0 text-13 leading-[1.6] text-dim">{form.description}</p>
      </div>
      {pending.error && (
        <p
          role="alert"
          className="m-0 rounded-[10px] border border-wolf-line bg-wolf-bg px-3.5 py-2.5 text-13 text-wolf-soft"
        >
          上次提交没通过：{pending.error}
        </p>
      )}
      {main.map(field)}
      {more.length > 0 && (
        <Disclosure summary="更多（可选）" bodyClassName="flex flex-col gap-4">
          {more.map(field)}
        </Disclosure>
      )}
      {problem && (
        <p role="alert" className="m-0 text-13 text-wolf-fg">
          {problem}
        </p>
      )}
      <Button type="submit" variant="primary" disabled={submitting}>
        {submitting ? '已提交，等待结算…' : '提交'}
      </Button>
    </form>
  );
}
