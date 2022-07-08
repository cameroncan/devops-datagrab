import json
import uuid
from datetime import datetime
from typing import List


class DeployedTicket:
    def __init__(self, deployment_id: uuid, app_name: str, ticket_id: str, ticket_type: str, caused_by: str,
                 created_instant: datetime, merged_instant: datetime, merge_author: str,
                 repositories_affected: List[str]) -> None:
        self.id = uuid.uuid4()
        self.deployment_id = deployment_id
        self.app_name = app_name
        self.ticket_id = ticket_id
        self.ticket_type = ticket_type
        self.caused_by = caused_by
        self.created_instant = created_instant
        self.merged_instant = merged_instant
        self.merge_author = merge_author
        self.repositories_affected: List[str] = repositories_affected

    def get_property_dict(self) -> dict:
        property_dict: dict = {
            'app_name': self.app_name,
            'ticket_id': self.ticket_id,
            'ticket_type': self.ticket_type,
            'caused_by': self.caused_by,
            'created_instant': str(self.created_instant),
            'merged_instant': str(self.merged_instant),
            'merge_author': self.merge_author,
            'repositories_affected': json.dumps(self.repositories_affected)
        }
        return property_dict


class DeploymentInfo:
    def __init__(self, app_name: str, app_version: str, deployed_instant: datetime, deployed_by_user_id: str) -> None:
        self.id: uuid = uuid.uuid4()
        self.app_name: str = app_name
        self.app_version: str = app_version
        self.deployed_instant: datetime = deployed_instant
        self.deployed_by_user_id: str = deployed_by_user_id

    def get_property_dict(self) -> dict:
        property_dict: dict = {
            'app_name': self.app_name,
            'app_version': self.app_version,
            'deployed_instant': str(self.deployed_instant),
            'deployed_by_user_id': self.deployed_by_user_id
        }
        return property_dict


class DevopsMetricsInfo:
    def __init__(self, deployment_info: DeploymentInfo, deployed_tickets: List[DeployedTicket]) -> None:
        self.deployment_info: DeploymentInfo = deployment_info
        self.deployed_tickets: List[DeployedTicket] = deployed_tickets

    def to_pretty_str(self) -> str:
        list_of_dicts = [deployed_ticket.get_property_dict() for deployed_ticket in self.deployed_tickets]
        string_dict = {
            "DeployedTickets": list_of_dicts,
            "DeployedInfo": self.deployment_info.get_property_dict()
        }
        return json.dumps(string_dict)
