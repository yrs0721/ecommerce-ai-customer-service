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

## 订单物流 Excel 导入（MVP）

在项目根目录激活虚拟环境，确认 `.env` 的数据库配置后执行：

```powershell
python -m scripts.import_order_tracking data/raw/order_tracking_table.xlsx
```

依赖 `openpyxl` 和项目现有 SQLAlchemy/PyMySQL/pydantic-settings。
脚本读取首个工作表，校验业务表头，允许并忽略可选的 `index` 列。
手机号作为模拟 customer 的唯一 username；密码字段使用不可用于登录的
`!disabled$sha256$` 占位标记，后续认证必须拒绝该标记，设置正式密码后才能登录。
收货人姓名保存在订单上。金额使用 Decimal，未发货物流的承运商和单号保存为 NULL。

全部业务写入使用一个事务。已有订单的全部导入字段、所属用户和物流均一致时跳过；
存在冲突或缺失物流时整批回滚，不更新已有订单。Excel 内重复订单号直接报错。
脚本不会自动建表或修改表结构。新环境可运行 `python -m scripts.create_tables`；
已有表不会被 create_all 自动升级，应先核对结构。

本次本地数据库的 orders 原先缺少五列，已在确认该表为空后执行以下增量修复，
其他环境请先检查缺失列和已有数据，不要重复执行：

```sql
ALTER TABLE orders
  ADD COLUMN product_name VARCHAR(200) NOT NULL,
  ADD COLUMN quantity INT NOT NULL,
  ADD COLUMN receiver_name VARCHAR(50) NOT NULL,
  ADD COLUMN receiver_phone VARCHAR(20) NOT NULL,
  ADD COLUMN receiver_address VARCHAR(255) NOT NULL;
```

验证数量和随机已发货订单关联：

```sql
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM orders;
SELECT COUNT(*) FROM shipments;

SELECT u.id AS user_id, o.order_no, o.user_id AS order_user_id,
       o.id AS order_id, s.order_id AS shipment_order_id,
       s.carrier, s.tracking_no, s.status
FROM users u
JOIN orders o ON o.user_id = u.id
JOIN shipments s ON s.order_id = o.id
WHERE s.tracking_no IS NOT NULL
ORDER BY RAND()
LIMIT 1;
```

现有 orders.user_id 外键及 shipments.order_id 唯一约束支持用户归属和一对一物流。
后续 FastAPI 订单查询必须同时限制订单号和**服务端认证获得的**用户 ID：

```python
select(Order).where(
    Order.order_no == order_no,
    Order.user_id == current_user.id,
)
```

数据库结构本身不会自动实现接口鉴权，不得使用客户端传入的 user_id 替代认证用户。
