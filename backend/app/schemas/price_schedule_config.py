from pydantic import BaseModel, Field, model_validator


class ScheduleConfigOut(BaseModel):
    job_key: str
    enabled: bool
    days: list[int]
    run_at_hour: int
    run_at_minute: int
    interval_minutes: int | None = None

    model_config = {"from_attributes": True}


class ScheduleConfigIn(BaseModel):
    job_key: str
    enabled: bool
    days: list[int] = Field(..., description="Weekday ints: 0=Mon … 6=Sun")
    run_at_hour: int = Field(..., ge=0, le=23)
    run_at_minute: int = Field(..., ge=0, le=59)
    interval_minutes: int | None = None

    @model_validator(mode="after")
    def days_required_when_enabled(self) -> "ScheduleConfigIn":
        if self.enabled and not self.days:
            raise ValueError("At least one day must be selected when the job is enabled")
        return self
