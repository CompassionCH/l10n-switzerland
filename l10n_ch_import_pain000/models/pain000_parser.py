from odoo import models

from lxml import etree


class Pain000Parser(models.AbstractModel):
    _name = 'account.pain000.parser'

    def parse(self, data):
        account_move_line_obj = self.env['account.move.line']
        payment_order_obj = self.env['account.payment.order']
        payment_line_obj = self.env['account.payment.line']
        account_move_obj = self.env['account.move']
        account_bank_parser_obj = self.env[
            'account.bank.statement.import.camt.parser']

        root = etree.fromstring(data, parser=etree.XMLParser(recover=True))
        ns = root.tag[1:root.tag.index("}")]

        result = dict()

        account_bank_parser_obj.add_value_from_node(ns, root,
                                 './ns:CstmrPmtStsRpt/ns:OrgnlGrpInfAndSts/ns:OrgnlMsgId',
                                 result,
                                 'orgnl_msg_id')
        account_bank_parser_obj.add_value_from_node(ns, root,
                                 './ns:CstmrPmtStsRpt/ns:OrgnlGrpInfAndSts/ns:OrgnlMsgNmId',
                                 result,
                                 'orgnl_msg_nm_Id')
        account_bank_parser_obj.add_value_from_node(ns, root,
                                 './ns:CstmrPmtStsRpt/ns:OrgnlPmtInfAndSts/ns:OrgnlPmtInfId',
                                 result,
                                 'orgnl_pmt_inf_id')

        account_bank_parser_obj.add_value_from_node(ns, root,
                                 './ns:CstmrPmtStsRpt/ns:OrgnlPmtInfAndSts/ns:PmtInfSts',
                                 result,
                                 'pmt_inf_sts')

        account_bank_parser_obj.add_value_from_node(ns, root,
                                 './ns:CstmrPmtStsRpt/ns:OrgnlPmtInfAndSts/ns:TxInfAndSts/ns:StsRsnInf/ns:Rsn/ns:Cd',
                                 result,
                                 'full_reconcile_id')
        account_bank_parser_obj.add_value_from_node(ns, root,
                                 './ns:CstmrPmtStsRpt/ns:OrgnlPmtInfAndSts/ns:StsRsnInf/ns:Rsn/ns:Cd',
                                 result,
                                 'full_reconcile_id')

        account_bank_parser_obj.add_value_from_node(ns, root,
                                  './ns:CstmrPmtStsRpt/ns:OrgnlPmtInfAndSts/ns:TxInfAndSts/ns:StsRsnInf/ns:AddtlInf',
                                  result,
                                  'add_tl_inf')

        if len(result) > 1 and 'orgnl_msg_nm_Id' in result:
            if result['orgnl_msg_nm_Id'] == 'pain.001':
                if 'pmt_inf_sts' in result:
                    if result['pmt_inf_sts'] == 'RJCT':
                        payment_order_obj = payment_order_obj.search([('name', '=', result['orgnl_msg_id'])])
                        payment_line_obj = payment_line_obj.search([('name', '=',result['orgnl_pmt_inf_id'])])

                        if payment_order_obj and payment_line_obj:
                            for payment_order_line in payment_order_obj:
                                move_ids = payment_order_line.ids

                            move_line_id = payment_line_obj.move_line_id.id
                            account_move_line_obj = account_move_line_obj.search([('id', '=', move_line_id)])
                            move_id = account_move_line_obj.move_id.id
                            display_name = account_move_line_obj.display_name

                            account_full_reconcile_id = account_move_line_obj.full_reconcile_id.id
                            account_move_line_obj = account_move_line_obj.search([('full_reconcile_id', '=', account_full_reconcile_id)
                                                                                  ,('move_id', '!=', move_id)])

                            account_move_obj = account_move_obj.search([('id', '=',account_move_line_obj.move_id.id)])

                            for move_line in account_move_obj:
                                # Unreconcile
                                account_move_line_obj.remove_move_reconcile()
                                # unpost
                                account_move_obj.button_cancel()
                                # Unlink
                                move_line.unlink()

                                payment_line_obj.unlink()

                                payment_line_obj = payment_line_obj.search([('order_id','=', move_ids)])
                                if len(payment_line_obj) == 0:
                                    payment_order_obj.unlink()
                            if 'add_tl_inf' in result:
                                payment_order_obj.message_post(display_name +
                                " has been removed beause : " + result['add_tl_inf'])
                            else:
                                payment_order_obj.message_post(display_name +
                                                               " has been "
                                                               "removed, "
                                                               "no reason "
                                                               "given.")
                return True
        return False

