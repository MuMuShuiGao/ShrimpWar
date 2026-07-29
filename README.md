# ShrimpWar

自托管多智能体协作平台。

## 快速启动

```bash
# 1. 安装 Python 依赖
pip install -r requirements.txt

# 2. （可选）安装 Tailwind CSS 并编译
npm install
npm run css:build

# 3. 启动服务
python -m uvicorn app.main:app --reload

# 4. 打开浏览器
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
