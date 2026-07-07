import logging

from odoo import SUPERUSER_ID, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # A database migrated while this module was dormant carries its workflow
    # templates deactivated, and a module update never touches the active
    # flag; without this the /ebill/* routes cannot resolve their templates.
    view_refs = env["ir.model.data"].search(
        [
            ("module", "=", "ebill_postfinance_recipient_subscription"),
            ("model", "=", "ir.ui.view"),
        ]
    )
    views = env["ir.ui.view"].browse(view_refs.mapped("res_id")).exists()
    for view in views.filtered(lambda view: not view.active):
        # A view that no longer validates (stale record pending cleanup)
        # must stay deactivated.
        try:
            with env.cr.savepoint():
                view.write({"active": True})
            _logger.info("reactivated view %s", view.key or view.name)
        except ValidationError:
            _logger.warning(
                "left view %s deactivated, it no longer validates",
                view.key or view.name,
            )
