import sys
from flask import Flask
from flask import request, json
import os
from mako.template import Template as MakoTemplate
from .api import OdooApi

app = Flask(__name__)

dir_json = os.path.dirname(os.path.realpath(__file__))
filname = os.path.join(dir_json, 'config.json')
with open(filname) as config_file:
    conn_config = json.load(config_file)


# #TODO LOGUIN ODOO
srv_app = conn_config['ODOO_SERVER']
db_app = conn_config['ODOO_DATABASE']
usr_app = conn_config['ODOO_USER']
apikey_app = conn_config['ODOO_APIKEY']
journal = conn_config['ODOO_PAYMENT_METHOD_ID']
pmethod = conn_config['ODOO_PAYMENT_METHOD_LINE_ID']
company = conn_config['ODOO_COMPANY_ID']
API = OdooApi(srv_app,db_app,usr_app,apikey_app,company)

@app.route('/cobrosexternos/cobros/getdata', methods=['POST', 'GET'])
def get_data_debit():
    codigo = request.args.get('codigo')
    (pagos,partner) = API.get_debt_payment(codigo)
    if pagos:
        _template = MakoTemplate(filename=os.path.join(dir_json, "template/debt_response.xml"))
    else:
        _template = MakoTemplate(filename=os.path.join(dir_json, "template/not_debt_response.xml"))

    return _template.render(
        nombre=partner,
        cedDeudor=request.args.get('codigo'),
        codDeudor=request.args.get('codigo'),
        pagos=pagos
    ).encode('utf-8', 'replace')


@app.route('/cobrosexternos/cobros/setdata', methods=['POST', 'GET'])
def set_data_payment_or_reverse():
    pagos = request.args.get('PAGOS')
    idtransaccion = request.args.get('idtransaccion')
    codigo = request.args.get('codigo')
    identificacion = request.args.get('identificacion')
    canal = request.args.get('canal')
    reverso = request.args.get('reverso')
    API.connect()
    if int(reverso) == 1:
        #todo Reverso
        try:
            API.reverse_debt_payment(idtransaccion,identificacion)
            _template = MakoTemplate(filename=os.path.join(dir_json, "template/payment_reverse.xml"))
            return _template.render(
                identificacion=identificacion or codigo,
                cedDeudor=identificacion or codigo
            )
        except Exception as ex:
            _template = MakoTemplate(filename=os.path.join(dir_json, "template/error_reverse_payment.xml"))
            return _template.render(
                error=ex.__str__(),
                identificacion=identificacion or codigo,
                cedDeudor= identificacion or codigo

            ).encode('utf-8', 'replace')
    else:
        #todo Pago
        if not pagos:
            _template = MakoTemplate(filename=os.path.join(dir_json, "template/error_send_payment.xml"))
            return _template.render(
                error="NO HA ENVIADO LOS VALORES CORRECTOS PARA REALIZAR EL PAGO"
            )

        payment_lines = pagos.split(";")
        payment_disc = {}
        for line in payment_lines:
            (referencia, monto) = line.split(":")
            payment_disc[int(referencia)] = monto

        try:
            API.set_debt_payment(journal,pmethod,payment_disc,idtransaccion,canal)
            _template = MakoTemplate(filename=os.path.join(dir_json, "template/return_debt_payment.xml"))

            return _template.render(
                        identificacion=request.args.get('codigo'),
                        cedDeudor=request.args.get('codigo'),
                    ).encode('utf-8', 'replace')
        except Exception as ex:
            _template = MakoTemplate(filename=os.path.join(dir_json, "template/error_send_payment.xml"))
            return _template.render(
                error=ex.__str__()
            ).encode('utf-8', 'replace')