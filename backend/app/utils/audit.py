"""
SPT Hospital HRMS — Audit Log Utility
Helper function to record audit events.
"""
import json
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


async def log_audit(
    db: AsyncSession,
    user_id: Optional[int],
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    description: str = "",
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """
    Record an audit log entry.

    Args:
        db: Database session
        user_id: ID of the user performing the action
        action: Action code (e.g., "CREATE", "UPDATE", "DELETE", "IMPORT", "FINALIZE")
        entity_type: Type of entity affected (e.g., "Employee", "Attendance", "Payroll")
        entity_id: ID of the affected entity
        description: Human-readable description of the action
        old_value: JSON string of old values (for updates)
        new_value: JSON string of new values
        ip_address: Client IP if available
        user_agent: Client user agent if available
    """
    try:
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(log_entry)
        # Do NOT commit here — let the calling function handle transaction
    except Exception as e:
        # Never let audit log failure break the main operation
        logger.error(f"Failed to write audit log: {e}", exc_info=True)
