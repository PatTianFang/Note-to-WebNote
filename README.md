# Note to WebNote

把本地 `Note/` 中的 PDF 笔记发布成可访问的静态网站。PDF 文件上传到 Cloudflare R2，前端静态页面提交到 `PatTianFang.github.io` 仓库，避免把大 PDF 提交到 GitHub。

## 当前架构

- 笔记源：`Note/`
- 发布脚本：`Publish.py`
- 前端站点：`WebNote/PatTianFang.github.io/`
- PDF 存储：Cloudflare R2 bucket `webnote-pdfs`
- PDF 公共域名：`https://static.patfang.xyz`
- 网站域名：`https://www.patfang.xyz`

发布后的结构：

- HTML 页面：`WebNote/PatTianFang.github.io/posts/<Note 相对路径>.html`
- R2 对象：`pdfs/<Note 相对路径>.pdf`
- 索引数据：`WebNote/PatTianFang.github.io/data/posts.json`

PDF 移动或删除后，再次运行 `Publish.py` 会同步更新文章页、`posts.json`、本地 R2 manifest 和远端 R2 旧对象。

## 仓库分工

- `PatTianFang/Note-to-WebNote`：本仓库，保存发布脚本、说明文档、子仓库指针和项目级配置。
- `PatTianFang/PatTianFang.github.io`：WebNote 前端仓库，保存 HTML/CSS/JS/JSON，不保存 PDF。
- `PatTianFang/Note`：Note 源仓库，只提交 Markdown 和图片；PDF 可以留在本地用于发布，但不会提交到 Git。

`Publish.py` 成功运行后会依次处理并推送：

1. WebNote 仓库
2. Note 仓库
3. 根仓库

## 环境要求

- Python 3
- Git
- Node.js LTS
- Wrangler

首次配置 Wrangler：

```powershell
npm install -g wrangler
wrangler login
wrangler r2 bucket list
```

确认能看到 `webnote-pdfs` bucket。

## 发布流程

在根目录运行：

```powershell
$env:WEBNOTE_R2_BUCKET="webnote-pdfs"
$env:WEBNOTE_R2_PUBLIC_BASE_URL="https://static.patfang.xyz"
$env:WEBNOTE_WRANGLER_TIMEOUT_SECONDS="600"

python Publish.py
```

可选环境变量：

```powershell
$env:WEBNOTE_R2_CACHE_CONTROL="public, max-age=31536000"
```

脚本会执行：

- 扫描 `Note/` 下所有 PDF。
- 生成文章 HTML。
- 上传新增或变更 PDF 到 R2。
- 删除 manifest 中已经不再对应当前 Note PDF 的旧 R2 对象。
- 更新 `data/posts.json`。
- 清理 `posts/` 下空目录。
- 提交并推送 WebNote、Note、根仓库。

## 前端功能

WebNote 是纯 HTML/CSS/JS 静态站点，无构建步骤。

- 首页从 `data/posts.json` 渲染文章。
- 支持分类过滤。
- 支持搜索标题、分类、摘要和日期。
- 支持分页，每页 10 篇。
- 文章页使用自适应宽屏容器，桌面端 PDF 预览更宽，移动端自动收缩。
- PDF 通过 R2 公共 URL 嵌入，不依赖 GitHub 存储大文件。

## 目录结构

```text
.
├── Note/                         # 本地笔记源；根仓库忽略该目录
├── WebNote/
│   └── PatTianFang.github.io/    # 前端站点仓库
│       ├── css/
│       ├── data/posts.json
│       ├── js/
│       ├── posts/
│       ├── index.html
│       └── CNAME
├── Publish.py                    # 发布脚本
├── .webnote-r2-manifest.json     # 本地 R2 同步清单；不提交
└── README.md
```

## 验证

发布后检查：

```powershell
git status --short --branch
git -C WebNote\PatTianFang.github.io status --short --branch
git -C Note status --short --branch
```

访问：

- `https://www.patfang.xyz/`
- `https://www.patfang.xyz/data/posts.json`
- `https://static.patfang.xyz/pdfs/...pdf`

GitHub 仓库中不应出现新增 PDF 文件。
