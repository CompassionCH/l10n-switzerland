import re
from lxml import etree

from openerp import models


class customParser(models.AbstractModel):
    _inherit = 'account.bank.statement.import.camt.parser'

    def parse_entry(self, ns, node):
        """Parse an Ntry node and yield transactions"""
        transaction = {'name': '/', 'amount': 0}  # fallback defaults
        self.add_value_from_node(
            ns, node, './ns:BkTxCd/ns:Prtry/ns:Cd', transaction,
            'transfer_type'
        )
        self.add_value_from_node(
            ns, node, './ns:BookgDt/ns:Dt', transaction, 'date')
        self.add_value_from_node(
            ns, node, './ns:BookgDt/ns:Dt', transaction, 'execution_date')
        self.add_value_from_node(
            ns, node, './ns:ValDt/ns:Dt', transaction, 'value_date')
        amount = self.parse_amount(ns, node)
        if amount != 0.0:
            transaction['amount'] = amount
        self.add_value_from_node(
            ns, node, './ns:AddtlNtryInf', transaction, 'name')
        self.add_value_from_node(
            ns, node, [
                './ns:NtryDtls/ns:RmtInf/ns:Strd/ns:CdtrRefInf/ns:Ref',
                './ns:NtryDtls/ns:Btch/ns:PmtInfId',
                './ns:NtryDtls/ns:TxDtls/ns:Refs/ns:AcctSvcrRef'
            ],
            transaction, 'ref'
        )
        details_nodes = node.xpath(
            './ns:NtryDtls/ns:TxDtls', namespaces={'ns': ns})
        if len(details_nodes) == 0:
            yield transaction
            self.add_value_from_node(
                ns, node, './ns:AcctSvcrRef', transaction, 'acct_svcr_ref')
            return
        transaction_base = transaction
        for node in details_nodes:
            transaction = transaction_base.copy()
            self.parse_transaction_details(ns, node, transaction)
            yield transaction

    def parse_transaction_details(self, ns, node, transaction):
        super(customParser, self).parse_transaction_details(
            ns, node, transaction)
        # Check if a global AcctSvcrRef exist
        found_node = node.xpath('../../ns:AcctSvcrRef', namespaces={'ns': ns})
        if len(found_node) != 0:
            self.add_value_from_node(
                ns, node, '../../ns:AcctSvcrRef', transaction, 'acct_svcr_ref')
        else:
            self.add_value_from_node(ns, node, './ns:Refs/ns:AcctSvcrRef', transaction,'acct_svcr_ref')

    def parse_statement(self, ns, node):
        result = super(customParser, self).parse_statement(ns, node)
        self.add_value_from_node(
            ns, node, './ns:Ntry/ns:NtryRef', result, 'ntryRef')
        return result

    def parse(self, data):
        result = super(customParser, self).parse(data)
        currency = result[0]
        account_number = result[1]
        statements = result[2]

        if 'ntryRef' in statements[0]:
            account_number = statements[0]['ntryRef']
        return currency, account_number, statements

    def get_balance_amounts(self, ns, node):
        result = super(customParser, self).get_balance_amounts(ns, node)
        start_balance_node = result[0]
        end_balance_node = result[0]

        details_nodes = node.xpath(
            './ns:Bal/ns:Amt', namespaces={'ns': ns})

        if start_balance_node == 0.0 and not len(details_nodes):
            start_balance_node = node.xpath('./ns:Ntry', namespaces={'ns':
                                                                         ns})
            amount_tot = 0
            for node in start_balance_node:
                amount_tot -= self.parse_amount(ns, node)
            return (
                amount_tot,
                end_balance_node
            )
        return result

    def check_version(self, ns, root):
        try:
            super(customParser, self).check_version(ns, root)
        except ValueError:
            re_camt_version = re.compile(
                r'(^urn:iso:std:iso:20022:tech:xsd:camt.054.'
                r'|^ISO:camt.054.)'
            )
            if not re_camt_version.search(ns):
                raise ValueError('no camt 052 or 053 or 054: ' + ns)
            # Check GrpHdr element:
            root_0_0 = root[0][0].tag[len(ns) + 2:]  # strip namespace
            if root_0_0 != 'GrpHdr':
                raise ValueError('expected GrpHdr, got: ' + root_0_0)

