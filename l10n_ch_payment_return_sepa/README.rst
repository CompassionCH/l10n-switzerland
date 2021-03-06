====================
Parse payment return
====================

.. !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
   !! This file is generated by oca-gen-addon-readme !!
   !! changes will be overwritten.                   !!
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/licence-AGPL--3-blue.png
    :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3
.. |badge3| image:: https://img.shields.io/badge/github-OCA%2Fl10n--switzerland-lightgray.png?logo=github
    :target: https://github.com/OCA/l10n-switzerland/tree/11.0/l10n_ch_payment_return_sepa
    :alt: OCA/l10n-switzerland
.. |badge4| image:: https://img.shields.io/badge/weblate-Translate%20me-F47D42.png
    :target: https://translation.odoo-community.org/projects/l10n-switzerland-11-0/l10n-switzerland-11-0-l10n_ch_payment_return_sepa
    :alt: Translate me on Weblate
.. |badge5| image:: https://img.shields.io/badge/runbot-Try%20me-875A7B.png
    :target: https://runbot.odoo-community.org/runbot/125/11.0
    :alt: Try me on Runbot

|badge1| |badge2| |badge3| |badge4| |badge5| 

This module allow you to parse and import pain002 files. It will automatically cancel payment and reconciliation for rejected payment.

** Features list :**
    * import pain002 files
    * parse pain002 files
    * unpost rejected payments
    * unreconcile rejected payments
    * remove payments lines from rejected payments
    * remove payment order there's no more payment line in it

**Table of contents**

.. contents::
   :local:

Known issues / Roadmap
======================

If pmt is in return (use EndToEndId to identify the payment order payment.order.line.name)
    * do the same as rejected pain002
    * reconcile together payment out with the in
    * do this in the completion/reconcile process

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/OCA/l10n-switzerland/issues>`_.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us smashing it by providing a detailed and welcomed
`feedback <https://github.com/OCA/l10n-switzerland/issues/new?body=module:%20l10n_ch_payment_return_sepa%0Aversion:%2011.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_.

Do not contact contributors directly about support or help with technical issues.

Credits
=======

Authors
~~~~~~~

* Compassion CH

Contributors
~~~~~~~~~~~~

* Marco Monzione
* Benoît Schopfer

Maintainers
~~~~~~~~~~~

This module is maintained by the OCA.

.. image:: https://odoo-community.org/logo.png
   :alt: Odoo Community Association
   :target: https://odoo-community.org

OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.

This module is part of the `OCA/l10n-switzerland <https://github.com/OCA/l10n-switzerland/tree/11.0/l10n_ch_payment_return_sepa>`_ project on GitHub.

You are welcome to contribute. To learn how please visit https://odoo-community.org/page/Contribute.
