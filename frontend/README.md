# 前端 · Vue 3 + Vite + TypeScript

小学学习工作台的前端。两套界面共用一套骨架：**孩子端**看任务、做题、交作业，**家长端**布置、审核、看周报。

> 本章所有路径均相对于 `frontend/`，例如 `src/App.vue` 即 `frontend/src/App.vue`。

---

## 跑起来

```bash
npm install
npm run dev          # http://localhost:5173
```

| 命令 | 作用 |
|---|---|
| `npm run dev` | 开发服务器，热更新，`/api` 代理到 8000 |
| `npm run build` | 先 `vue-tsc --noEmit` 类型检查，再 `vite build` 输出到 `dist/` |
| `npm run preview` | 本地预览构建产物 |

**只跑前端不够**，`/api` 请求要落到后端。要么另开一个终端起后端，要么在项目根目录跑 `bash scripts/dev.sh` 一次起两边。

依赖已经在磁盘上了（`node_modules` 存在时不用再 `npm install`）。

### IDE 里起

WebStorm 打开 `frontend/` 目录，打开 `package.json`，把光标放到 `"dev": "vite"` 那行，行号栏出现绿色 ▶，点它。

如果报 `npm: command not found`，是 **WebStorm 从 Dock 启动时拿不到 shell 的 PATH**。在 Settings → Languages & Frameworks → JavaScript Runtime 里手动把 Node runtime 指到 `~/.workbuddy/binaries/node/versions/*/bin/node`，Package manager 指到同目录的 `npm`。

---

## 技术栈

| 依赖 | 版本 | 为什么是它 |
|---|---|---|
| vue | 3.5 | 组合式 API + `<script setup>` |
| vue-router | 4.5 | 孩子端和家长端分两组路由，各自懒加载 |
| pinia | 2.3 | 会话上下文只有角色和孩子 id，一个 store 足够 |
| axios | 1.7 | 统一拦截器，页面里不出现裸 axios |
| vite | 6.0 | 开发服务器 + 代理 + 构建 |
| vue-tsc | 2.1 | 类型检查，`build` 里强制先跑 |

**没有 UI 框架**。原型是手写的，直接搬过来的也是手写 CSS + design token 更省事；引 Element Plus 这类库反而要和原型对齐两套视觉。等 M2 表单变多再评估。

**没有 ESLint / Prettier**。单人开发，`vue-tsc` 已经能挡住大部分低级错误。如果后面加，建议只加 `eslint-plugin-vue` 的 essential 规则集，不要开全部。

---

## 目录

```
frontend/
├── index.html
├── vite.config.ts
├── tsconfig.json
├── package.json
└── src/
    ├── main.ts
    ├── App.vue
    ├── env.d.ts
    ├── router/
    │   └── index.ts
    ├── views/
    │   ├── Home.vue
    │   ├── Login.vue
    │   ├── kid/Today.vue          四个分区：今日 / 补做 / 待审核 / 已完成
    │   ├── kid/Task.vue           作业页：计时、拍照、说明、提交
    │   ├── kid/Calc.vue           口算页：一题一屏，交卷当场判分
    │   ├── parent/Dashboard.vue   总览 + 孩子档案
    │   ├── parent/Tasks.vue       布置 / 编辑 / 删除
    │   ├── parent/Review.vue      审核：通过发星、退回、错题判对错
    │   └── parent/Mistakes.vue    错题本：录入、复习节奏、重做记录
    ├── api/
    │   ├── http.ts
    │   ├── auth.ts
    │   ├── tasks.ts
    │   ├── mistakes.ts
    │   ├── calc.ts
    │   └── system.ts
    ├── lib/
    │   └── time.ts                时间格式化与计时
    ├── stores/
    │   └── session.ts
    └── styles/
        └── tokens.css
```

分层比后端简单，只有三条线：**路由决定看哪一页，视图只负责渲染，api 层负责取数**。

---

## 一次请求怎么走

以首页自检为例，`GET /api/v1/health`：

| 步 | 发生什么 | 落在哪 |
|---|---|---|
| 1 | 路由匹配到 `/`，懒加载 `Home.vue` | `src/router/index.ts` |
| 2 | 组件 `onMounted` 调用 `load()` | `src/views/Home.vue` |
| 3 | `load()` 调 `getHealth()`，它内部用 `http.get('/health')` | `src/api/system.ts` |
| 4 | axios 拼出 `/api/v1/health`（`baseURL` 是 `/api/v1`） | `src/api/http.ts` |
| 5 | 浏览器发到 `localhost:5173/api/v1/health` | — |
| 6 | Vite 按 `proxy` 规则转发到 `127.0.0.1:8000`，路径不变 | `vite.config.ts` |
| 7 | 响应回来，拦截器取 `res.data` 直接返回 | `src/api/http.ts` |
| 8 | 组件拿到 `Health` 对象，渲染三张状态卡 | `src/views/Home.vue` |

**关键点：前端代码里永远不出现后端地址。** 只写 `/api/v1/xxx`，本地靠 Vite 代理，上云靠 Nginx 同源反代。这样以后换端口、换域名都不用改业务代码。

---

## 逐目录说明

### `index.html`

唯一的 HTML 入口，只提供一个 `<div id="app">` 和 `<script type="module" src="/src/main.ts">`。

**不放**：任何样式、任何文字内容。页面内容全部由 Vue 渲染。

### `src/main.ts`

8 行，装配顺序固定：

```ts
createApp(App).use(createPinia()).use(router).mount('#app')
```

必须先 `use(createPinia())` 再 `use(router)`。反过来，路由守卫里拿不到 store。

### `src/App.vue`

布局壳：顶部导航条 + `<RouterView />`。

导航栏现在是三个临时链接（首页 / 孩子端 / 家长端），M1 之后要换成按角色切换的正式入口，孩子端还应该是独立入口 `/kid`，因为孩子不该看到家长端的按钮。

**不放**：任何页面内容。`App.vue` 一胖，所有页面都会跟着重渲染。

### `src/router/`

| 文件 | 职责 |
|---|---|
| `index.ts` | 路由表 + `scrollBehavior` |

路由设计上有两个刻意的选择：

**孩子端和家长端分成两组父路由**（`/kid/*`、`/parent/*`），不是平铺的六个路径。这样以后加路由守卫时，可以按 `path.startsWith('/parent')` 统一拦一道，不用逐条配 `meta`。

**全部懒加载**（`() => import(...)`）。切到家长端不会加载孩子端的代码；两个端首屏各自只有几十 KB。

末尾的 `{ path: '/:pathMatch(.*)*', redirect: '/' }` 是兜底：输错地址不会白屏，会回到首页。

用 `createWebHistory()`（History 模式，地址栏没有 `#`）。**代价是服务端必须支持 fallback**：刷新 `/parent/dashboard` 时，服务器要返回 `index.html` 而不是 404。Vite dev server 自带，生产用 Nginx 时要加 `try_files $uri /index.html;`。

### `src/views/`

一个文件一页，按端分目录。

| 文件 | 职责 |
|---|---|
| `Home.vue` | 环境自检页。后端没起时是唯一能打开的地方 |
| `Login.vue` | 登录，成功后按 `?redirect=` 回跳 |
| `kid/Today.vue` | 今日 / 补做 / 待审核 / 已完成四区。分区口径在服务端 `bucket`，前端不自己算 |
| `kid/Task.vue` | 作业页：计时、拍照、写说明、提交、撤回。口算任务在这里只显示一个入口 |
| `kid/Calc.vue` | 口算一题一屏，回车跳下一题，交卷当场出分 |
| `parent/Dashboard.vue` | 总览四个数（待审核 / 还没交 / 已完成 / 错题待复习）+ 孩子档案 |
| `parent/Tasks.vue` | 布置、编辑、删除。可选题型：普通作业 / 口算 |
| `parent/Review.vue` | 审核：看照片、通过发星、退回写原因；**错题重做任务要顺手判「做对了 / 还是错」** |
| `parent/Mistakes.vue` | 错题本：录入、三档列表、复习进度、重做流水 |

`Home.vue` 值得看的是它的三段式模板：`v-if="loading"` / `v-else-if="error"` / `v-else-if="health"`。**三个状态都要有 UI**，不能只写成功分支 —— 后端没起时页面上要有"连不上后端"的明确提示和下一步命令，而不是一片空白。

两处刻意的页面划分：

**拍照不在列表页。** `Today.vue` 只负责导航，计时和拍照全在 `Task.vue`。因为「开始」才写 `started_at`，提交按钮放在列表上，计时就没有起点。

**口算不走 `Task.vue`。** 它是客观题，孩子一题一屏做、交卷当场判分，没有照片也没有待审核环节。`Today.vue` 用 `taskLink()` 按 `kind` 分流，后端用 `kind=calc` 的 `autograde` 边直接进 `done`。

**放**：模板、该页专属的 `scoped` 样式、调用 api。

**不放**：跨页复用的逻辑（进 `composables/`）、跨页复用的组件（进 `components/`）。

### `src/api/`

所有对后端的调用都在这里，页面里不出现 `axios`。

**`http.ts`** 是唯一实例：

```ts
const http = axios.create({
  baseURL: '/api/v1',
  timeout: 20000,
  withCredentials: true,
})
```

三个配置各有原因：

- `baseURL: '/api/v1'` —— 页面里只写 `/health`，版本号集中一处
- `withCredentials: true` —— M0 用不上，但 **M1 接 JWT 后必须靠它带 Cookie**。`<img>` 和 PDF 的 `<iframe>` 带不了 `Authorization` 头，只能走 Cookie，这是技术方案 v1.1 缺口 1 的结论。现在配好，将来不用回头改
- `timeout: 20000` —— 上传 40MB 教材要时间，默认的 0（不限时）会让失败请求一直挂着

响应拦截器做了两件事：**剥掉 `AxiosResponse` 外壳**，把 `res.data` 直接返回；把后端返回的 `detail` 提取成 `Error.message`，所以页面里 `catch` 到的是能直接展示的中文。

**`system.ts`** 是接口定义样板：

```ts
export const getHealth = () => http.get<unknown, Health>('/health')
```

注意**第二个泛型参数**才是返回类型。因为拦截器已经改变了返回值，写成 `http.get<Health>()` 会让 TS 认为返回的是 `AxiosResponse<Health>`，取 `res.db` 时类型报错。

**约定**：一个后端模块一个文件（`system.ts`、将来的 `task.ts`、`mistake.ts`），每个接口返回 `Promise<T>`，类型用 `interface` 写在这个文件顶部，不单独建 `types/` 目录 —— 前端类型跟着接口走，拆开反而要两头找。

### `src/stores/`

`session.ts`，Pinia 的 setup 写法：角色 + 当前孩子 id。

```ts
export type Role = 'kid' | 'parent'
const role = ref<Role>('kid')
const childId = ref<number | null>(null)
```

`childId` 现在还是 `null`，但**从第一天就留着**：数据模型上 `account` 和 `child` 是一对多，迟早要支持二孩，写死单孩子会返工。

M1 之后这个 store 还要装：登录态、token 刷新、账号昵称、孩子列表与切换。

**放**：跨页共享的少量状态。

**不放**：接口数据缓存。任务列表、错题列表都是页面自己的状态，放进 store 会导致"在 A 页改了、B 页还是旧数据"的经典问题。等真的需要共享时再抽，不要提前。

### `src/styles/`

`tokens.css` 是全局唯一样式文件，只做两件事：定义 CSS 变量、设全局重置与字体。

```
--ink / --ink-2 / --muted / --hint    文字四级
--line / --page / --card              边框与背景
--kid / --kid-soft / --star           品牌色与星星色
--ok / --warn / --bad                 状态色
--r-sm / --r-md / --r-lg              圆角
--sp-1 ~ --sp-5                       间距
```

**原则是先有 token 再写组件**。原型里同一批颜色出现了几十次，直接搬过来后期改配色要全局搜索替换；抽成变量后改一处即可。

组件样式一律用 `<style scoped>` 写在自己文件里，**不要往 `tokens.css` 里加组件样式**。这个文件只应该有变量和全局重置，一旦开始放 `.card { ... }`，它就会变成第二个全局样式表。

### `vite.config.ts`

```ts
server: {
  port: 5173,
  proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } },
}
```

代理是前后端分离能"看起来同源"的关键。`changeOrigin: true` 会把 Host 头改成目标地址，否则后端某些按 Host 判断的逻辑会出问题。

**改代理要重启 dev server**，热更新不生效。

### `tsconfig.json` / `src/env.d.ts`

`strict: true` 全开。`moduleResolution: "bundler"` 是 Vite 推荐的解析模式。

`env.d.ts` 里有一句 `declare module '*.vue'`，让 TS 认识 `.vue` 导入。**这是通配声明**，意味着写错路径也能通过类型检查 —— 见下面「踩过的坑」第一条。

---

## 尚未建立的目录

### `src/components/` —— M2 起引入

现在所有 UI 都写在页面里，因为页面之间还没出现重复结构。M2 之后会出现明显复用：

- 任务条目（孩子端今日列表 / 家长端布置列表 / 错题清单都是同一种卡片）
- 状态标签（todo / doing / submitted / done / rejected 五种色）
- 上传弹层（作业照片、错题照片、教材 PDF 三处都要）

判据：**同一个结构在第三个地方出现时**，抽到 `components/`。第二个地方出现时先复制，过早抽象比重复更难改。

命名直接用 `TaskCard.vue`、`StatusTag.vue`，不加 `Base`、`App` 之类前缀 —— 那是给组件库用的，业务项目不需要。

### `src/composables/` —— 按需引入

`useUpload()`（压缩 + 分片 + 进度）、`usePolling()` 这类跨页逻辑才放这里。现在没有，不建空目录。

---

## 新增一个页面的标准动作

以"孩子端错题本"为例（下面两个文件都还不存在，是示范命名）：

1. 建 `src/views/kid/Mistakes.vue`
2. `router/index.ts` 的 `/kid` 子路由里加一条，**路径写成 `../views/kid/Mistakes.vue`**（漏一级就白屏，见坑 1）
3. `src/api/mistake.ts` 定义接口函数和返回类型
4. 页面里 `onMounted` 拉数据，模板写 loading / error / 空列表 / 有数据四种状态
5. 有复用结构才抽 `components/`
6. `npm run build` 过一遍类型检查

**空状态必须有 UI**。孩子第一次进来错题本是空的，显示一片空白会让人以为页面坏了。

---

## 开发约定

1. **页面里不出现 `axios`**，一律走 `src/api/`
2. **不写后端地址**，只写 `/api/v1/...`
3. **组件样式用 `scoped`**，不往 `tokens.css` 加组件类
4. **颜色不用十六进制字面量**，用 `var(--xxx)`
5. **接口返回的 `Promise<T>` 要有 `interface`**，不写 `any`
6. **三种状态都要渲染**：loading / error / 数据
7. **路由懒加载**，新增页面照抄 `() => import(...)`

---

## 踩过的坑

| 现象 | 原因 | 解法 |
|---|---|---|
| 浏览器白屏，浮层写 `Failed to resolve import "./views/Home.vue"` | `router/index.ts` 在 `src/` 下，`./views` 解析成 `src/router/views`，少了一级 | 写 `../views/...` |
| 上面这个错 `vue-tsc` 查不出来 | `env.d.ts` 里 `*.vue` 是通配声明，任何路径都能匹配 | 只能靠 Vite 加载时发现；建议加一个校验相对 import 存在性的脚本 |
| WebStorm 里 `npm` 找不到 | GUI 启动不读 `~/.zshrc`，没有 Node 的 PATH | Settings → JavaScript Runtime 手动指定绝对路径 |
| 终端里 `npm` 也找不到 | Node 装在 `~/.workbuddy/binaries/` 里，没进 PATH | 已写入 `~/.zshrc`，用 `sort -V` 取最高版本 |
| `npm run dev` 起来是 5174 不是 5173 | 5173 已被另一个 Vite 占用（比如 `dev.sh` 也起了一个） | 只留一个；`dev.sh` 与 IDE 二选一 |
| `res.db` 报类型错误 | 拦截器剥了 `AxiosResponse`，泛型要写 `http.get<unknown, Health>` | 第二个泛型参数才是返回类型 |
| 生产环境刷新子路由 404 | History 模式需要服务端 fallback | Nginx 加 `try_files $uri /index.html;` |

---

## 前端进度

| 阶段 | 前端内容 | 状态 |
|---|---|---|
| M0 | 工程骨架、路由、请求层、设计 token、自检页 | 完成 |
| M1 | 登录页、孩子档案页、按角色切换入口 | 未开始 |
| M2 | 今日任务、布置导入、提交上传、审核退回 | 未开始 |
| M3 | 口算练习页、错题本、星星商店 | 未开始 |
| M4 | 教材管理、个人设置、周报 | 未开始 |
| M5 | AI 助手对话（SSE 流式）、拍照识别核对页 | 未开始 |
