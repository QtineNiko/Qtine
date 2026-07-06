import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'Qtine',
  description: '模块化聊天机器人框架',
  lang: 'zh-CN',
  lastUpdated: true,
  cleanUrls: true,

  head: [
    ['meta', { name: 'theme-color', content: '#3aa675' }],
    ['link', { rel: 'icon', href: '/favicon.svg' }],
  ],

  themeConfig: {
    nav: nav(),
    sidebar: {
      '/guide/': sidebarGuide(),
      '/config/': sidebarConfig(),
      '/develop/': sidebarDevelop(),
      '/commands/': sidebarCommands(),
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/QtineNiko/Qtine' },
    ],

    footer: {
      message: '基于 MIT 协议发布',
      copyright: '版权所有 © 2025 Qtine 开发团队',
    },

    search: {
      provider: 'local',
      options: {
        translations: {
          button: {
            buttonText: '搜索文档',
            buttonAriaLabel: '搜索文档',
          },
          modal: {
            noResultsText: '无法找到相关结果',
            resetButtonTitle: '清除查询条件',
            footer: {
              selectText: '选择',
              navigateText: '切换',
            },
          },
        },
      },
    },

    outline: {
      label: '本页目录',
      level: [2, 3],
    },

    docFooter: {
      prev: '上一页',
      next: '下一页',
    },

    lastUpdatedText: '最后更新于',

    returnToTopLabel: '回到顶部',
    sidebarMenuLabel: '菜单',
    darkModeSwitchLabel: '主题',
    lightModeSwitchTitle: '切换到浅色模式',
    darkModeSwitchTitle: '切换到深色模式',
  },
})

function nav() {
  return [
    { text: '指南', link: '/guide/what-is-qtine', activeMatch: '/guide/' },
    { text: '配置', link: '/config/basic', activeMatch: '/config/' },
    { text: '命令', link: '/commands/user', activeMatch: '/commands/' },
    { text: '开发', link: '/develop/plugin', activeMatch: '/develop/' },
    {
      text: 'GitHub',
      link: 'https://github.com/QtineNiko/Qtine',
    },
  ]
}

function sidebarGuide() {
  return [
    {
      text: '开始',
      collapsed: false,
      items: [
        { text: 'Qtine 是什么', link: '/guide/what-is-qtine' },
        { text: '快速开始', link: '/guide/quick-start' },
        { text: '对接 NapCat', link: '/guide/connect-napcat' },
      ],
    },
    {
      text: '基础',
      collapsed: false,
      items: [
        { text: '目录结构', link: '/guide/structure' },
        { text: 'WebUI 面板', link: '/guide/webui' },
        { text: '插件管理', link: '/guide/plugin-manage' },
        { text: '适配器管理', link: '/guide/adapter-manage' },
      ],
    },
    {
      text: '进阶',
      collapsed: false,
      items: [
        { text: '架构设计', link: '/guide/architecture' },
        { text: '消息管道', link: '/guide/pipeline' },
        { text: '事件总线', link: '/guide/event-bus' },
        { text: '存储后端', link: '/guide/storage' },
        { text: '权限系统', link: '/guide/permission' },
        { text: '频率限制', link: '/guide/rate-limit' },
      ],
    },
    {
      text: '部署',
      collapsed: false,
      items: [
        { text: 'Docker 部署', link: '/guide/docker' },
        { text: '反向代理', link: '/guide/reverse-proxy' },
      ],
    },
    {
      text: '其他',
      collapsed: false,
      items: [
        { text: 'FAQ 常见问题', link: '/guide/faq' },
        { text: '更新日志', link: '/guide/changelog' },
      ],
    },
  ]
}

function sidebarConfig() {
  return [
    {
      text: '配置参考',
      collapsed: false,
      items: [
        { text: '基础配置', link: '/config/basic' },
        { text: '适配器配置', link: '/config/adapter' },
        { text: '安全配置', link: '/config/security' },
        { text: '存储配置', link: '/config/storage' },
        { text: '日志配置', link: '/config/logging' },
        { text: 'WebUI 配置', link: '/config/webui' },
      ],
    },
  ]
}

function sidebarCommands() {
  return [
    {
      text: '命令列表',
      collapsed: false,
      items: [
        { text: '用户命令', link: '/commands/user' },
        { text: '管理员命令', link: '/commands/admin' },
        { text: '插件命令', link: '/commands/plugin' },
      ],
    },
  ]
}

function sidebarDevelop() {
  return [
    {
      text: '开发指南',
      collapsed: false,
      items: [
        { text: '插件开发', link: '/develop/plugin' },
        { text: '适配器开发', link: '/develop/adapter' },
        { text: 'API 接口', link: '/develop/api' },
      ],
    },
  ]
}
