import argparse
import logging
from dotenv import load_dotenv
from datetime import datetime
from devops_metrics_info import DevopsMetricsInfo
from devops_metrics_repository import DevopsMetricsRepository
from devops_metrics_service import DevopsMetricsService


def main(logger: logging.Logger, project_name: str, project_version: str, deployed_instant: datetime,
         deployed_by_user_id: str) -> None:
    load_dotenv()
    metrics_repo: DevopsMetricsRepository = DevopsMetricsRepository(logger)
    metrics_service: DevopsMetricsService = DevopsMetricsService("INFO")

    # Adjust app naming from rundeck to match git repo naming
    project_name = rename_project_if_needed(project_name)

    # Check to see if this is a new deploy
    is_already_deployed: bool = metrics_repo.is_app_version_already_deployed(project_name, project_version)
    if not is_already_deployed:
        # Get the metrics info
        metrics_info: DevopsMetricsInfo = metrics_service.get_devops_metrics_information(project_name, project_version,
                                                                                         deployed_instant,
                                                                                         deployed_by_user_id)
        logger.info("Finished gathering metrics, now inserting them into the DB. metrics_info={}"
                    .format(metrics_info.to_pretty_str()))

        # Save the metrics in the DB
        metrics_repo.insert_devops_metrics_info(metrics_info)
        logger.info("Finished inserting into DB, process completed successfully")
    else:
        logger.info("This app version has already been deployed. No further work needed. app={} version={}"
                    .format(project_name, project_version))


def rename_project_if_needed(project_name: str) -> str:
    if project_name == "cvel":
        project_name = "cv-event-listener"
    elif project_name == "cvmadmin":
        project_name = "cv-management-admin-web"
    elif project_name == "cvmweb":
        project_name = "cv-management-web"
    elif project_name == "shadegen":
        project_name = "shading-analysis-generator"
    elif project_name == "measgen":
        project_name = "measurements-generator"
    elif project_name == "modelgen":
        project_name = "model-generator"

    return project_name


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Store devops metrics")
    parser.add_argument("--project_name", help="The name of the project that was just deployed. "
                                               "The git repo name is preferred.", required=True)
    parser.add_argument("--project_version", help="The version of the project that was just deployed.", required=True)
    parser.add_argument("--deployed_instant", help="The name of the project that was just deployed. "
                                                   "The git repo name is preferred.", required=True)
    parser.add_argument("--deployed_by_user_id", help="The id of the user who triggered the deploy.", required=True)
    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
    outer_logger = logging.getLogger(__name__)
    outer_logger.setLevel("DEBUG")

    main(outer_logger,
         args.project_name,
         args.project_version,
         args.deployed_instant,
         args.deployed_by_user_id)
