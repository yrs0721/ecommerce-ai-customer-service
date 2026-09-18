# AI Ecommerce Customer Service

基于 Dify + FastAPI + MySQL + Docker 的 AI 智能电商客服系统。

## 项目性质

个人实践 / 求职项目。

本项目用于 AI 项目交付工程师 / FDE / AI 应用开发相关岗位的项目实践。

所有商品、用户、订单、物流和工单均为模拟数据。

本项目不接入真实支付、退款或物流系统，售后仅创建待审核工单。

## 业务场景

虚构一家数码电商，主要销售：

- 耳机
- 键盘
- 充电器

## 核心功能

- 商品咨询
- FAQ 问答
- 本人订单查询
- 模拟物流查询
- 售后预检查
- 售后工单创建
- 工单状态查询
- 异常兜底
- 权限校验

## 技术栈

- Dify Chatflow
- Dify Knowledge Base
- FastAPI
- MySQL
- SQLAlchemy
- Alembic
- pytest
- Docker Compose
- Nginx
- Git / GitHub

## 项目目标

实现一个可以：

- 演示
- 测试
- 部署
- 交接

的 AI 智能客服练习项目。

核心业务闭环：

商品咨询 → 查询本人订单 → 查询物流 → 售后预检查 → 确认草稿 → 创建工单 → 查询工单状态

## 当前进度

Stage 0 - Environment Setup