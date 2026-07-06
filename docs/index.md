---
layout: home

hero:
  name: Qtine
  text: 模块化聊天机器人框架
  tagline: 基于 Flask + WebSocket，支持 OneBot V11 / NapCat，插件化扩展，开箱即用
  image:
    src: /logo.svg
    alt: Qtine
  actions:
    - theme: brand
      text: 开始使用
      link: /guide/what-is-qtine
    - theme: alt
      text: GitHub
      link: https://github.com/QtineNiko/Qtine

features:
  - icon: 🧩
    title: 插件化架构
    details: 支持热加载、热启用/禁用，插件以 .zip 包导入，管理后台一目了然。
  - icon: 🔌
    title: 多平台适配器
    details: 内置 OneBot V11 适配器，无缝对接 NapCat / LLOneBot，预留 Discord / Telegram 扩展能力。
  - icon: 🔄
    title: 反向 & 正向 WebSocket
    details: 同时支持 NapCat 主动连接和 Qtine 主动连接两种模式，灵活适配各种网络环境。
  - icon: 🖥️
    title: WebUI 管理面板
    details: Material Design 3 风格，仪表盘、插件管理、适配器管理、日志查看、系统设置一应俱全。
  - icon: 💬
    title: 聊天式命令管理
    details: 在 QQ 群里直接用命令管理机器人，启用/禁用插件、重连适配器、查看日志，无需登录后台。
  - icon: 🛡️
    title: 权限与频率限制
    details: 管理员/普通用户两级权限，令牌桶算法防刷屏，黑名单机制保障安全。
  - icon: 💾
    title: 持久化存储
    details: 支持 SQLite 持久化或内存存储，会话状态、配置、缓存全部可保存。
  - icon: 🐳
    title: Docker 一键部署
    details: 提供完整 Docker Compose 配置，一行命令部署上线。
---
