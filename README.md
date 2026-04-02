# 😊 HAPPY

> **基于 Python 的家庭资产管理平台（Home Asset Platform）**

HAPPY 是一个轻量级的 **家庭版 ERP（Enterprise Resource Planning）系统**，用于帮助个人和家庭以结构化、系统化的方式管理资产、维护记录等信息。

---

## ✨ 功能特性

### 🏠 资产管理

- [ ] 管理家庭资产（家电、衣物、工具等）
- [ ] 记录品牌、型号、购买时间、保修期、售后信息
- [ ] 支持资产与位置绑定（房间 → 柜子 → 层级）

### 🗂 空间管理

- [ ] 支持层级结构：房子 → 房间 → 区域 → 位置
- [ ] 快速定位物品存放位置

### 🔧 维护管理

- [ ] 记录维护历史（如空调清洗、热水器更换镁棒）
- [ ] 支持周期性维护计划
- [ ] 记录费用及服务人员

### 💰 财务集成

- [ ] 支持从外部记账 App 导入 CSV 数据
- [ ] 将消费与资产/维护记录关联
- [ ] 分析单个资产的生命周期成本

### 👨‍🔧 联系人管理

- [ ] 管理维修师傅等服务人员
- [ ] 关联维护记录

### 🔔 可扩展集成

- [ ] 支持日历同步（CalDAV，如 Nextcloud）
- [ ] 支持任务提醒（定期维护）

---

## 🚀 技术栈

- 后端：Python（FastAPI）
- 数据库：PostgreSQL
- 前端：Vue

---

## 📦 项目结构

```txt
Happy/
├── backend/
│   ├── api/
│   ├── models/
│   ├── services/
│   └── main.py
├── frontend/
├── docs/
└── README.md
```

---

## 📈 未来规划

- IoT 接入
- AI 助手集成
- 智能决策

---

## 📝 开源协议

[DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE](LICENSE)
