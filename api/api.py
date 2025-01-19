import xmlrpc.client
from datetime import datetime, timedelta

MONTHS = ["", "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE",
          "NOVIEMBRE", "DICIEMBRE"]


class OdooApi:

    def __init__(self, server, db, user, key, company):
        self.server = server
        self.db = db
        self.user = user
        self.key = key
        self.uid = 0
        self.common = False
        self.company = company

    def connect(self):
        if not self.common:
            common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(self.server))
            uid = common.authenticate(self.db, self.user, self.key, {})

            self.uid = uid
            self.common = common

        return self.common

    def get_sale_subscription(self, models, identification):
        subscription = {}
        ids = []
        saleSubscriptions = models.execute_kw(
            self.db,
            self.uid,
            self.key,
            'sale.subscription',
            'search_read',
            [[
                ['partner_id.vat', '=', identification],
                ['company_id', '=', self.company],
            ]],
            {'fields': ['id', 'name', 'code']})

        for rec in saleSubscriptions:
            ids.append(rec.get('id', 0))
            subscription[rec.get('id', 0)] = rec.get('code', 0)
        return (subscription, ids)

    def get_sale_order_with_amount_residual(self, models, ids):
        partners = {}
        sales = models.execute_kw(
            self.db,
            self.uid,
            self.key,
            'sale.order',
            'search_read',
            [[
                ['id', 'in', ids],
                ['amount_residual', '>', 0],
                ['company_id', '=', self.company],
            ]],
            {'fields': ['id', 'partner_id']})

        for rec in sales:
            partners[rec.get('id', 0)] = rec.get('partner_id')[0]
        return partners

    def get_debt_payment(self, identification):
        self.connect()
        models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(self.server))

        (subscription, ids) = self.get_sale_subscription(models, identification)
        sales_for_payment = []

        domain = []
        sales = models.execute_kw(
            self.db,
            self.uid,
            self.key,
            'sale.order',
            'search_read',
            [[
                ['partner_id.vat', '=', identification],
                ['amount_residual', '>', 0],
                ['company_id', '=', self.company],
                ['order_line.subscription_id', 'in', ids],
            ]],
            {'fields': ['id', 'name', 'partner_id', 'promotion_templ_id', 'ek_subscription_id', 'amount_residual',
                        'date_order', 'amount_tax','account_payment_ids','amount_total'],
             'order': "date_order asc"})

        partner = False
        for sale in sales:
            payment_valitation = self.get_payment_validation_value(models, sale.get('id', 0))
            if payment_valitation:
                continue
            if self._normalize_total(sale.get('amount_total', 0)) != self._normalize_total(sale.get('amount_residual', 0)):
                continue
            date_str_to = datetime.strptime(sale.get('date_order'), '%Y-%m-%d %H:%M:%S') + timedelta(hours=-5)
            if not partner:
                partner = sale.get('partner_id', ["", False])[1]
            if sale.get("ek_subscription_id", False):
                contrato = subscription.get(sale.get("ek_subscription_id")[0], list(subscription.values())[0])
            else:
                contrato = list(subscription.values())[0]

            referencia1 = "%s - %s %s" % (
                sale.get('name'),
                MONTHS[date_str_to.month],
                date_str_to.year
            )
            sales_for_payment.append({
                "referencia": sale.get('id', 0),
                "contrato": contrato,
                "referencia1": referencia1,
                "valor": self._normalize_total(sale.get('amount_residual', 0)),
                "comision": 0,
                "valorMinimo": self._normalize_total(sale.get('amount_residual', 0)),
                "codigoRetorno": 0,
                "iva": self._normalize_total(sale.get('amount_tax', 0)),
                "prioridad": 1,
            })

        return (sales_for_payment, partner)

    def get_payment_validation_value(self, models, sale_id):
        value_payment = models.execute_kw(
            self.db,
            self.uid,
            self.key,
            'account.payment',
            'search_read',
            [[
                ['sale_id', '=', sale_id],
                ['state', '=', 'posted'],
            ]],
            {'fields': ['amount']})
        return sum([x.get('amount', 0) for x in value_payment])

    def get_sale_order_amount_residual_payment(self, models, id):
        sales = models.execute_kw(
            self.db,
            self.uid,
            self.key,
            'sale.order',
            'search_read',
            [[
                ['id', 'in', id],
            ]],
            {'fields': ['amount_residual']})
        
        return sum([x.get('amount_residual', 0) for x in sales])


    def _exists_id_in_list(self, list_ids, list_match):
        return [str(x) for x in list_ids if x not in list_match]

    def set_debt_payment(self, journal, pmethod, payments, idtransaccion):
        self.connect()
        models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(self.server), allow_none=True)
        partner_id_for_sale = self.get_sale_order_with_amount_residual(models, list(payments.keys()))
       # odoo_payments_id = []
        key_not_exit = self._exists_id_in_list(list(payments.keys()), list(partner_id_for_sale.keys()))
        if len(key_not_exit) > 0:
            raise Exception(
                "LA(S) DEUDA(S) CON REFERENCIA(S) %s NO HA(N) SIDO ENCONTRADA(S)" % ",".join(key_not_exit))
                    
        dict_payment = []
        for sale, amount in payments.items():
            value_total = self.get_sale_order_amount_residual_payment(models, [sale])
            if amount != self._normalize_total(value_total) :
                raise Exception(
                    "NO HA ENVIADO LOS VALORES CORRECTOS DE DEUDA PARA REALIZAR EL PAGO")
            dict_payment.append({
                'sale_id': sale,
                'amount': self._desnormalize_total(amount),
                'journal_id': journal,
                'payment_method_line_id': pmethod,
                'partner_id': partner_id_for_sale[sale],
                'date': datetime.today().strftime('%Y-%m-%d'),
                'payment_time': datetime.today().strftime('%Y-%m-%d %H:%M:%S'),
                'ref': idtransaccion,
                'ref_ext': idtransaccion,
                'ref_card': idtransaccion,
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'company_id': self.company,
		        'is_collector': True,
                "collector_ext":  'switch',

            })
        payment_id = models.execute_kw(
            self.db,
            self.uid,
            self.key,
            'account.payment',
            'create',
            [dict_payment]
        )


        try:
            models.execute_kw(
                self.db,
                self.uid,
                self.key,
                'account.payment',
                'action_post',
                [payment_id]
            )
        except Exception as ex:
            if "allow_none is enabled" not in ex.__str__():
                self.reverse_debt_payment(idtransaccion)
                raise ex

    def reverse_debt_payment(self, idtransaccion, identification):
        self.connect()
        models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(self.server), allow_none=True)

        ids = models.execute_kw(self.db,
                                self.uid,
                                self.key, 'account.payment', 'search', [[
                ['ref_card', '=', idtransaccion],
                ['state', '=', 'posted'],

            ]])

        if not ids:
            raise Exception("NO EXISTEN TRANSACCIONES A REVERSAR CON EL ID %s" % idtransaccion)

        try:
            models.execute_kw(
                self.db,
                self.uid,
                self.key,
                'account.payment',
                'action_cancel',
                [ids]
            )
        except Exception as ex:
            if "allow_none is enabled" not in ex.__str__():
                raise ex

    def _normalize_total(self, amount):
        total = str("%.2f" % amount)
        _normalize = total.replace(".", "").replace(",", "")
        return int(_normalize[0]) == 0 and _normalize[1:] or _normalize

    def _desnormalize_total(self, amount):
        str_amount = str(amount)
        if amount:
            if len(str_amount) >= 3:
                return float("%s.%s" % (str_amount[:-2], str_amount[-2:]))
            else:
                return float("0.%s" % str_amount)

