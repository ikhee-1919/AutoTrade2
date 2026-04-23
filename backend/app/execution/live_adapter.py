from app.execution.base import BaseExecutionAdapter, ExecutionResult, OrderRequest


class UpbitLiveExecutionAdapter(BaseExecutionAdapter):
    """Placeholder for future live execution integration."""

    def submit_order(self, order: OrderRequest) -> ExecutionResult:
        # TODO: Implement real Upbit API order submission in a future phase.
        return ExecutionResult(
            accepted=False,
            message="Live execution is not enabled in the current project phase.",
            external_order_id=None,
        )
