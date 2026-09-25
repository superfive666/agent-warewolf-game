"""集群部署：每个座位一个 Pod，用 kubernetes 官方 SDK 直接操作。

  start()   创建 PVC（memory）→ 创建 Pod → 等 Ready → 拿 Pod IP
  release() 先抓会话（RuntimePool 负责）→ 删 Pod
            **PVC 不删** —— agent 的私有笔记本要活得比 Pod 长

编排端需要能直连 Pod IP（跑在集群内，或者通过 port-forward）。
"""
from __future__ import annotations

import time

from .http import AgentUnreachable, HttpRuntime

DEFAULT_NAMESPACE = "werewolf"


def load_k8s():
    """惰性导入官方 SDK，并加载 in-cluster 或 kubeconfig 配置。"""
    try:
        from kubernetes import client, config
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "k8s 部署需要官方 SDK：uv sync --extra k8s"
        ) from exc
    try:
        config.load_incluster_config()
    except Exception:
        config.load_kube_config()
    return client


class K8sRuntime(HttpRuntime):
    def __init__(self, seat: int, spec, *, game_id: str, image: str,
                 namespace: str = DEFAULT_NAMESPACE, env: dict | None = None,
                 secret_name: str | None = None,
                 cpu: str = "500m", memory: str = "1Gi",
                 storage: str = "256Mi", storage_class: str | None = None,
                 service_account: str | None = None,
                 label: str = "", **kw) -> None:
        self.seat = seat
        self.spec = spec
        self.game_id = game_id
        self.image = image
        self.namespace = namespace
        self.env = dict(env or {})
        self.secret_name = secret_name
        self.cpu, self.memory = cpu, memory
        self.storage, self.storage_class = storage, storage_class
        self.service_account = service_account
        self.pod_name = f"wolf-{game_id}-seat-{seat:02d}"
        #: PVC 独立于 Pod，Pod 删了笔记还在
        self.pvc_name = f"wolf-{game_id}-mem-{seat:02d}"
        self._client = None
        self._api = None
        super().__init__(seat, "http://unset", label=label or f"k8s:{spec.label}", **kw)

    # ------------------------------------------------------------------
    @property
    def api(self):
        if self._api is None:
            self._client = load_k8s()
            self._api = self._client.CoreV1Api()
        return self._api

    def _labels(self) -> dict:
        return {"app": "werewolf-agent", "werewolf/game": self.game_id,
                "werewolf/seat": str(self.seat)}

    def _pvc_manifest(self):
        c = self._client
        return c.V1PersistentVolumeClaim(
            metadata=c.V1ObjectMeta(name=self.pvc_name, labels=self._labels()),
            spec=c.V1PersistentVolumeClaimSpec(
                access_modes=["ReadWriteOnce"],
                storage_class_name=self.storage_class,
                resources=c.V1ResourceRequirements(requests={"storage": self.storage}),
            ),
        )

    def _pod_manifest(self):
        c = self._client
        env = [
            c.V1EnvVar(name="WEREWOLF_SEAT", value=str(self.seat)),
            c.V1EnvVar(name="WEREWOLF_BACKEND", value=self.spec.backend),
            c.V1EnvVar(name="WEREWOLF_MODEL", value=self.spec.model),
            c.V1EnvVar(name="WEREWOLF_EFFORT", value=self.spec.effort),
            c.V1EnvVar(name="WEREWOLF_BASE_URL", value=self.spec.base_url),
            c.V1EnvVar(name="WEREWOLF_API_KEY_ENV", value=self.spec.api_key_env),
            c.V1EnvVar(name="WEREWOLF_MAX_TOKENS", value=str(self.spec.max_tokens)),
            c.V1EnvVar(name="WEREWOLF_MEMORY_DIR", value="/memory"),
            c.V1EnvVar(name="WEREWOLF_PORT", value="8100"),
        ] + [c.V1EnvVar(name=k, value=str(v)) for k, v in self.env.items()]
        if self.spec.api_key:
            # 注意：直接注进 Pod spec 的密钥，任何能 `kubectl get pod -o yaml`
            # 的人都看得到。生产环境请改用下面的 Secret 方式。
            env.append(c.V1EnvVar(name=self.spec.api_key_env, value=self.spec.api_key))
        elif self.secret_name:
            env.append(c.V1EnvVar(
                name="ANTHROPIC_API_KEY",
                value_from=c.V1EnvVarSource(secret_key_ref=c.V1SecretKeySelector(
                    name=self.secret_name, key="api-key")),
            ))
        return c.V1Pod(
            metadata=c.V1ObjectMeta(name=self.pod_name, labels=self._labels()),
            spec=c.V1PodSpec(
                restart_policy="Never",
                service_account_name=self.service_account,
                containers=[c.V1Container(
                    name="agent",
                    image=self.image,
                    command=["werewolf-agent"],
                    ports=[c.V1ContainerPort(container_port=8100)],
                    env=env,
                    resources=c.V1ResourceRequirements(
                        requests={"cpu": self.cpu, "memory": self.memory},
                        limits={"cpu": self.cpu, "memory": self.memory}),
                    volume_mounts=[c.V1VolumeMount(name="memory", mount_path="/memory")],
                    readiness_probe=c.V1Probe(
                        http_get=c.V1HTTPGetAction(path="/healthz", port=8100),
                        initial_delay_seconds=2, period_seconds=2, failure_threshold=30),
                    security_context=c.V1SecurityContext(
                        allow_privilege_escalation=False,
                        run_as_non_root=False,
                        capabilities=c.V1Capabilities(drop=["ALL"])),
                )],
                volumes=[c.V1Volume(
                    name="memory",
                    persistent_volume_claim=c.V1PersistentVolumeClaimVolumeSource(
                        claim_name=self.pvc_name))],
            ),
        )

    # ------------------------------------------------------------------
    def start(self) -> None:
        api = self.api
        for create, manifest, kind in (
            (api.create_namespaced_persistent_volume_claim, self._pvc_manifest(), "PVC"),
            (api.create_namespaced_pod, self._pod_manifest(), "Pod"),
        ):
            try:
                create(namespace=self.namespace, body=manifest)
            except Exception as exc:
                if getattr(exc, "status", None) != 409:  # 409 = 已存在，复用
                    raise RuntimeError(f"创建 {kind} {self.pod_name} 失败：{exc}") from exc

        deadline = time.time() + self.ready_timeout
        while time.time() < deadline:
            pod = api.read_namespaced_pod(self.pod_name, self.namespace)
            ready = any(
                c.type == "Ready" and c.status == "True"
                for c in (pod.status.conditions or [])
            )
            if ready and pod.status.pod_ip:
                self.base_url = f"http://{pod.status.pod_ip}:8100"
                return
            if pod.status.phase in ("Failed", "Succeeded"):
                raise AgentUnreachable(f"{self.pod_name} 进入 {pod.status.phase}")
            time.sleep(1)
        raise AgentUnreachable(f"{self.pod_name} 在 {self.ready_timeout}s 内没有 Ready")

    def release(self, reason: str) -> None:
        """删 Pod。**PVC 保留** —— 笔记要活得比 Pod 长。"""
        if self._released:
            return
        try:
            self.api.delete_namespaced_pod(
                self.pod_name, self.namespace,
                grace_period_seconds=5,
                body=self._client.V1DeleteOptions(propagation_policy="Background"),
            )
        except Exception:
            pass  # 已经没了也算成功
        super().release(reason)

    def logs(self, tail: int = 50) -> str:
        try:
            return self.api.read_namespaced_pod_log(
                self.pod_name, self.namespace, tail_lines=tail)
        except Exception as exc:
            return f"取日志失败：{exc}"
