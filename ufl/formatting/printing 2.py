# -*- coding: utf-8 -*-
"""A collection of utility algorithms for printing
of UFL objects, mostly intended for debugging purposes."""

# Copyright (C) 2008-2015 Martin Sandve Alnæs
#
# This file is part of UFL.
#
# UFL is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# UFL is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with UFL. If not, see <http://www.gnu.org/licenses/>.
#
# Modified by Anders Logg 2009, 2014

from itertools import chain

from ufl.log import error
from ufl.assertions import ufl_assert
from ufl.core.expr import Expr
from ufl.core.terminal import Terminal
from ufl.form import Form
from ufl.integral import Integral, Measure

#--- Utilities for constructing informative strings from UFL objects ---

def integral_info(integral):
    ufl_assert(isinstance(integral, Integral), "Expecting an Integral.")
    s  = "  Integral:\n"
    s += "    Type:\n"
    s += "      %s\n" % integral.integral_type()
    s += "    Domain:\n"
    s += "      %r\n" % integral.domain()
    s += "    Domain id:\n"
    s += "      %r\n" % integral.subdomain_id()
    s += "    Domain data:\n"
    s += "      %s\n" % integral.subdomain_data()
    s += "    Compiler metadata:\n"
    s += "      %s\n" % integral.metadata()
    s += "    Integrand expression representation:\n"
    s += "      %r\n" % integral.integrand()
    s += "    Integrand expression short form:\n"
    s += "      %s" % integral.integrand()
    return s

def form_info(form):
    ufl_assert(isinstance(form, Form), "Expecting a Form.")

    bf = form.arguments()
    cf = form.coefficients()

    s  = "Form info:\n"
    s += "  rank:                          %d\n" % len(bf)
    s += "  num_coefficients:              %d\n" % len(cf)
    s += "\n"

    for f in cf:
        if f._name:
            s += "\n"
            s += "  Coefficient %d is named '%s'" % (f._count, f._name)
    s += "\n"

    integrals = form.integrals()
    integral_types = sorted(set(itg.integral_type() for itg in integrals))
    for integral_type in integral_types:
        itgs = form.integrals_by_type(integral_type)
        s += "  num_{0}_integrals:  {1}\n".format(integral_type, len(itgs))
    s += "\n"

    for integral_type in integral_types:
        itgs = form.integrals_by_type(integral_type)
        for itg in itgs:
            s += integral_info(itg)
            s += "\n"

    return s

def _indent_string(n):
    return "    "*n

def _tree_format_expression(expression, indentation, parentheses):
    ind = _indent_string(indentation)
    if expression._ufl_is_terminal_:
        s = ind + "%s" % repr(expression)
    else:
        sops = [_tree_format_expression(o, indentation+1, parentheses) for o in expression.ufl_operands]
        s = ind + "%s\n" % expression._ufl_class_.__name__
        if parentheses and len(sops) > 1:
            s += ind + "(\n"
        s += "\n".join(sops)
        if parentheses and len(sops) > 1:
            s += "\n" + ind + ")"
    return s

def tree_format(expression, indentation=0, parentheses=True):
    s = ""

    if isinstance(expression, Form):
        form = expression
        integrals = form.integrals()
        integral_types = sorted(set(itg.integral_type() for itg in integrals))
        itgs = []
        for integral_type in integral_types:
            itgs += list(form.integrals_by_type(integral_type))

        ind = _indent_string(indentation)
        s += ind + "Form:\n"
        s += "\n".join(tree_format(itg, indentation+1, parentheses) for itg in itgs)

    elif isinstance(expression, Integral):
        ind = _indent_string(indentation)
        s += ind + "Integral:\n"
        ind = _indent_string(indentation+1)
        s += ind + "integral type: %s\n" % expression.integral_type()
        s += ind + "subdomain id: %s\n" % expression.subdomain_id()
        s += ind + "integrand:\n"
        s += tree_format(expression._integrand, indentation+2, parentheses)

    elif isinstance(expression, Expr):
        s += _tree_format_expression(expression, indentation, parentheses)

    else:
        error("Invalid object type %s" % type(expression))

    return s
