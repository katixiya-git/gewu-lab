# 格物前端（Vue 3 + Element Plus）

格物 · 实验室智能预约平台的前端。学生端以对话为主入口，管理端管实验室、设备、预约审核与用户。

## 脚本

```bash
npm install
npm run dev      # 开发服务器 5173，/api 与 /media 已代理到 http://127.0.0.1:8000
npm run build    # 产物到 dist/
npm run preview  # 预览构建产物
```

Node 版本要求见 `package.json` 的 `engines`（Node 22.18+ 或 24.12+）。

## 目录

```
src/
├── api/            后端接口封装
│   ├── request.js     axios 实例：统一解包 {code,message,data}，401 清登录态
│   ├── sse.js         SSE 分片解析（纯函数，可用 node 直接测）
│   ├── ai.js          对话流：fetch + ReadableStream，逐帧派发事件
│   └── booking.js 等  各业务接口
├── components/     通用组件（booking/BookingCard.vue 是对话里的预约单）
├── views/
│   ├── student/      对话、实验室、我的预约
│   ├── admin/        审核、实验室管理、设备管理、用户管理
│   └── ...           登录、注册、个人资料
├── router/         路由与登录/角色守卫
├── utils/          展示层工具（状态文案、类型文案、日期格式）
└── styles/         全局样式与 Element Plus 皮肤
```

## 对话链路（前端侧）

```
ChatView.vue
   │ streamChat()  —— src/api/ai.js：fetch + AbortController
   ▼
sse.js  parseSSEChunk()   把网络分片切成一帧帧 {event, data}
   ▼
chatEvents.js  applyEvent()   归约到「本轮助手消息」对象上
   ▼
模板渲染：气泡文字 / 工具进度 / 预约卡片（BookingCard.vue）
```

- 事件类型：`user_message`、`token`、`tool_call`、`tool`、`booking_card`、`error`、`done`，每条带 `seq`，跳号会提示。
- 卡片只是「提议」，点「确认预约」才调 `POST /api/bookings` 真正创建；生成过程中按钮禁用，被新卡片取代的旧卡片置灰。

## 验证

```bash
node scripts/check-sse.mjs   # SSE 解析器的 7 组用例（不依赖测试框架）
npm run build                # 构建校验
```
