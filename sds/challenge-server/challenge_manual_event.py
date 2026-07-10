import asyncio

from acps_ca_challenge.api import publish_runtime_event


asyncio.run(
    publish_runtime_event(
        event_type="challenge.manual.verify",
        level="info",
        title="Challenge 手工事件验证",
        message="Challenge publish helper 手工验证。",
        aic="1.2.156.3088.0001.00001.ABCDEF.GHIJKL.1.MNOP",
        extra={"stage": "manual"},
    )
)
