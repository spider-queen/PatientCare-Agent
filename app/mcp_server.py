from typing import Optional

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "The MCP server requires the `mcp` package and Python 3.10+. "
        "Your current environment cannot import it."
    ) from exc

from app.db.session import SessionLocal
from app.services import mcp_tool_service


mcp = FastMCP("patient-agent-mcp-server")

@mcp.tool()
def verify_patient_identity(
    patient_code: str,
    phone: Optional[str] = None,
    id_number: Optional[str] = None,
) -> dict:
    """
    校验患者身份。
    可使用 patient_code + phone 或 patient_code + id_number 进行验证。
    """
    db = SessionLocal()
    try:
        return mcp_tool_service.verify_patient(
            db,
            patient_code=patient_code,
            phone=phone,
            id_number=id_number,
        )
    finally:
        db.close()


@mcp.tool()
def get_patient_profile(
    patient_id: Optional[int] = None,
    patient_code: Optional[str] = None,
) -> dict:
    """
    查询患者基础信息。
    patient_id 和 patient_code 二选一。
    """
    db = SessionLocal()
    try:
        return mcp_tool_service.get_patient_profile(
            db,
            patient_id=patient_id,
            patient_code=patient_code,
        )
    finally:
        db.close()


@mcp.tool()
def get_patient_medical_cases(
    patient_id: Optional[int] = None,
    patient_code: Optional[str] = None,
) -> dict:
    """
    查询患者病例信息。
    patient_id 和 patient_code 二选一。
    """
    db = SessionLocal()
    try:
        return mcp_tool_service.get_patient_medical_cases(
            db,
            patient_id=patient_id,
            patient_code=patient_code,
        )
    finally:
        db.close()

@mcp.tool()
def get_patient_visit_records(
    patient_id: Optional[int] = None,
    patient_code: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict:
    """
    查询患者就诊记录。
    patient_id 和 patient_code 二选一。
    如果只查最近一次记录，传 limit=1。
    """
    db = SessionLocal()
    try:
        return mcp_tool_service.get_patient_visit_records(
            db,
            patient_id=patient_id,
            patient_code=patient_code,
            limit=limit,
        )
    finally:
        db.close()


@mcp.tool()
def get_follow_up_plans(
    patient_id: Optional[int] = None,
    patient_code: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    """
    查询患者诊后随访计划。主链路使用 Function Tools / Tool Calling，
    该 MCP 入口仅作为可选适配层。
    """
    db = SessionLocal()
    try:
        return mcp_tool_service.get_follow_up_plans(
            db,
            patient_id=patient_id,
            patient_code=patient_code,
            status=status,
        )
    finally:
        db.close()


@mcp.tool()
def get_medication_reminders(
    patient_id: Optional[int] = None,
    patient_code: Optional[str] = None,
) -> dict:
    """
    查询患者用药提醒。访问私有数据前应先完成身份验权。
    """
    db = SessionLocal()
    try:
        return mcp_tool_service.get_medication_reminders(
            db,
            patient_id=patient_id,
            patient_code=patient_code,
        )
    finally:
        db.close()


@mcp.tool()
def assess_follow_up_risk(query: str) -> dict:
    """
    基于规则识别诊后随访风险提示，不替代医生诊断。
    """
    return mcp_tool_service.assess_follow_up_risk(query=query)


if __name__ == "__main__":
    mcp.run()
