"""The ConnectionManager:1 service. We're a source-only, connection-less
HTTP media server (like every simple DLNA MediaServer), so this is mostly
declaring "here's what I can serve" and answering the two required queries
with fixed, single-connection values -- there's no real connection
lifecycle to track."""

import xml.etree.ElementTree as ET

from async_upnp_client.const import ServiceInfo
from async_upnp_client.server import UpnpServerService, callable_action, create_state_var

from orvchestra.dlna.protocol_info import protocol_info

_SOURCE_PROTOCOL_INFO = ",".join(protocol_info(codec) for codec in ("FLAC", "MP3", "WAV", "AAC", "ALAC"))


class ConnectionManagerService(UpnpServerService):
    SERVICE_DEFINITION = ServiceInfo(
        service_id="urn:upnp-org:serviceId:ConnectionManager",
        service_type="urn:schemas-upnp-org:service:ConnectionManager:1",
        control_url="/upnp/connection_manager/control",
        event_sub_url="/upnp/connection_manager/event",
        scpd_url="/upnp/connection_manager/scpd.xml",
        xml=ET.Element("service"),
    )
    STATE_VARIABLE_DEFINITIONS = {
        "SourceProtocolInfo": create_state_var("string", default=_SOURCE_PROTOCOL_INFO),
        "SinkProtocolInfo": create_state_var("string", default=""),
        "CurrentConnectionIDs": create_state_var("string", default="0"),
        "A_ARG_TYPE_ConnectionStatus": create_state_var("string", default="OK"),
        "A_ARG_TYPE_ConnectionManager": create_state_var("string"),
        "A_ARG_TYPE_Direction": create_state_var("string", allowed=["Input", "Output"]),
        "A_ARG_TYPE_ProtocolInfo": create_state_var("string"),
        "A_ARG_TYPE_ConnectionID": create_state_var("i4"),
        "A_ARG_TYPE_AVTransportID": create_state_var("i4"),
        "A_ARG_TYPE_RcsID": create_state_var("i4"),
    }

    @callable_action(
        "GetProtocolInfo", in_args={}, out_args={"Source": "SourceProtocolInfo", "Sink": "SinkProtocolInfo"}
    )
    async def get_protocol_info(self) -> dict:
        return {"Source": _SOURCE_PROTOCOL_INFO, "Sink": ""}

    @callable_action(
        "GetCurrentConnectionIDs", in_args={}, out_args={"ConnectionIDs": "CurrentConnectionIDs"}
    )
    async def get_current_connection_ids(self) -> dict:
        return {"ConnectionIDs": "0"}

    @callable_action(
        "GetCurrentConnectionInfo",
        in_args={"ConnectionID": "A_ARG_TYPE_ConnectionID"},
        out_args={
            "RcsID": "A_ARG_TYPE_RcsID",
            "AVTransportID": "A_ARG_TYPE_AVTransportID",
            "ProtocolInfo": "A_ARG_TYPE_ProtocolInfo",
            "PeerConnectionManager": "A_ARG_TYPE_ConnectionManager",
            "PeerConnectionID": "A_ARG_TYPE_ConnectionID",
            "Direction": "A_ARG_TYPE_Direction",
            "Status": "A_ARG_TYPE_ConnectionStatus",
        },
    )
    async def get_current_connection_info(self, ConnectionID: int) -> dict:
        return {
            "RcsID": -1,
            "AVTransportID": -1,
            "ProtocolInfo": "",
            "PeerConnectionManager": "",
            "PeerConnectionID": -1,
            "Direction": "Output",
            "Status": "OK",
        }
