# k8s 部署

每个座位一个 Pod，编排端用官方 Python SDK 直接建/删。

```bash
# 1. 建镜像并推到集群能拉到的仓库
docker build -t <registry>/werewolf-agent:latest -f deploy/docker/Dockerfile .
docker push <registry>/werewolf-agent:latest

# 2. API key（LLM 后端需要）
kubectl -n werewolf create secret generic anthropic --from-literal=api-key=sk-ant-...

# 3. 部署
kubectl apply -f deploy/k8s/00-namespace-rbac.yaml
kubectl apply -f deploy/k8s/10-orchestrator.yaml

# 4. 访问
kubectl -n werewolf port-forward svc/werewolf 8000:80
```

## 每个座位的生命周期

```
开局           编排端 create PVC（memory）→ create Pod → 等 readinessProbe 通过
进行中         编排端把 PlayerView 发到 Pod IP:8100/act
玩家离场       ① GET /session 把会话抓出来写进会话库   ← 顺序不能反
（被刀/被票/    ② delete Pod
  自爆/游戏结束）③ PVC 保留，agent 的私有笔记还在
```

**为什么 Role 里没有 `persistentvolumeclaims: delete`**：那是故意的。
Pod 删掉之后笔记必须还在，编排端根本不该有删 PVC 的能力。
清理旧对局的 PVC 是运维的事（带 `werewolf/game=<id>` 标签，可按标签批量清）。

```bash
# 查某一局留下的卷
kubectl -n werewolf get pvc -l werewolf/game=<game_id>
# 确认不再需要之后再手工清
kubectl -n werewolf delete pvc -l werewolf/game=<game_id>
```

## 换掉 SQLite

编排端的 Deployment 固定 `replicas: 1`，因为默认会话库是 SQLite 单文件。
要多副本就实现一个 `PostgresStore`（照着 `werewolf/store/base.py` 的 `SessionStore`
协议写），然后把 `WEREWOLF_STORE` 换成 `postgres://...`。其余代码不用动。
