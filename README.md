# 三谋猜一猜

根据阵营、兵种、战法和赛季来猜橙将，也可以猜通用战法。答案只留在服务端，猜完或放弃才会揭晓。

四种模式：

- 经典：八次机会猜一名橙将
- 每日挑战：按上海时间每天 0 点换题，分入门、标准和全部三档
- 海龟汤：提问和点名共用 24 次，每次只回答一项
- 猜战法：按品质、类型、效果、赛季和发动率来猜

## 本地游玩

需要 Python 3.11 或更新版本。

```bash
python scripts/serve_guess.py
```

打开 http://127.0.0.1:8770/

默认监听所有网卡的 8770 端口。可以用环境变量改变：

```bash
HOST=127.0.0.1 PORT=8770 python scripts/serve_guess.py
```

## 公开部署

服务只使用 Python 标准库。平台会传入 `PORT` 时，保持 `HOST=0.0.0.0`。

Docker：

```bash
docker build -t sanmou-guess .
docker run --rm -p 8770:8770 sanmou-guess
```

Render 可以直接用仓库里的 `render.yaml` 创建免费 Web 服务。免费实例空闲一段时间后会休眠，下次打开大约要等一分钟。当天的题目按日期固定，进行中的对局和排行榜保存在 `data/runtime/`，实例重启后会清空。这个目录不要提交。

## 数据

武将和战法资料整理自公开页面，头像只用于局内辨认。更新本地题库：

```bash
python scripts/update_from_sgmdtx.py
python scripts/apply_wiki_troops.py
```

第二条会按已保存的兵种对照表修正阵营和兵种，需要本机有 Node.js。
