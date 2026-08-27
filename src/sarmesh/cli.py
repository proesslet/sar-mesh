from pathlib import Path

import typer

from sarmesh.storage.database import Database

app = typer.Typer(help="SARMesh command line interface")

incident_app = typer.Typer(help="Manage incidents")
team_app = typer.Typer(help="Manage teams")
tracker_app = typer.Typer(help="Manage trackers")

app.add_typer(incident_app, name="incident")
app.add_typer(team_app, name="team")
app.add_typer(tracker_app, name="tracker")


def get_database() -> Database:
    database = Database(Path("sarmesh.db"))
    database.initialize()
    return database


@incident_app.command("create")
def create_incident(
    name: str,
) -> None:
    database = get_database()

    incident = database.create_incident(name=name)

    typer.echo(f"Created incident {incident.id}: {incident.name}")


@team_app.command("create")
def create_team(
    name: str,
    personnel: int = typer.Option(
        1,
        "--personnel",
        "-p",
        help="Number of personnel in the team",
    ),
) -> None:
    database = get_database()

    team = database.create_team(
        name=name,
        personnel_count=personnel,
    )

    typer.echo(f"Created team {team.id}: {team.name}")


@tracker_app.command("add")
def add_tracker(
    node_id: str,
    label: str,
) -> None:
    database = get_database()

    tracker = database.create_tracker(
        node_id=node_id,
        label=label,
    )

    typer.echo(f"Added tracker {tracker.label} ({tracker.node_id})")


@tracker_app.command("assign")
def assign_tracker(
    node_id: str,
    team_id: str,
    incident_id: str,
) -> None:
    database = get_database()

    database.assign_tracker(
        incident_id=incident_id,
        tracker_node_id=node_id,
        team_id=team_id,
    )

    typer.echo(f"Assigned {node_id} to team {team_id} for incident {incident_id}")


@app.command("run")
def run(
    host: str | None = typer.Option(
        None,
        "--host",
        "-H",
        help="Reach the node over TCP instead of USB serial",
    ),
    port: int | None = typer.Option(
        None,
        "--port",
        help="TCP port for --host (default 4403)",
    ),
) -> None:
    from sarmesh.core.registry import TrackerRegistry
    from sarmesh.services.tracking import TrackingService
    from sarmesh.transports.meshtastic import MeshtasticTransport

    database = get_database()
    registry = TrackerRegistry()
    tracking_service = TrackingService(
        registry=registry,
        database=database,
    )

    transport = MeshtasticTransport(
        on_position=tracking_service.handle_position,
        host=host,
        port=port,
    )

    try:
        transport.run()
    except ConnectionError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error
    finally:
        database.close()
