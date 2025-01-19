# -*- coding: utf-8 -*-
##############################################################################
#    Sistema FINAMSYS
#    Copyright (C) 2019-Today Ekuasoft S.A All Rights Reserved
#
#    Collaborators of this module:
#    Coded by: Cristhian Luzon <@cristhian_70>
#    Planifyied by: Yordany Oliva
#   This project is mantained by Ekuasoft Group Solutions
##############################################################################

from api import app
from api import OdooApi



if __name__ == '__main__':
    app.run(port=9002, host="0.0.0.0",debug=True)
