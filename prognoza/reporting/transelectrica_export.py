"""Export notificari fizice catre format XML/CSV pentru Transelectrica."""
from __future__ import annotations

from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Optional
from xml.etree.ElementTree import Element, SubElement, tostring
from zoneinfo import ZoneInfo

import pandas as pd

try:
    import xmlschema
except ImportError:  # pragma: no cover
    xmlschema = None

from prognoza.processing.notification_builder import PhysicalNotification

CSV_HEADERS = [
    "COD_PRE",
    "COD_BRP",
    "DATA_LIVRARE",
    "INTERVAL_START",
    "INTERVAL_END",
    "PUTERE_MW",
    "UNITATE_ID",
]


def notification_to_xml(notification: PhysicalNotification) -> bytes:
    root = Element("NotificareFizica")
    header = SubElement(root, "Header")
    SubElement(header, "CodPRE").text = notification.cod_pre
    SubElement(header, "CodBRP").text = notification.cod_brp
    SubElement(header, "DataLivrare").text = notification.delivery_day.strftime("%Y-%m-%d")
    SubElement(header, "Rezolutie").text = notification.resolution
    productie = SubElement(root, "Productie")
    for entry in notification.intervals:
        interval = SubElement(productie, "Interval")
        SubElement(interval, "Start").text = entry.start.isoformat()
        SubElement(interval, "End").text = entry.end.isoformat()
        SubElement(interval, "Putere").text = f"{entry.power_mw:.3f}"
    return tostring(root, encoding="utf-8", xml_declaration=True)


def notification_to_csv(notification: PhysicalNotification, unit_id: str) -> pd.DataFrame:
    rows = []
    for entry in notification.intervals:
        rows.append(
            [
                notification.cod_pre,
                notification.cod_brp,
                notification.delivery_day.strftime("%Y-%m-%d"),
                entry.start.isoformat(),
                entry.end.isoformat(),
                f"{entry.power_mw:.3f}",
                unit_id,
            ]
        )
    return pd.DataFrame(rows, columns=CSV_HEADERS)


def save_xml(notification: PhysicalNotification, path: Path, schema: Optional[Path] = None) -> None:
    xml_bytes = notification_to_xml(notification)
    path.write_bytes(xml_bytes)
    if schema and xmlschema:
        xmlschema.XMLSchema(str(schema)).validate(str(path))


def save_csv(notification: PhysicalNotification, path: Path, unit_id: str) -> None:
    df = notification_to_csv(notification, unit_id)
    df.to_csv(path, index=False)


def ensure_deadline(delivery_day: datetime, submit_time: datetime, tz: str = "Europe/Bucharest") -> bool:
    """Returneaza ``True`` daca notificarea este transmisa pana la D-1 ora 15:00."""

    zone = ZoneInfo(tz)

    if delivery_day.tzinfo is None:
        delivery_ref = delivery_day.replace(tzinfo=zone)
    else:
        delivery_ref = delivery_day.astimezone(zone)

    deadline_date = delivery_ref.date() - timedelta(days=1)
    deadline = datetime.combine(deadline_date, time(hour=15), tzinfo=zone)

    if submit_time.tzinfo is None:
        submit_ref = submit_time.replace(tzinfo=zone)
    else:
        submit_ref = submit_time.astimezone(zone)

    return submit_ref <= deadline
