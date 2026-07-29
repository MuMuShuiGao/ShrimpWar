# ShrimpWar

自托管多智能体协作平台。

## 快速启动

```bash
# 1. 安装 uv（如已安装跳过）
pip install uv

# 2. 创建虚拟环境 + 安装依赖（一次性）
uv venv
uv pip install -r requirements.txt

# 3. （可选）安装 Tailwind CSS 并编译
npm install
npm run css:build

# 4. 启动服务
uv run uvicorn app.main:app --reload

# 5. 打开浏览器
# http://localhost:8000 → 自动跳转到 Agent 列表页
```

## 项目结构

```
app/
├── main.py              # FastAPI 入口
├── db.py                # SQLite 初始化
├── agents/              # Agent CRUD + 页面路由
├── runner/              # asyncio 子进程管理
├── workspace/           # 工作区文件操作
├── templates/           # Jinja2 模板
└── static/              # 静态资源
```
