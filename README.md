# Note to WebNote - 自动化个人笔记发布系统

这是一个将本地 PDF 笔记库自动转化为现代化个人博客的完整解决方案。通过 Python 脚本将本地 `Note` 目录结构映射到 Web 页面，实现 **"Write Locally, Publish Globally"**（本地写作，全球发布）。

本系统包含两个核心部分：
1. **Automation Tool**: 智能同步脚本，处理文件映射和页面生成。
2. **WebNote**: 极简风格的静态展示前端（基于纯 HTML/CSS/JS）。

---

## 🚀 部署工作流

只需简单四步，即可将本地笔记发布到互联网：

### 1. 整理笔记 (Note)
在项目根目录的 `Note/` 文件夹中整理你的 PDF 文件。
- 支持创建多级子目录（如 `Note/计算机视觉/SLAM/`）。
- 同步工具会自动将其识别为一级分类（如 `计算机视觉`），并将子目录下的文件统一归类。

### 2. 执行同步 (Sync)
在根目录下运行 Python 脚本：
```powershell
python Publish.py
```
脚本将自动完成以下工作：
- **扁平化处理**：将深层目录下的 PDF 统一映射到对应的一级分类下。
- **上传 R2**：将 PDF 上传到 Cloudflare R2，不再把 PDF 发布副本提交到 GitHub。
- **生成页面**：为每个 PDF 生成独立的 HTML 阅读页面。
- **更新索引**：自动更新 `posts.json` 数据源。

### 3. 本地预览 (Preview)
进入 `WebNote/PatTianFang.github.io/` 目录，直接在浏览器打开 `index.html`，或者使用 VS Code 的 Live Server 预览效果。

### 4. 发布上线 (Deploy)
将 `WebNote/PatTianFang.github.io` 目录下的变更推送到 GitHub 仓库。
- 确保 Cloudflare Pages 已连接该 GitHub 仓库。
- 推送后，Cloudflare Pages 将自动部署你的静态博客。

---

## 🛠️ 自动化工具核心功能

同步脚本 (`sync_pdfs.py`) 是连接本地笔记与 Web 展示的桥梁：

1. **智能扁平化**：
   - 递归遍历 `Note` 下的所有子文件夹。
   - 自动将所有 PDF 文件同步到 Web 目录的对应一级分类下，忽略源路径的复杂深度，让 Web 端分类更清晰。
2. **双路径发布**：
   - Cloudflare R2：存放实体 PDF 文件。
   - `posts/`：存放自动生成的 HTML 包装页面。
3. **自动化生成**：
   - 基于模板 (`posts/demo/pdf-embed-demo.html`) 自动生成包含 PDF 嵌入代码的 HTML 文件。
   - 自动提取文件创建时间作为文章日期。
   - 自动更新 `data/posts.json` 数据索引，无需手动编辑配置。
4. **增量与权限优化**：
   - **增量更新**：仅同步变更文件，速度极快。
   - **权限保护**：使用 `shutil.copy` 结合手动时间戳同步，确保生成的文件不需要管理员权限即可删除。
5. **中文支持**：
   - 完美处理包含中文、空格等特殊字符的路径。

---

## 🌐 WebNote 前端特性

前端部分是一个追求极简与高性能的静态网页模板：

- **零依赖**：无 npm，无 Webpack，无外部框架。打开即运行。
- **动态渲染**：JS 读取 `data/posts.json` 自动渲染文章列表和分类过滤器。
- **PDF 优选**：内置 PDF 阅读器适配，适合学术论文和技术文档展示。
- **响应式设计**：完美适配桌面和移动端浏览器。

---

## 📂 项目目录结构

建议保持如下目录结构以确保工具正常运行：

```text
根目录/
├── Note/                  # [输入端] 本地 PDF 笔记库
│   ├── C Sharp/           # 一级分类 (将映射为博客分类)
│   │   └── ...            # 可以包含任意深度的子文件夹
│   └── 计算机视觉/
│       └── ...
├── WebNote/               # [输出端] Web 项目根目录
│   └── PatTianFang.github.io/
│       ├── data/posts.json        # 自动生成的文章索引
│       ├── posts/                 # 自动生成的 HTML 页面
│       └── index.html             # 博客首页
├── Publish.py             # 自动化同步脚本
└── README.md              # 本说明文档
```

## 🚀 部署 Cloudflare Pages + R2 详细步骤

### 1. 准备 Cloudflare R2

1. 注册 Cloudflare 账号并接入一个域名。
2. 创建 R2 bucket，建议命名为 `webnote-pdfs`。
3. 给该 bucket 绑定自定义域名，例如 `https://static.example.com`。
4. 安装并登录 Wrangler：
   ```powershell
   npm install -g wrangler
   wrangler login
   wrangler r2 bucket list
   ```

### 2. 设置发布环境变量

每次运行 `Publish.py` 前，在 PowerShell 中设置：

```powershell
$env:WEBNOTE_R2_BUCKET="webnote-pdfs"
$env:WEBNOTE_R2_PUBLIC_BASE_URL="https://static.example.com"
```

可选：如果需要覆盖默认缓存策略，可以设置：

```powershell
$env:WEBNOTE_R2_CACHE_CONTROL="public, max-age=31536000"
```

### 3. 生成并上传

```powershell
python Publish.py
```

脚本会把 PDF 上传到 R2，并生成引用 R2 URL 的文章页面。
生成的 PDF URL 会带有源文件修改时间版本号，源 PDF 更新后页面链接会随之变化，避免浏览器继续使用旧缓存。
脚本成功后会自动提交并推送 `WebNote/PatTianFang.github.io` 仓库，Cloudflare Pages 会根据这次 push 自动部署。

### 4. 部署 Cloudflare Pages

1. 在 Cloudflare Dashboard 进入 **Workers & Pages**。
2. 创建 Pages 项目并连接 GitHub 仓库 `PatTianFang/PatTianFang.github.io`。
3. 构建设置：
   - Framework preset: `None`
   - Build command: 留空
   - Build output directory: `/`
4. `Publish.py` 自动推送 `WebNote/PatTianFang.github.io` 仓库后，Cloudflare Pages 会自动部署。

## 🚀 原 GitHub Pages 部署步骤（旧方案）

如果仍想使用 GitHub Pages，可以参考以下旧流程；但大 PDF 不建议继续提交到 GitHub。

1. **准备仓库**：在 GitHub 上创建一个和GitHub账号同名的新公开仓库（例如名为 `PatTianFang.github.io`）。
2. **修改为Github名称**：将`PatTianFang.github.io`文件夹名称替换为刚刚创建的仓库名称。
   
3. **初始化 Git**：进入 `WebNote/PatTianFang.github.io/` 目录：
   ```powershell
   cd WebNote/PatTianFang.github.io/
   git init
   git add .
   git commit -m "Initial commit"
   ```
4. **推送到 GitHub**：
   ```powershell
   git remote add origin https://github.com/你的用户名/你的仓库名.git
   git branch -M main
   git push -u origin main
   ```
5. **开启 Pages**：
   - 在 GitHub 仓库页面，点击 **Settings**。
   - 在左侧菜单选择 **Pages**。
   - 在 **Build and deployment > Branch** 下，选择 `main` 分支和 `/ (root)` 目录，点击 **Save**。
   - 等待几分钟，你的博客将通过 `https://你的用户名.github.io/你的仓库名/` 访问。

## 📂 修改 WebNote 文件夹名称步骤

如果你想修改 `WebNote/PatTianFang.github.io` 这个文件夹的名称（例如改为 `WebNote/MyBlog`），请按以下步骤操作：

1. **手动重命名**：在文件资源管理器中直接将文件夹 `PatTianFang.github.io` 重命名为 `MyBlog`。
2. **修改脚本配置**：打开 `Publish.py`，修改以下三处路径配置：
   ```python
   # Publish.py 第 14, 23, 50, 51 行左右
   template_path = os.path.join('.', 'WebNote', 'MyBlog', 'posts', 'demo', 'pdf-embed-demo.html')
   json_path = os.path.join('.', 'WebNote', 'MyBlog', 'data', 'posts.json')
   posts_base_dir = os.path.join('.', 'WebNote', 'MyBlog', 'posts')
   pdfs_base_dir = os.path.join('.', 'WebNote', 'MyBlog', 'pdfs')
   ```
3. **重新运行**：执行 `python Publish.py` 确保路径正确映射。

## 🔧 环境要求

- **Python**: 3.6 或更高版本 (用于运行同步脚本)
- **Git**: (用于发布到 GitHub Pages)
- **OS**: Windows/macOS/Linux (已针对 Windows 环境优化)
