"""F2: the 'break something' panel. Only available while the simulator is the device source."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.models import DeviceSnapshot
from app.devices.simulator import Simulator

router = APIRouter(prefix="/api")


class TriggerIn(BaseModel):
    scenario: Literal["washer_e3", "washer_done", "ac_spike", "dryer_done", "reset"]


def _simulator(request: Request) -> Simulator:
    simulator = request.app.state.ctx.simulator
    if simulator is None:
        raise HTTPException(409, "The simulator is off because real SmartThings devices are connected.")
    return simulator


@router.get("/devices", response_model=list[DeviceSnapshot])
async def devices(request: Request) -> list[DeviceSnapshot]:
    return request.app.state.ctx.store.all()


@router.post("/sim/trigger")
async def trigger(body: TriggerIn, request: Request) -> dict[str, str]:
    await _simulator(request).trigger(body.scenario)
    return {"scenario": body.scenario}


@router.post("/sim/reset")
async def reset(request: Request) -> dict[str, str]:
    await _simulator(request).trigger("reset")
    return {"scenario": "reset"}
