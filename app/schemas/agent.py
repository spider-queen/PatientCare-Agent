
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AgentImageInput(BaseModel):
    image_url: Optional[str] = None
    image_base64: Optional[str] = None
    mime_type: str = "image/png"

    @model_validator(mode="after")
    def validate_source(self) -> "AgentImageInput":
        if not self.image_url and not self.image_base64:
            raise ValueError("image_url or image_base64 is required")
        return self


class AgentIdentityVerification(BaseModel):
    phone: Optional[str] = None
    id_number: Optional[str] = None

    @model_validator(mode="after")
    def validate_credential(self) -> "AgentIdentityVerification":
        if not self.phone and not self.id_number:
            raise ValueError("phone or id_number is required")
        return self


class AgentAccessContext(BaseModel):
    actor_role: str
    access_purpose: str
    operator_id: str = "demo-operator"
    tenant_id: str = "demo-tenant"
    is_demo_context: bool = False


class AgentQueryRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query: str
    patient_code: Optional[str] = None
    identity_verification: Optional[AgentIdentityVerification] = None
    images: List[AgentImageInput] = Field(default_factory=list)
    debug_planner: bool = False
    force_full_agent: bool = False


class AgentToolOutput(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    result: Dict[str, Any]


class AgentQueryResponse(BaseModel):
    answer: str
    tool_outputs: List[AgentToolOutput]
    intent: Optional[str] = None
    intent_confidence: Optional[float] = None
    route_type: Optional[str] = None
    route_reason: Optional[str] = None
    cache_hit: Optional[bool] = None
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    risk_level: Optional[str] = None
    recommended_action: Optional[str] = None
    runtime_metrics: Optional[Dict[str, Any]] = None
    planner_debug: Optional[Dict[str, Any]] = None
    run_id: Optional[str] = None
    memory_refresh_scheduled: Optional[bool] = None
    execution_trace: Optional[Dict[str, Any]] = None
