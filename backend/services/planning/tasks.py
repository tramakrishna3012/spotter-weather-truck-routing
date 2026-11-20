"""Celery task definitions for asynchronous Spotter route planning."""

from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from apps.trips.models import Plan, PlanJob
from config.logging import reset_request_id, set_request_id

logger = logging.getLogger("spotter.planning.tasks")


@shared_task(
    bind=True,
    name="services.planning.tasks.execute_plan_job",
    max_retries=2,
    default_retry_delay=5,
)
def execute_plan_job(self, plan_id: str, request_id: str | None = None) -> str:
    """Execute a queued route plan inside a worker process with bounded retries."""
    from providers.ports import ProviderError
    from services.planning.orchestrator import PlanningOrchestrator

    token = set_request_id(request_id or f"task-{plan_id}")
    try:
        plan = Plan.objects.filter(id=plan_id).first()
        if plan is None:
            logger.warning("Plan not found for worker job", extra={"plan_id": plan_id})
            return "missing"

        if plan.status == Plan.Status.CANCELED:
            logger.info("Skipping canceled plan job", extra={"plan_id": plan_id})
            return str(Plan.Status.CANCELED)

        orchestrator = PlanningOrchestrator()
        updated = orchestrator.execute_plan(plan)
        return str(updated.status)
    except ProviderError as exc:
        if getattr(exc, "retryable", False) and self.request.retries < self.max_retries:
            logger.warning(
                "Retrying plan job after retryable provider error",
                extra={"plan_id": plan_id, "attempt": self.request.retries + 1},
            )
            raise self.retry(exc=exc, countdown=2 ** (self.request.retries + 1)) from exc

        now = timezone.now()
        Plan.objects.filter(id=plan_id).exclude(status=Plan.Status.CANCELED).update(
            status=Plan.Status.FAILED,
            error_code=getattr(exc, "code", "PROVIDER_UNAVAILABLE"),
            error_message="Upstream provider error prevented plan completion.",
            updated_at=now,
        )
        PlanJob.objects.filter(plan_id=plan_id).update(
            status=Plan.Status.FAILED,
            error_code=getattr(exc, "code", "PROVIDER_UNAVAILABLE"),
            completed_at=now,
        )
        return str(Plan.Status.FAILED)
    except Exception:
        logger.exception("Unexpected error while executing plan job", extra={"plan_id": plan_id})
        now = timezone.now()
        Plan.objects.filter(id=plan_id).exclude(status=Plan.Status.CANCELED).update(
            status=Plan.Status.FAILED,
            error_code="INTERNAL_PLANNING_ERROR",
            error_message="An internal error occurred while evaluating this trip.",
            updated_at=now,
        )
        PlanJob.objects.filter(plan_id=plan_id).update(
            status=Plan.Status.FAILED,
            error_code="INTERNAL_PLANNING_ERROR",
            completed_at=now,
        )
        raise
    finally:
        reset_request_id(token)
