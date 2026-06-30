# Publish 工程结构

`Publish.py` 现在只保留命令入口，实际发布逻辑拆分在 `Publish/` 包中。

## 入口

- `../Publish.py`：薄入口，调用 `Publish.app.main()`。
- `app.py`：发布流程编排，保持原有执行顺序：
  1. 清理本地生成产物
  2. 同步记录页
  3. 同步 PDF 文章页
  4. 注入上一篇/下一篇导航
  5. 同步全站 footer
  6. 再次清理本地生成产物
  7. 提交并推送仓库

## 模块职责

- `config.py`：路径、环境变量名、远程仓库地址等常量。
- `logging_utils.py`：日志初始化。
- `cleanup.py`：本地生成产物和空目录清理。
- `r2.py`：Cloudflare R2 配置、上传、删除、远端对象校验。
- `manifest.py`：本地 R2 manifest 读写和源文件签名。
- `git_ops.py`：Git 仓库初始化、提交、推送。
- `paths.py`：站点相对路径、CSS 版本、回忆页链接路径。
- `html_utils.py`：HTML 转义、CSS 链接刷新、footer 生成与替换。
- `records.py`：旅行/生活记录页生成和记录图片同步。
- `pdf_posts.py`：Note PDF 扫描、R2 上传、文章 HTML 生成、`posts.json` 更新。
- `posts_index.py`：文章索引合并和失效文章清理。
- `page_nav.py`：收集 HTML 页面并注入上一篇/下一篇导航。
- `footers.py`：同步全站 HTML footer。

## 运行

在项目根目录运行：

```powershell
python Publish.py
```

需要发布环境变量：

```powershell
$env:WEBNOTE_R2_BUCKET="webnote-pdfs"
$env:WEBNOTE_R2_PUBLIC_BASE_URL="https://static.patfang.xyz"
```

可选：

```powershell
$env:WEBNOTE_WRANGLER_TIMEOUT_SECONDS="600"
$env:WEBNOTE_R2_CACHE_CONTROL="public, max-age=31536000"
```

## 维护约定

- 新功能优先放入对应领域模块，不再把逻辑堆回根目录 `Publish.py`。
- 涉及 HTML 通用外壳的修改放在 `html_utils.py`，并通过 `footers.py` 或 `page_nav.py` 批量同步。
- 涉及 R2 对象命名和上传删除的修改放在 `r2.py`。
- 涉及 Git 提交和推送的修改放在 `git_ops.py`。
