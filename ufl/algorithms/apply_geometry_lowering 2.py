# -*- coding: utf-8 -*-
"""Algorithm for lowering abstractions of geometric types.

This means replacing high-level types with expressions
of mostly the Jacobian and reference cell data.
"""

# Copyright (C) 2013-2015 Martin Sandve Alnæs
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

from six.moves import xrange as range

from ufl.log import error, warning
from ufl.assertions import ufl_assert

from ufl.core.multiindex import Index, indices
from ufl.corealg.multifunction import MultiFunction, memoized_handler
from ufl.corealg.map_dag import map_expr_dag

from ufl.classes import (Expr, Form, Integral,
                         ReferenceGrad, ReferenceValue,
                         Jacobian, JacobianInverse, JacobianDeterminant,
                         CellOrientation, CellOrigin, CellCoordinate,
                         FacetJacobian, FacetJacobianDeterminant,
                         CellFacetJacobian,
                         CellEdgeVectors, FacetEdgeVectors,
                         FacetNormal, CellNormal, ReferenceNormal,
                         ReferenceCellVolume, ReferenceFacetVolume,
                         CellVolume, FacetArea,
                         SpatialCoordinate)
#FacetJacobianInverse,
#FacetOrientation, QuadratureWeight,

from ufl.tensors import as_tensor, as_vector
from ufl.operators import sqrt, max_value, min_value

from ufl.compound_expressions import determinant_expr, cross_expr, inverse_expr


class GeometryLoweringApplier(MultiFunction):
    def __init__(self, preserve_types=()):
        MultiFunction.__init__(self)
        # Store preserve_types as boolean lookup table
        self._preserve_types = [False]*Expr._ufl_num_typecodes_
        for cls in preserve_types:
            self._preserve_types[cls._ufl_typecode_] = True

    expr = MultiFunction.reuse_if_untouched

    def terminal(self, t):
        return t

    @memoized_handler
    def jacobian(self, o):
        if self._preserve_types[o._ufl_typecode_]:
            return o

        domain = o.domain()
        if domain.ufl_coordinates() is None:
            # Affine case in FEniCS: preserve J if there's no coordinate function
            # (the handling of coordinate functions will soon be refactored)
            return o

        x = self.spatial_coordinate(SpatialCoordinate(domain))
        return ReferenceGrad(x)

    @memoized_handler
    def _future_jacobian(self, o):
        # If we're not using Coefficient to represent the spatial coordinate,
        # we can just as well just return o here too unless we add representation
        # of basis functions and dofs to the ufl layer (which is nice to avoid).
        return o

    @memoized_handler
    def jacobian_inverse(self, o):
        if self._preserve_types[o._ufl_typecode_]:
            return o

        domain = o.domain()
        J = self.jacobian(Jacobian(domain))
        # TODO: This could in principle use preserve_types[JacobianDeterminant] with minor refactoring:
        K = inverse_expr(J)
        return K

    @memoized_handler
    def jacobian_determinant(self, o):
        if self._preserve_types[o._ufl_typecode_]:
            return o

        domain = o.domain()
        J = self.jacobian(Jacobian(domain))
        detJ = determinant_expr(J)

        # TODO: Is "signing" the determinant for manifolds the cleanest approach?
        #       The alternative is to have a specific type for the unsigned pseudo-determinant.
        if domain.topological_dimension() < domain.geometric_dimension():
            co = CellOrientation(domain)
            detJ = co*detJ

        return detJ

    @memoized_handler
    def facet_jacobian(self, o):
        if self._preserve_types[o._ufl_typecode_]:
            return o

        domain = o.domain()
        J = self.jacobian(Jacobian(domain))
        RFJ = CellFacetJacobian(domain)
        i, j, k = indices(3)
        return as_tensor(J[i, k]*RFJ[k, j], (i, j))

    @memoized_handler
    def facet_jacobian_inverse(self, o):
        if self._preserve_types[o._ufl_typecode_]:
            return o

        domain = o.domain()
        FJ = self.facet_jacobian(FacetJacobian(domain))
        # This could in principle use preserve_types[JacobianDeterminant] with minor refactoring:
        return inverse_expr(FJ)

    @memoized_handler
    def facet_jacobian_determinant(self, o):
        if self._preserve_types[o._ufl_typecode_]:
            return o

        domain = o.domain()
        FJ = self.facet_jacobian(FacetJacobian(domain))
        detFJ = determinant_expr(FJ)

        # TODO: Should we "sign" the facet jacobian determinant for manifolds?
        #       It's currently used unsigned in apply_integral_scaling.
        #if domain.topological_dimension() < domain.geometric_dimension():
        #    co = CellOrientation(domain)
        #    detFJ = co*detFJ

        return detFJ

    @memoized_handler
    def spatial_coordinate(self, o):
        "Fall through to coordinate field of domain if it exists."
        if self._preserve_types[o._ufl_typecode_]:
            return o

        domain = o.domain()
        x = domain.ufl_coordinates()
        if x is None:
            # Old affine domains
            return o

        # TODO: If we're not using Coefficient to represent the spatial coordinate,
        # we can just as well always return o here too unless we add representation
        # of basis functions and dofs to the ufl layer (which is nice to avoid).
        if x.element().mapping() != "identity":
            error("Piola mapped coordinates are not implemented.")
        return ReferenceValue(x)

    @memoized_handler
    def cell_coordinate(self, o):
        "Compute from physical coordinates if they are known, using the appropriate mappings."
        if self._preserve_types[o._ufl_typecode_]:
            return o

        domain = o.domain()
        K = self.jacobian_inverse(JacobianInverse(domain))
        x = self.spatial_coordinate(SpatialCoordinate(domain))
        x0 = CellOrigin(domain)
        i, j = indices(2)
        X = as_tensor(K[i, j] * (x[j] - x0[j]), (i,))
        return X

    @memoized_handler
    def facet_cell_coordinate(self, o):
        if self._preserve_types[o._ufl_typecode_]:
            return o

        error("Missing computation of facet reference coordinates "
              "from physical coordinates via mappings.")

    @memoized_handler
    def cell_volume(self, o):
        if self._preserve_types[o._ufl_typecode_]:
            return o

        domain = o.domain()
        if not domain.is_piecewise_linear_simplex_domain():
            # Don't lower for non-affine cells, instead leave it to form compiler
            warning("Only know how to compute the cell volume of an affine cell.")
            return o

        r = self.jacobian_determinant(JacobianDeterminant(domain))
        r0 = ReferenceCellVolume(domain)
        return abs(r * r0)

    @memoized_handler
    def facet_area(self, o):
        if self._preserve_types[o._ufl_typecode_]:
            return o

        domain = o.domain()
        if not domain.is_piecewise_linear_simplex_domain():
            # Don't lower for non-affine cells, instead leave it to form compiler
            warning("Only know how to compute the facet area of an affine cell.")
            return o

        r = self.facet_jacobian_determinant(FacetJacobianDeterminant(domain))
        r0 = ReferenceFacetVolume(domain)
        return abs(r * r0)

    @memoized_handler
    def circumradius(self, o):
        if self._preserve_types[o._ufl_typecode_]:
            return o

        domain = o.domain()
        if not domain.is_piecewise_linear_simplex_domain():
            # Don't lower for non-affine cells, instead leave it to form compiler
            warning("Only know how to compute the circumradius of an affine cell.")
            return o

        cellname = domain.ufl_cell().cellname()
        cellvolume = self.cell_volume(CellVolume(domain))

        if cellname == "interval":
            r = 0.5 * cellvolume

        elif cellname == "triangle":
            J = self.jacobian(Jacobian(domain))
            trev = CellEdgeVectors(domain)
            num_edges = 3
            i, j, k = indices(3)
            elen = [sqrt((J[i, j]*trev[edge, j])*(J[i, k]*trev[edge, k]))
                    for edge in range(num_edges)]

            r = (elen[0] * elen[1] * elen[2]) / (4.0 * cellvolume)

        elif cellname == "tetrahedron":
            J = self.jacobian(Jacobian(domain))
            trev = CellEdgeVectors(domain)
            num_edges = 6
            i, j, k = indices(3)
            elen = [sqrt((J[i, j]*trev[edge, j])*(J[i, k]*trev[edge, k]))
                    for edge in range(num_edges)]

            # elen[3] = length of edge 3
            # la, lb, lc = lengths of the sides of an intermediate triangle
            la = elen[3] * elen[2]
            lb = elen[4] * elen[1]
            lc = elen[5] * elen[0]
            # p = perimeter
            p = (la + lb + lc)
            # s = semiperimeter
            s = p / 2
            # area of intermediate triangle with Herons formula
            triangle_area = sqrt(s * (s - la) * (s - lb) * (s - lc))
            r = triangle_area / (6.0 * cellvolume)

        else:
            error("Unhandled cell type %s." % cellname)

        return r

    @memoized_handler
    def min_cell_edge_length(self, o):
        if self._preserve_types[o._ufl_typecode_]:
            return o

        domain = o.domain()
        if not domain.is_piecewise_linear_simplex_domain():
            # Don't lower for non-affine cells, instead leave it to form compiler
            warning("Only know how to compute the min_cell_edge_length of an affine cell.")
            return o

        cellname = domain.ufl_cell().cellname()

        J = self.jacobian(Jacobian(domain))
        trev = CellEdgeVectors(domain)
        num_edges = trev.ufl_shape[0]
        i, j, k = indices(3)
        elen = [sqrt((J[i, j]*trev[edge, j])*(J[i, k]*trev[edge, k]))
                for edge in range(num_edges)]

        if cellname == "triangle":
            return min_value(elen[0], min_value(elen[1], elen[2]))
        elif cellname == "tetrahedron":
            min1 = min_value(elen[0], min_value(elen[1], elen[2]))
            min2 = min_value(elen[3], min_value(elen[4], elen[5]))
            return min_value(min1, min2)
        else:
            error("Unhandled cell type %s." % cellname)

    @memoized_handler
    def max_cell_edge_length(self, o):
        if self._preserve_types[o._ufl_typecode_]:
            return o

        domain = o.domain()
        if not domain.is_piecewise_linear_simplex_domain():
            # Don't lower for non-affine cells, instead leave it to form compiler
            warning("Only know how to compute the max_cell_edge_length of an affine cell.")
            return o

        cellname = domain.ufl_cell().cellname()

        J = self.jacobian(Jacobian(domain))
        trev = CellEdgeVectors(domain)
        num_edges = trev.ufl_shape[0]
        i, j, k = indices(3)
        elen = [sqrt((J[i, j]*trev[edge, j])*(J[i, k]*trev[edge, k]))
                for edge in range(num_edges)]

        if cellname == "triangle":
            return max_value(elen[0], max_value(elen[1], elen[2]))
        elif cellname == "tetrahedron":
            max1 = max_value(elen[0], max_value(elen[1], elen[2]))
            max2 = max_value(elen[3], max_value(elen[4], elen[5]))
            return max_value(max1, max2)
        else:
            error("Unhandled cell type %s." % cellname)

    @memoized_handler
    def min_facet_edge_length(self, o):
        if self._preserve_types[o._ufl_typecode_]:
            return o

        domain = o.domain()
        if not domain.is_piecewise_linear_simplex_domain():
            # Don't lower for non-affine cells, instead leave it to form compiler
            warning("Only know how to compute the min_facet_edge_length of an affine cell.")
            return o

        cellname = domain.ufl_cell().cellname()

        if cellname == "triangle":
            return self.facet_area(FacetArea(domain))
        elif cellname == "tetrahedron":
            J = self.jacobian(Jacobian(domain))
            trev = FacetEdgeVectors(domain)
            num_edges = 3
            i, j, k = indices(3)
            elen = [sqrt((J[i, j]*trev[edge, j])*(J[i, k]*trev[edge, k]))
                    for edge in range(num_edges)]
            return min_value(elen[0], min_value(elen[1], elen[2]))
        else:
            error("Unhandled cell type %s." % cellname)

    @memoized_handler
    def max_facet_edge_length(self, o):
        if self._preserve_types[o._ufl_typecode_]:
            return o

        domain = o.domain()
        if not domain.is_piecewise_linear_simplex_domain():
            # Don't lower for non-affine cells, instead leave it to form compiler
            warning("Only know how to compute the max_facet_edge_length of an affine cell.")
            return o

        cellname = domain.ufl_cell().cellname()

        if cellname == "triangle":
            return self.facet_area(FacetArea(domain))
        elif cellname == "tetrahedron":
            J = self.jacobian(Jacobian(domain))
            trev = FacetEdgeVectors(domain)
            num_edges = 3
            i, j, k = indices(3)
            elen = [sqrt((J[i, j]*trev[edge, j])*(J[i, k]*trev[edge, k]))
                    for edge in range(num_edges)]
            return max_value(elen[0], max_value(elen[1], elen[2]))
        else:
            error("Unhandled cell type %s." % cellname)

    @memoized_handler
    def cell_normal(self, o):
        if self._preserve_types[o._ufl_typecode_]:
            return o

        domain = o.domain()
        gdim = domain.geometric_dimension()
        tdim = domain.topological_dimension()

        if tdim == gdim - 1: # n-manifold embedded in n-1 space
            i = Index()
            J = self.jacobian(Jacobian(domain))

            if tdim == 2:
                # Surface in 3D
                t0 = as_vector(J[i, 0], i)
                t1 = as_vector(J[i, 1], i)
                cell_normal = cross_expr(t0, t1)
            elif tdim == 1:
                # Line in 2D (cell normal is 'up' for a line pointing to the 'right')
                cell_normal = as_vector((-J[1, 0], J[0, 0]))
            else:
                error("Cell normal not implemented for tdim %d, gdim %d" % (tdim, gdim))

            # Return normalized vector, sign corrected by cell orientation
            co = CellOrientation(domain)
            return co * cell_normal / sqrt(cell_normal[i]*cell_normal[i])
        else:
            error("What do you want cell normal in gdim={0}, tdim={1} to be?".format(gdim, tdim))

    @memoized_handler
    def facet_normal(self, o):
        if self._preserve_types[o._ufl_typecode_]:
            return o

        domain = o.domain()
        tdim = domain.topological_dimension()

        if tdim == 1:
            # Special-case 1D (possibly immersed), for which we say that
            # n is just in the direction of J.
            J = self.jacobian(Jacobian(domain)) # dx/dX
            ndir = J[:, 0]

            gdim = domain.geometric_dimension()
            if gdim == 1:
                nlen = abs(ndir[0])
            else:
                i = Index()
                nlen = sqrt(ndir[i]*ndir[i])

            rn = ReferenceNormal(domain)  # +/- 1.0 here
            n = rn[0] * ndir / nlen
            r = n
        else:
            # Recall that the covariant Piola transform u -> J^(-T)*u preserves
            # tangential components. The normal vector is characterised by
            # having zero tangential component in reference and physical space.
            Jinv = self.jacobian_inverse(JacobianInverse(domain))
            i, j = indices(2)

            rn = ReferenceNormal(domain)
            # compute signed, unnormalised normal; note transpose
            ndir = as_vector(Jinv[j, i] * rn[j], i)

            # normalise
            i = Index()
            n = ndir / sqrt(ndir[i]*ndir[i])
            r = n

        ufl_assert(r.ufl_shape == o.ufl_shape,
                   "Inconsistent dimensions (in=%d, out=%d)." % (o.ufl_shape[0], r.ufl_shape[0]))
        return r

def apply_geometry_lowering(form, preserve_types=()):
    """Change GeometricQuantity objects in expression to the lowest level GeometricQuantity objects.

    Assumes the expression is preprocessed or at least that derivatives have been expanded.

    @param form:
        An Expr or Form.
    """
    if isinstance(form, Form):
        newintegrals = [apply_geometry_lowering(integral, preserve_types)
                        for integral in form.integrals()]
        return Form(newintegrals)

    elif isinstance(form, Integral):
        integral = form
        if integral.integral_type() in ("custom", "vertex"):
            automatic_preserve_types = [SpatialCoordinate, Jacobian]
        else:
            automatic_preserve_types = [CellCoordinate]
        preserve_types = set(preserve_types) | set(automatic_preserve_types)

        mf = GeometryLoweringApplier(preserve_types)
        newintegrand = map_expr_dag(mf, integral.integrand())
        return integral.reconstruct(integrand=newintegrand)

    elif isinstance(form, Expr):
        expr = form
        mf = GeometryLoweringApplier(preserve_types)
        return map_expr_dag(mf, expr)

    else:
        error("Invalid type %s" % (form.__class__.__name__,))
