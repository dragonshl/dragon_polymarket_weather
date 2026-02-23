# 总控龙宝交易系统 (DragonMax Trading System)

## 项目简介

全自动加密货币量化交易系统，支持多策略融合和机器学习优化。

## 系统架构

```
├── trading_system.py    # 主交易系统代码
├── memory/             # 文档和日志
│   ├── CODE_DOCS.md   # 代码说明文档
│   ├── AUDIT_REPORT.md # 审计报告
│   └── GROWTH_PLAN.md # 成长计划
└── team/              # 团队配置
```

## 主要功能

- 多策略融合 (订单流、RSI、动量、MACD、布林带)
- 机器学习增强
- 风险管理 (止损、止盈、最大回撤)
- 多币种配置

## 配置的交易对

| 币种 | 仓位 | 杠杆 |
|------|------|------|
| BTC | 10% | 5x |
| ETH | 9% | 5x |
| XRP | 6% | 4x |
| SOL | 5% | 4x |
| BNB | 5% | 4x |
| ADA | 3% | 3x |

## 目标

- 年化收益: >60%
- 最大回撤: <10%

## 使用方法

```bash
python trading_system.py
```

## 分支说明

- `master` - 生产版本
- `develop` - 开发版本
- `feature/*` - 功能分支

## 版本

v1.2 - ML增强版 (2026-02-23)
