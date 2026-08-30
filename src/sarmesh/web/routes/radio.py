"""The node plugged into this machine, rather than the mesh around it.

/api/nodes answers "what is out there". This answers "what am I transmitting
with", which is what an operator checks when the map has gone quiet and they
need to know whether the problem is the radio or the search.
"""

from fastapi import APIRouter, HTTPException

from sarmesh.transports.meshtastic import RadioUnavailable
from sarmesh.web.dependencies import Radio
from sarmesh.web.schemas import RadioInfoOut

router = APIRouter(prefix="/api/radio", tags=["radio"])


# Deliberately sync: the radio calls block, and a sync handler runs in the
# threadpool instead of stalling the event loop that serves every other route.
@router.get("")
def radio_info(radio: Radio) -> RadioInfoOut:
    try:
        info = radio.node_info()
    except RadioUnavailable as error:
        # The interface went away between the dependency resolving and this
        # call -- a shutdown, or a USB cable pulled mid-request.
        raise HTTPException(503, str(error)) from error

    return RadioInfoOut.model_validate(info)
