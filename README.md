# DolphinDB Backtest App (V1)

该子项目对齐 `DolphinDB/gygg_sample` 的核心工作流：
- 创建选股因子
- 回测参数配置
- 回测分析（指标 + 收益曲线 + 历史交易明细）
- 智能模型（规则推荐 + 受限对话补丁）

## 版本说明

### V1.0.1（2026-03-16）

本次版本围绕“量化研究员真实使用体验”做了一轮较完整的增强，重点更新如下：

- 新增买入条件和卖出条件分离配置。原先基本面因子、技术面因子默认都作为买入条件，现在前端支持分别配置买入条件和卖出条件；如果用户未设置卖出条件，系统继续沿用原有默认卖出逻辑，兼容旧策略。
- 增强语义策略输入。支持从自然语言中自动识别买入信号、卖出信号、持有周期、基准设置，并自动勾选对应因子、回填阈值和条件参数，减少人工逐项选择。
- 优化语义策略输入默认示例。默认示例已调整为更贴近日常研究使用的表达方式，方便直接修改后发起回测。
- 因子页新增 AI 生成推荐策略。系统会基于现有回测任务结果总结当前策略表现，并生成两类语义策略建议：一类用于增强已有较优思路，另一类用于尝试不同风格的策略方向。
- 回测任务页新增配置展示能力。任务详情页现在可以查看该次回测提交时的策略设置、买卖因子、参数快照和提交到 DolphinDB 的代码，便于复盘和团队沟通。
- 回测任务页支持代码折叠与一键复制。提交到 DolphinDB 的代码分块默认收起，展开后可一键复制整段代码。
- 优化任务结果可视化。任务页图表支持展示净值、基准、超额收益和回撤，并采用共用时间轴的主图/子图布局；同时支持按策略涉及的技术指标动态叠加展示，便于观察信号和净值表现的关系。
- 优化关键指标文案展示。总收益、年化收益、最大回撤等指标已明确百分比含义，降低阅读歧义。
- 优化任务命名。回测任务不再统一显示为 `combo_01`，而是根据买卖因子和策略规则自动生成更便于识别的策略名称，方便研究员在任务列表中快速定位。
- 新增单个任务删除功能。支持在任务列表中删除无效或无参考价值的回测任务；删除后的任务不会再参与 AI 推荐策略的汇总分析。
- 优化任务页布局与交互。左侧任务列表与右侧详情区对齐方式、折叠结构、按钮位置、滚动行为等均做了整理，减少横向滚动和重复操作，整体更适合连续查看多个任务。

## 目录

- `backend`: FastAPI 服务
- `frontend`: React + Vite 前端

## 本机启动

### 1. 启动后端

```powershell
cd <project_root>
.\start_backend.ps1
```

后端默认地址：`http://127.0.0.1:8000`

### 2. 启动前端

```powershell
cd <project_root>
.\start_frontend.ps1
```

前端默认地址：`http://127.0.0.1:5173`

## 一键启停 / 重启

```powershell
cd <project_root>
.\start_services.ps1
```

```powershell
cd <project_root>
.\stop_services.ps1
```

```powershell
cd <project_root>
.\restart_services.ps1
```

说明：
- `start_services.ps1` 会在后台拉起后端和前端，并等待健康检查通过。
- `stop_services.ps1` 会根据端口（8000/5173）和 PID 文件停止服务。
- `restart_services.ps1` 会先停后起。

## 默认 DolphinDB 配置

- Host: `183.134.101.135`
- Port: `8030`
- User: `admin`
- Password: `123456`

后端会自动探测 data node（优先可执行 `loadTable` 的节点，例如 `8032`）。

## API

- `GET /api/dolphindb/config/ddb`
- `POST /api/dolphindb/config/ddb`
- `GET /api/dolphindb/meta/templates`
- `GET /api/dolphindb/meta/factors`
- `POST /api/dolphindb/backtests/run`
- `GET /api/dolphindb/backtests/{run_id}`
- `DELETE /api/dolphindb/backtests/{run_id}`
- `GET /api/dolphindb/backtests/{run_id}/equity`
- `GET /api/dolphindb/backtests/{run_id}/trades`
- `POST /api/dolphindb/ai/recommend`
- `POST /api/dolphindb/ai/chat`
