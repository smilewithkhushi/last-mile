from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class DeliveryStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"        # 3+ drivers confirmed, recent
    MEDIUM = "MEDIUM"    # 2 confirmations or older
    LOW = "LOW"          # 1 report, unverified
    COLD_START = "COLD_START"  # no history, similarity fallback


class DeliveryNoteCreate(BaseModel):
    address_id: str
    address_text: str
    driver_id: str
    driver_name: str
    status: DeliveryStatus
    note_text: str
    timestamp: Optional[datetime] = None  # defaults to now; seed data can backdate


class DeliveryNote(DeliveryNoteCreate):
    id: int
    timestamp: datetime


class BriefingResponse(BaseModel):
    address_id: str
    address_text: str
    briefing: str
    confidence: ConfidenceLevel
    total_visits: int
    failed_visits: int
    last_visit: Optional[datetime]
    key_facts: list[str]
    is_stale: bool = False


class AddressDashboardEntry(BaseModel):
    address_id: str
    address_text: str
    total_deliveries: int
    failed_deliveries: int
    failure_rate: float
    cost_at_risk: float       # failed attempts × cost_per_failure
    cost_avoided: float       # estimated savings from memory
    has_memory: bool
    confidence: ConfidenceLevel
    last_delivery: Optional[datetime]
    conflicts_detected: int


class DashboardResponse(BaseModel):
    total_addresses: int
    total_deliveries: int
    total_failed: int
    overall_failure_rate: float
    total_cost_avoided: float
    addresses: list[AddressDashboardEntry]


class SeedResponse(BaseModel):
    message: str
    notes_ingested: int
    addresses_seeded: int


class ForgetResponse(BaseModel):
    address_id: str
    message: str
    notes_purged: int
