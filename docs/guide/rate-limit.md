# 频率限制

Qtine 内置基于令牌桶算法的频率限制，防止用户刷屏。

## 配置

```yaml
security:
  rate_limit:
    enabled: true               # 是否启用
    messages_per_second: 5      # 每秒补充的令牌数
    burst: 10                   # 桶容量（允许的瞬时突发）
```

## 工作原理

令牌桶算法：

1. 每个用户有一个"令牌桶"
2. 桶初始容量为 `burst`（突发上限）
3. 每秒补充 `messages_per_second` 个令牌
4. 每次消息消耗 1 个令牌
5. 桶满则不再补充
6. 桶空则拒绝请求

### 示例

配置 `messages_per_second: 5`，`burst: 10`：

- 用户瞬间最多可以发 10 条消息
- 之后每秒恢复 5 条的额度
- 长期平均速率 5 条/秒

## 启用/禁用

### 配置文件

```yaml
security:
  rate_limit:
    enabled: false  # 关闭
```

### 运行时

目前仅支持配置文件控制，不支持运行时切换。

## 触发后行为

被限流的用户：

1. 消息进入 PRE 阶段
2. `pre_rate_limit` 中间件检查令牌
3. 令牌不足 → `ctx.abort("Rate limited")`
4. 管道终止，不回复

::: tip
被限流的消息**不会回复**，避免给刷屏用户更多反馈。
:::

## 自定义限流策略

可以注册自定义中间件实现更复杂的限流：

```python
from qtine.core.pipeline import PipelineContext
import time


# 群聊限流：每群每分钟最多 100 条
_group_buckets = {}


def group_rate_limit(ctx: PipelineContext, next_fn):
    if not ctx.message.is_group():
        return next_fn(ctx)

    group_id = ctx.message.group_id
    now = time.time()
    bucket = _group_buckets.setdefault(group_id, [])
    # 清理 60 秒前的记录
    bucket[:] = [t for t in bucket if now - t < 60]
    if len(bucket) >= 100:
        ctx.abort("Group rate limited")
        return None
    bucket.append(now)
    return next_fn(ctx)


bot.pipeline.pre(group_rate_limit)
```

## 监控

通过 WebUI 或日志查看限流情况：

- 日志中出现 `Rate limited user: <user_id>` 表示触发限流
- 适配器的 `error_count` 不累加（限流不算错误）

## 调优建议

| 场景 | messages_per_second | burst |
|------|---------------------|-------|
| 个人机器人 | 5 | 10 |
| 群机器人 | 2 | 5 |
| 高活跃群 | 10 | 20 |
| 关闭限流 | - | - |

::: warning
`burst` 不要设置过大，否则限流形同虚设。一般 `burst = messages_per_second * 2` 较合理。
:::
