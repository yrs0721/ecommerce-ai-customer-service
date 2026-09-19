"""Import orders atomically. Run from the project root with python -m scripts.import_order_tracking PATH."""

import argparse
import hashlib
from datetime import datetime
from decimal import Decimal, InvalidOperation

import openpyxl
from sqlalchemy import inspect, select

from app.config import settings
from app.db import SessionLocal, engine
from app.models import Order, Shipment, User


HEADERS = {
    "order_id", "order_time", "product_name", "quantity", "total_amount",
    "order_status", "receiver_name", "receiver_phone", "receiver_address",
    "express_company", "tracking_number", "logistics_status",
}


def read_orders(path):
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=False)
    try:
        records = workbook.active.iter_rows()
        headers = [cell.value for cell in next(records, [])]
        if len(headers) != len(set(headers)) or set(headers) not in (HEADERS, HEADERS | {"index"}):
            raise ValueError("Excel headers must match the required fields, with optional index")
        result, seen = [], set()
        for line, cells in enumerate(records, 2):
            source = dict(zip(headers, cells))
            source.pop("index", None)
            if all(cell.value in (None, "") for cell in source.values()):
                continue
            if any(cell.data_type == "f" for cell in source.values()):
                raise ValueError(f"Row {line}: formulas are not supported")
            raw = {key: cell.value for key, cell in source.items()}

            def field(key, limit, optional=False):
                value = "" if raw[key] is None else str(raw[key]).strip()
                if (not value and not optional) or len(value) > limit:
                    raise ValueError(f"Row {line}: invalid {key}")
                return value or None

            try:
                quantity = Decimal(str(raw["quantity"]))
                amount = Decimal(str(raw["total_amount"]))
                if not quantity.is_finite() or quantity != quantity.to_integral_value() or not 0 < quantity <= 2147483647:
                    raise ValueError("quantity must be a positive integer")
                if not amount.is_finite() or not 0 <= amount < Decimal("100000000") or amount != amount.quantize(Decimal("0.01")):
                    raise ValueError("total_amount must fit DECIMAL(10,2)")
                created_at = raw["order_time"]
                if not isinstance(created_at, datetime):
                    created_at = datetime.strptime(str(created_at), "%Y-%m-%d %H:%M:%S")
                if created_at.microsecond or created_at.tzinfo or created_at.year < 1000:
                    raise ValueError("order_time must be a MySQL DATETIME in whole seconds")
            except (ValueError, InvalidOperation) as exc:
                raise ValueError(f"Row {line}: invalid quantity, amount or order_time: {exc}") from exc
            order = dict(
                order_no=field("order_id", 50), created_at=created_at,
                product_name=field("product_name", 200), quantity=int(quantity),
                total_amount=amount, status=field("order_status", 20),
                receiver_name=field("receiver_name", 50),
                receiver_phone=field("receiver_phone", 20),
                receiver_address=field("receiver_address", 255),
            )
            shipment = dict(
                carrier=field("express_company", 50, True),
                tracking_no=field("tracking_number", 100, True),
                status=field("logistics_status", 50, True),
            )
            if shipment["carrier"] is None and shipment["tracking_no"] is None:
                if shipment["status"] not in (None, "未发货"):
                    raise ValueError(f"Row {line}: missing shipping details conflict with logistics status")
                shipment["status"] = "未发货"
            elif shipment["carrier"] is None or shipment["tracking_no"] is None or shipment["status"] is None:
                raise ValueError(f"Row {line}: incomplete shipping details")
            if order["order_no"] in seen:
                raise ValueError(f"Row {line}: duplicate order_id in Excel")
            seen.add(order["order_no"])
            result.append((order, shipment))
        return result
    finally:
        workbook.close()


def check_schema():
    """Fail before writes when the database lacks required fields or constraints."""
    inspector = inspect(engine)
    for model, unique in ((User, "username"), (Order, "order_no"), (Shipment, "order_id")):
        table = model.__table__
        columns = {c["name"]: c for c in inspector.get_columns(table.name)}
        missing = set(table.columns.keys()) - columns.keys()
        if missing:
            raise ValueError(f"{table.name}: missing columns {sorted(missing)}; repair schema first")
        constraints = inspector.get_unique_constraints(table.name)
        if not any(c["column_names"] == [unique] for c in constraints):
            raise ValueError(f"{table.name}: missing unique constraint on {unique}")
        if inspector.get_table_options(table.name).get("mysql_engine", "").lower() != "innodb":
            raise ValueError(f"{table.name}: InnoDB is required for transaction rollback")
    for column in ("carrier", "tracking_no"):
        if not columns[column]["nullable"]:
            raise ValueError(f"shipments.{column} must allow NULL")


def import_orders(rows):
    check_schema()
    counts = dict(valid_orders=len(rows), users=0, orders=0, shipments=0, skipped=0)
    with SessionLocal.begin() as session:
        for order_data, shipment_data in rows:
            phone = order_data["receiver_phone"]
            user = session.scalar(select(User).where(User.username == phone))
            order = session.scalar(select(Order).where(Order.order_no == order_data["order_no"]))
            if user is not None and (user.username != phone or user.role != "customer"):
                raise ValueError(f"User identity/role conflict for order {order_data['order_no']}")
            if order is not None:
                shipment = session.scalar(select(Shipment).where(Shipment.order_id == order.id))
                if (user is None or order.user_id != user.id
                        or any(getattr(order, key) != value for key, value in order_data.items())
                        or shipment is None
                        or any(getattr(shipment, key) != value for key, value in shipment_data.items())):
                    raise ValueError(f"Conflicting existing order {order_data['order_no']}; entire import rolled back")
                counts["skipped"] += 1
                continue
            if user is None:
                # Disabled marker, not a usable password verifier. Login must reject this prefix.
                placeholder = "!disabled$sha256$" + hashlib.sha256(("excel-customer:" + phone).encode()).hexdigest()
                user = User(username=phone, role="customer", password_hash=placeholder)
                session.add(user)
                session.flush()
                counts["users"] += 1
            order = Order(user_id=user.id, **order_data)
            session.add(order)
            session.flush()
            session.add(Shipment(order_id=order.id, **shipment_data))
            session.flush()
            counts["orders"] += 1
            counts["shipments"] += 1
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook")
    args = parser.parse_args()
    try:
        counts = import_orders(read_orders(args.workbook))
    except Exception as exc:
        # Avoid printing connection URLs or SQL parameters containing customer data.
        message = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        parser.exit(1, f"Import failed; no import changes committed: {message}\n")
    print(f"Database: {settings.db_name}; {counts}")


if __name__ == "__main__":
    main()
