# 消息管道

消息管道是 Qtine 的核心，所有进入机器人的消息都会经过管道处理。

## 三阶段架构

```
PRE（预处理）  →  HANDLER（命令处理）  →  POST（后处理）
```

每个阶段可以注册多个中间件，按注册顺序执行。

### PRE 阶段

预处理阶段，在命令匹配之前执行。典型用途：

- **黑名单过滤**：拦截黑名单用户的消息
- **频率限制**：防止刷屏
- **日志记录**：记录所有进入的消息

### HANDLER 阶段

命令处理阶段，按顺序尝试匹配：

1. **命令匹配**：精确匹配命令前缀（如 `#help`、`/echo`）
2. **正则匹配**：正则表达式匹配
3. **关键词匹配**：包含关键词即触发

任一匹配成功并产生回复后，管道终止。

### POST 阶段

后处理阶段，在命令未匹配时执行。典型用途：

- **复读检测**：群聊刷屏自动 +1
- **默认回复**：未匹配命令时的兜底回复

## 中间件签名

每个中间件是一个函数：

```python
def my_middleware(ctx: PipelineContext, next_fn):
    # 前置处理
    result = next_fn(ctx)  # 调用下一个中间件
    # 后置处理
    return result
```

- `ctx`：[PipelineContext](https://github.com/QtineNiko/Qtine/blob/main/qtine/core/pipeline.py) 上下文，包含消息、回复方法等
- `next_fn`：调用下一个中间件的函数
- 返回值：回复内容（字符串或 None）

## 内置中间件

Qtine 默认注册了以下中间件：

### PRE 阶段

1. **pre_blacklist**：黑名单过滤
2. **pre_rate_limit**：频率限制

### HANDLER 阶段

**handler_commands**：命令/正则/关键词匹配

流程：

1. 调用 `PluginManager.find_command_handler(content)` 查找命令
2. 命中则检查权限（admin/user）
3. 执行处理函数，结果作为回复
4. 未命中则尝试正则匹配
5. 仍未命中则尝试关键词匹配
6. 都未命中则进入 POST 阶段

### POST 阶段

**post_repeat**：复读检测（调用 `repeat` 插件）

## 自定义中间件示例

```python
from qtine.core.pipeline import PipelineContext


def my_middleware(ctx: PipelineContext, next_fn):
    # 前置：记录消息
    print(f"收到消息: {ctx.message.content}")

    # 调用下一个中间件
    result = next_fn(ctx)

    # 后置：记录回复
    if result:
        print(f"回复: {result}")

    return result


# 注册到管道
bot.pipeline.pre(my_middleware)
```

## 中止处理

中间件可以通过 `ctx.abort()` 中止后续处理：

```python
def block_spam(ctx: PipelineContext, next_fn):
    if is_spam(ctx.message):
        ctx.abort("Spam detected")
        return None  # 必须返回 None
    return next_fn(ctx)
```

中止后：

- 后续中间件不再执行
- `process()` 返回 None
- 不会有回复发送

## PipelineContext

`PipelineContext` 主要属性：

| 属性 | 类型 | 说明 |
|------|------|------|
| `message` | Message | 原始消息对象 |
| `response` | str / None | 当前回复内容 |
| `aborted` | bool | 是否被中止 |

主要方法：

| 方法 | 说明 |
|------|------|
| `reply(text)` | 设置回复内容 |
| `abort(reason)` | 中止管道处理 |

## 完整流程示例

用户发送 `#help`：

```
1. PRE: pre_blacklist 检查用户是否在黑名单 → 否，放行
2. PRE: pre_rate_limit 检查频率 → 未超限，放行
3. HANDLER: handler_commands 调用 PluginManager
   - find_command_handler("#help") 命中 help 插件
   - 检查权限：user 级别，放行
   - 执行 HelpPlugin 的处理函数
   - 返回帮助文本
4. POST: 跳过（HANDLER 已返回结果）
5. 管道返回帮助文本
6. Bot 将文本通过适配器发送给用户
```
