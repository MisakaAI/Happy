from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, Relationship, SQLModel


class EquipmentType(StrEnum):
    REFRIGERATOR = "冰箱"
    WASHER = "洗衣机"
    DRYER = "烘干机"
    AIR_CONDITIONER = "空调"
    OTHER = "其他"


# 货架类型
class ShelfType(SQLModel, table=True):
    __tablename__ = "wms_shelf_type"

    id: int | None = Field(default=None, primary_key=True)
    # 名称
    name: str = Field(max_length=100, nullable=False)


# 住宅
class Housing(SQLModel, table=True):
    __tablename__ = "wms_housing"

    id: int | None = Field(default=None, primary_key=True)
    # 名称
    name: str = Field(max_length=100, nullable=False)
    # 面积（平方米）
    area: float | None = Field(default=None, ge=0)
    # 地址
    address: str | None = Field(default=None, max_length=300)
    # 创建时间
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), nullable=False
    )

    # 一对多关联关系，并双向自动同步
    rooms: list[Room] = Relationship(back_populates="housing")


# 房间
class Room(SQLModel, table=True):
    __tablename__ = "wms_room"

    id: int | None = Field(default=None, primary_key=True)
    # 名称
    name: str = Field(max_length=100, nullable=False)
    # 面积（平方米）
    area: float | None = Field(default=None, ge=0)
    # 所属住宅
    housing_id: int = Field(foreign_key="wms_housing.id", nullable=False)
    # 创建时间
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), nullable=False
    )

    # 一对多关联关系，并双向自动同步
    housing: Housing | None = Relationship(back_populates="rooms")
    shelves: list[Shelf] = Relationship(back_populates="room")
    equipment: list[Equipment] = Relationship(back_populates="room")


# 货架
class Shelf(SQLModel, table=True):
    __tablename__ = "wms_shelf"

    id: int | None = Field(default=None, primary_key=True)
    # 名称
    name: str = Field(max_length=100, nullable=False)
    # 货架类型
    type: int = Field(default=0)
    # 所属房间
    room_id: int = Field(foreign_key="wms_room.id", nullable=False)
    # 创建时间
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), nullable=False
    )

    # 一对多关联关系，并双向自动同步
    room: Room | None = Relationship(back_populates="shelves")
    supplies: list[Supplies] = Relationship(back_populates="shelf")


# 补给品
class Supplies(SQLModel, table=True):
    __tablename__ = "wms_supplies"

    id: int | None = Field(default=None, primary_key=True)
    # 名称
    name: str = Field(max_length=100, nullable=False)
    # 数量
    quantity: int = Field(default=0, ge=0)
    # 单位
    unit: str | None = Field(default=None, max_length=20)
    # 所属货架
    shelf_id: int = Field(foreign_key="wms_shelf.id", nullable=False)
    # 创建时间
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), nullable=False
    )
    # 更新时间
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column_kwargs={"onupdate": lambda: datetime.now(UTC)},
        nullable=False,
    )

    shelf: Shelf | None = Relationship(back_populates="supplies")


# 设备
class Equipment(SQLModel, table=True):
    __tablename__ = "wms_equipment"

    id: int | None = Field(default=None, primary_key=True)
    # 名称
    name: str = Field(max_length=100, nullable=False)
    # 设备类型
    type: EquipmentType = Field(default=EquipmentType.OTHER, nullable=False)
    # 所属房间
    room_id: int = Field(foreign_key="wms_room.id", nullable=False)
    # 创建时间
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), nullable=False
    )

    room: Room | None = Relationship(back_populates="equipment")

    # 自引用：设备间连接（如冰箱 ↔ 冰柜）
    connections: list[EquipmentConnection] = Relationship(
        back_populates="equipment",
        sa_relationship_kwargs={"foreign_keys": "EquipmentConnection.equipment_id"},
    )
    connected_to: list[EquipmentConnection] = Relationship(
        back_populates="connected_equipment",
        sa_relationship_kwargs={
            "foreign_keys": "EquipmentConnection.connected_equipment_id"
        },
    )


# ---------- 设备连接（多对多中间表） ----------


class EquipmentConnection(SQLModel, table=True):
    __tablename__ = "wms_equipment_connection"

    id: int | None = Field(default=None, primary_key=True)
    # 设备ID
    equipment_id: int = Field(foreign_key="wms_equipment.id", nullable=False)
    # 连接的设备ID
    connected_equipment_id: int = Field(foreign_key="wms_equipment.id", nullable=False)
    # 连接描述
    description: str | None = Field(default=None, max_length=200)

    equipment: Equipment | None = Relationship(
        back_populates="connections",
        sa_relationship_kwargs={"foreign_keys": "EquipmentConnection.equipment_id"},
    )
    connected_equipment: Equipment | None = Relationship(
        back_populates="connected_to",
        sa_relationship_kwargs={
            "foreign_keys": "EquipmentConnection.connected_equipment_id"
        },
    )
