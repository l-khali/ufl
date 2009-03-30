#!/usr/bin/env python
"""Render the ufl.Expr class hierarchy in .dot format."""

from collections import defaultdict
from ufl.classes import all_ufl_classes
import sys, optparse

# Get commandline options
usage = """Render a subset of the UFL class hierarchy."""

def opt(long, short, t, default, help):
    return optparse.make_option("--%s" % long, "-%s" % short, action="store", type=t, dest=long, default=default, help=help)

option_list = [ \
    opt("parent",     "p", "str", "object", "Parent of tree to render."),
    opt("skipparent", "s", "int", 1,        "Skip parent when rendering tree."),
    opt("maxlevels",  "m", "int", None,     "Max levels of tree to render."),
    ]

parser = optparse.OptionParser(usage=usage, option_list=option_list)
args = sys.argv[1:]
(options, args) = parser.parse_args(args=args)

parent = options.parent or "object"
skipparent = options.skipparent
maxlevels = options.maxlevels
level = 1 #options.level

# Build lists of subclasses
subgraphs = defaultdict(list)
for c in all_ufl_classes:
    subgraphs[c.mro()[1].__name__].append(c.__name__)

# Recursive graph formatting
def format_children(parent, level, skipparent=True, maxlevels=None):
    if maxlevels is not None and maxlevels <= 0:
        return ""
    children = subgraphs[parent]
    t = "  "*level
    begin = t + "subgraph {\n"
    end   = t + "}\n"
    g = ""
    for child in children:
        if child in subgraphs:
            g += begin
            g += format_children(child, level+1, skipparent=False, maxlevels=None if maxlevels is None else maxlevels-1)
            g += end
        if not skipparent:
            g += t + "%s -> %s;\n" % (child, parent)
    return g

# Render graph body!
body = format_children(parent, level, skipparent, maxlevels)

# Set global formatting options
format = """
  node [shape=box, style=filled, color=lightgrey];
  splines=true;
"""

# Combine everythig to a global graph
dot = """strict digraph {
%s
%s
}""" % (format, body)
print dot