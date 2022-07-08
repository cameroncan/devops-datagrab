import json
import logging
import os
import psycopg2
import psycopg2.extras
from devops_metrics_info import DevopsMetricsInfo, DeploymentInfo, DeployedTicket


class DevopsMetricsRepository:
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def connect(self) -> any:
        psycopg2.extras.register_uuid()
        connection = psycopg2.connect(
            user=os.getenv("database_username"),
            password=os.getenv("database_password"),
            host=os.getenv("database_host"),
            port=os.getenv("database_port"),
            database=os.getenv("database_name")
        )
        self.logger.info("Created connection with database")
        return connection

    def is_app_version_already_deployed(self, app_name: str, app_version: str) -> bool:
        version_check_sql = """SELECT 1 FROM deployment_info where app_name=%s and app_version=%s"""

        connection = self.connect()
        cursor = connection.cursor()

        cursor.execute(version_check_sql, (app_name, app_version,))
        return cursor.fetchone() is not None

    def insert_deployment_info(self, cursor: any, deployment_info: DeploymentInfo) -> None:
        deployment_info_sql = """INSERT INTO deployment_info
                            (id, app_name, app_version, deployed_instant, deployed_by_user_id)
                            VALUES(%s, %s, %s, %s, %s)"""
        self.logger.info("Inserting deployment info into DB")
        cursor.execute(deployment_info_sql, (deployment_info.id, deployment_info.app_name, deployment_info.app_version,
                                             deployment_info.deployed_instant, deployment_info.deployed_by_user_id,))

    def insert_deployed_ticket(self, cursor: any, deployed_ticket: DeployedTicket) -> None:
        deployed_ticket_sql = """INSERT INTO deployed_ticket
                            (id, deployment_id, app_name, ticket_id, ticket_type, caused_by, 
                            created_instant, merged_instant, merge_author, repositories_affected)
                            VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        self.logger.info("Inserting deployed ticket info into DB")
        cursor.execute(deployed_ticket_sql, (deployed_ticket.id, deployed_ticket.deployment_id,
                                             deployed_ticket.app_name, deployed_ticket.ticket_id,
                                             deployed_ticket.ticket_type, deployed_ticket.caused_by,
                                             deployed_ticket.created_instant, deployed_ticket.merged_instant,
                                             deployed_ticket.merge_author,
                                             json.dumps(deployed_ticket.repositories_affected),))

    def insert_devops_metrics_info(self, devops_metrics_info: DevopsMetricsInfo) -> None:
        connection = None
        try:
            connection = self.connect()
            cursor = connection.cursor()
            self.insert_deployment_info(cursor, devops_metrics_info.deployment_info)
            for deployed_ticket in devops_metrics_info.deployed_tickets:
                self.insert_deployed_ticket(cursor, deployed_ticket)
            connection.commit()
            cursor.close()
        except(Exception, psycopg2.DatabaseError) as error:
            self.logger.error("Error inserting devops metrics into the database. Error: {}".format(error))
            exit(20)
        finally:
            if connection is not None:
                connection.close()
