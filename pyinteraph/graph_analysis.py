#!/usr/bin/env python
# -*- Mode: python; tab-width: 4; indent-tabs-mode:nil; coding:utf-8 -*-

#    PyInteraph, a software suite to analyze interactions and 
#    interaction network in structural ensembles.
#    Copyright (C) 2013 Matteo Tiberti <matteo.tiberti@gmail.com>, 
#                       Gaetano Invernizzi, Yuval Inbar, 
#                       Matteo Lambrughi, Gideon Schreiber, 
#                       Elena Papaleo <elena.papaleo@unimib.it> 
#                                     <elena.papaleo@bio.ku.dk>
#
#    This program is free software: you can redistribute it 
#    and/or modify it under the terms of the GNU General Public 
#    License as published by the Free Software Foundation, either 
#    version 3 of the License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  
#    If not, see <http://www.gnu.org/licenses/>.


import argparse
import logging as log
import os
import os.path
import re
import sys

from Bio import PDB
import MDAnalysis as mda
import networkx as nx
import numpy as np


############################## FUNCTIONS ##############################

def get_resnum(resstring):
    """Get the residue number from the string representing the
    residue."""

    # using re to get rid of a bug where residues having a number
    # in their name (i.e. SP2) caused the residue number to include 
    # such number.
    # Here, only the first instance of consecutive digits is returned
    # (the actual residue number).
    return re.findall(r"\d+", resstring)[0]


def replace_bfac_column(pdb, vals, pdb_out):
    """Replace the column containing B-factors in a PDB with
    custom values."""

    # create tthe PDB parser
    parser = PDB.PDBParser()
    # get the protein structure
    structure = parser.get_structure("protein", pdb)
    io = PDB.PDBIO()
    chain_offset = 0
    for model in structure:
        for chain in model:
            for i, residue in enumerate(chain):
                for atom in residue:
                    # set the custom value
                    atom.set_bfactor(float(vals[i+chain_offset]))
            chain_offset += len(chain)
    # set the structure for the output
    io.set_structure(structure)
    # save the structure to a new PDB file
    io.save(pdb_out)


def build_graph(fname, pdb = None):
    """Build a graph from the provided matrix"""

    try:
        data = np.loadtxt(fname)
    except:
        errstr = "Could not load file {:s} or wrong file format."
        raise ValueError(errstr.format(fname))
    # if the user provided a reference structure
    if pdb is not None:
        try:
            # generate a Universe object from the PDB file
            u = mda.Universe(pdb)
        except Exception:
            errstr = \
                "Exception caught during creation of the Universe."
            raise ValueError(errstr)      
        # generate identifiers for the nodes of the graph
        idfmt = "{:s}-{:d}{:s}"
        identifiers = \
            [idfmt.format(r.segment.segid, r.resnum, r.resname) \
             for r in u.residues]
    # if the user did not provide a reference structure
    else:
        # generate automatic identifiers going from 1 to the
        # total number of residues considered
        identifiers = [str(i) for i in range(1, data.shape[0]+1)]
    
    # generate a graph from the data loaded
    G = nx.Graph(data)
    # set the names of the graph nodes (in place)
    node_names = dict(zip(range(data.shape[0]), identifiers))
    nx.relabel_nodes(G, mapping = node_names, copy = False)
    # return the idenfiers and the graph
    return identifiers, G


def get_connected_components(G):
    """Get the connected components of the graph."""
    print(list(nx.connected_components(G)))
    return list(nx.connected_components(G))


def write_connected_components(ccs, outfile = None):
    """Write the connected components of the graph."""
    
    # outfile = None makes it output to the standard output
    # (PyInteraph 1 behavior)

    # output string format
    outstr = "Connected component {:d}\n ({:d} elements) {:s}\n"
    if not outfile:
        for numcc, cc in enumerate(ccs):
            sys.stdout.write(outstr.format(\
                numcc + 1, \
                len(cc), \
                ", ".join(sorted(cc, key = get_resnum))))
    else:
        ### TODO: output to a file, not standard output
        raise NotImplementedError


def write_connected_components_pdb(identifiers,
                                   ccs,
                                   ref,
                                   components_pdb,
                                   replace_bfac_func):
    """Write a PDB file with the input structure but the B factor
    column replaced for each residue with the number of the
    connected component it belongs to."""
    
    # create an empty array for the custom B factors
    conn_comp_array = np.zeros(len(identifiers))
    for i, cc in enumerate(ccs):
        for res in cc:
            conn_comp_array[identifiers.index(res)] = i+1
    # write a PDB file identical to the reference PDB file
    # but with the b-factor column filled with the number of
    # the connected component a residue belongs to
    replace_bfac_func(pdb = ref,
                      vals = conn_comp_array,
                      pdb_out = components_pdb)


def get_hubs(G, min_k = 3, sorting = None):
    """Get hubs in the graph."""

    # get the hubs
    hubs = {node : k for node, k in G.degree() if k >= min_k}
    # if no hubs were found
    if len(list(hubs.keys())) == 0:
        # warn the user that no hubs have been found
        logstr = \
            "No hubs with connectivity >= {:d} have been found."
        log.warning(logstr.format(min_k))    
        return
    # if no sorting was requested
    if sorting is None:
        sorted_hubs = hubs.items()
    # sort the hubs in ascending order of degree
    elif sorting == "ascending":
        sorted_hubs = sorted(hubs.items(),
                             key = lambda item: item[1],
                             reverse = False)
    # sort hubs in descending order of degree
    elif sorting == "descending":
        sorted_hubs = sorted(hubs.items(),
                             key = lambda item: item[1],
                             reverse = True)
    # return the sorted list of hubs
    print(sorted_hubs)
    return sorted_hubs


def write_hubs(hubs, outfile = None):
    """Write the hubs."""

    # outfile = None makes it output to the standard output
    # (PyInteraph 1 behavior)
    if not outfile:
        sys.stdout.write("Hubs:\n\tNode\tk\n")
        for hub, k in hubs:
            sys.stdout.write("\t{:s}\t{:d}\n".format(hub, k))
    else:
        ### TODO: output to a file, not print
        raise NotImplementedError


def write_hubs_pdb(identifiers,
                   hubs,
                   ref,
                   hubs_pdb,
                   replace_bfac_func):
    """Write a PDB file with the input structure but the B factor
    column replaced for each residue with the degree of that
    residue if the residue is a hub, zero otherwise."""
    
    hubs_array = np.zeros(len(identifiers))
    hubs = dict(hubs)
    for index, node in enumerate(identifiers):
        if node in hubs.keys():
            # check if the node is a hub by checking
            # if it is in the keys of the hubs dictionary
            hubs_array[index] = hubs[node]
    # write a PDB file identical to the reference PDB file
    # but with the b-factor column filled with the degree of
    # a residue if it is a hub, zero otherwise       
    replace_bfac_func(pdb = ref,
                      vals = hubs_array,
                      pdb_out = hubs_pdb) 


def get_paths(G, source, target, maxl, sort_paths_by):
    """Get all the shortest paths between a source and a target
    node in the graph."""
    
    # both nodes must be in the graph
    if not source in G.nodes() or not target in G.nodes():
        errstr = "Source or target residues have been badly specified."
        log.error(errstr)
        raise ValueError(errstr)
    # check if there are any paths
    try:
        shortest = nx.algorithms.shortest_path(G = G, \
                                               source = source, \
                                               target = target)
    except nx.NetworkXNoPath:
        log.warning("No paths exist between selected residues.")
        # return None since no paths were found
        return
    # check if the shortest is within the length cut-off
    if len(shortest) > maxl:
        warnstr = \
            "No paths were found between the given nodes at the " \
            "given cut-off. Shortest path length between these two " \
            "nodes is {:d}"
        log.warning(warnstr.format(len(shortest)))
        # return None since no path of the desired maximum
        # length were found
        return

    # calculate all the paths
    paths = list(nx.algorithms.simple_paths.all_simple_paths(\
                    G = G,
                    source = source,
                    target = target,
                    cutoff = maxl))
    # get the length of each path
    lengths = [len(p) for p in paths]         
    # calculate the sum of the each path's weights
    sum_weights = \
        [np.sum([G[p[i]][p[i+1]]["weight"] for i in range(len(p)-1)]) \
         for p in paths]           
    # calculate the average of each path's weights
    avg_weights = \
        [np.average([G[p[i]][p[i+1]]["weight"] for i in range(len(p)-1)]) \
         for p in paths]
    # sort the paths
    full_paths = zip(paths, lengths, sum_weights, avg_weights)
    # sort by length (ascending, shortest paths first)
    if sort_paths_by == "length":
        key = lambda x: x[1]
        reverse = False
    # sort by cumulative weight (descending, paths with highest
    # cumulative weight first)  
    elif sort_paths_by == "cumulative_weight":
        key = lambda x: x[2]
        reverse = True
    # sort by average weight (descending, paths with highest
    # average weight first)
    elif sort_paths_by == "avg_weight":
        key = lambda x: x[3]
        reverse = True
    # return the sortes list of paths
    return sorted(full_paths, key = key, reverse = reverse)


def write_paths(paths, outfile = None):
    """Write the paths."""

    # write the paths found to the output in a human-readable format
    if not outfile:
        sys.stdout.write(\
            "Path #\tLength\tSum of weights\tAverage weight\tPath\n")
        pathfmt_str = "{:d}\t{:d}\t{:.1f}\t\t{:.1f}\t\t{:s}\n"
        for index, path in enumerate(paths):
            sys.stdout.write(\
                pathfmt_str.format(\
                    index+1, path[1], path[2], path[3], \
                    ",".join(path[0])))
    else:
        ### TODO: output to a file, not print
        raise NotImplementedError


def write_paths_matrices(identifiers, G, paths, fmt, where):
    """For each path, write a matrix with all edges erased apart
    from those constituting the path."""
    
    for index, path in enumerate(paths):
        # for each path...
        path_mat = np.zeros(nx.adjacency_matrix(G).shape)
        for node in range(len(path[0])-1):
            # for each node in the path...
            x = identifiers.index(path[0][node])
            y = identifiers.index(path[0][node+1])
            path_mat[x,y] = G[path[0][node]][path[0][node+1]]["weight"]
            path_mat[y,x] = G[path[0][node+1]][path[0][node]]["weight"]
        # save the matrix
        mat_file = os.path.join(where, "path{:d}.dat".format(index+1))
        np.savetxt(mat_file, path_mat, fmt = fmt)
    


def main():
    ######################### ARGUMENT PARSER #########################

    description = "PyInteraph network analysis module."
    parser = argparse.ArgumentParser(description = description)

    r_helpstr = "Reference topology file"
    parser.add_argument("-r", "--reference",
                        metavar = "TOPOLOGY",
                        dest = "top",
                        type = str,
                        default = None,
                        help = r_helpstr)

    a_helpstr = "Input graph file"
    parser.add_argument("-a", "--adj-matrix",
                        metavar = "DAT",
                        dest = "dat",
                        type = str,
                        default = None,
                        help = a_helpstr)

    c_helpstr = "Calculate connected components"
    parser.add_argument("-c", "--components",
                        dest = "do_components",
                        action = "store_true",
                        default = False,
                        help = c_helpstr)

    u_helpstr = "Calculate hubs"
    parser.add_argument("-u", "--hubs",
                        dest = "do_hubs",
                        action = "store_true",
                        default = False,
                        help = u_helpstr)

    k_default = 3
    k_helpstr = "Minimum number of connections for hubs (default: {:d})"
    parser.add_argument("-k", "--hubs-cutoff",
                        dest = "hubs_cutoff",
                        default = k_default,
                        type = int,
                        help = k_helpstr.format(k_default))

    p_helpstr = "Calculate all simple paths between " \
                "two residues in the graph"
    parser.add_argument("-p", "--all-paths",
                        dest = "do_paths",
                        action = "store_true",
                        default = False,
                        help = p_helpstr)

    r1_helpstr = "First residue for paths calculation (see option -p)"
    parser.add_argument("-r1", "--source",
                        dest = "source",
                        default = None,
                        help = r1_helpstr)

    r2_helpstr = "Last residue for paths calculation (see option -p)"
    parser.add_argument("-r2", "--target",
                        dest = "target",
                        default = None,
                        help = r2_helpstr)

    l_default = 10
    l_helpstr = "Maximum path length (see option -p) (default: {:d})"
    parser.add_argument("-l", "--maximum-path-length", \
                        dest = "maxl",
                        default = l_default,
                        type = int,
                        help = l_helpstr.format(l_default))

    s_choices = ["length", "cumulative_weight", "avg_weight"]
    s_default = "lenght"
    s_helpstr = \
        "How to sort pathways in output. Possible choices are {:s}" \
        " (default: {:s})"
    parser.add_argument("-s", "--sort-paths",
                        dest = "sort_paths_by",
                        choices = s_choices,
                        default = "length",
                        help = \
                            s_helpstr.format(", ".join(s_choices), s_default))

    cb_helpstr = "Save connected components ID in PDB file"
    parser.add_argument("-cb", "--components-pdb",
                        dest = "components_pdb",
                        default = None,
                        help = cb_helpstr)

    ub_helpstr = "Save hub degrees in PDB file"
    parser.add_argument("-ub", "--hubs-pdb",
                        dest = "hubs_pdb",
                        default = None,
                        help = cb_helpstr)

    d_helpstr = "Write the paths found as matrices"
    parser.add_argument("-d", "--write-paths",
                        dest = "write_paths",
                        default = False,
                        action = "store_true",
                        help = d_helpstr)

    args = parser.parse_args()

    # check the presence of the adjacency matrix (or matrices)
    if not args.dat:
        # exit if the adjacency matrix was not speficied
        log.error("Graph adjacency matrix must be specified. Exiting ...")
        exit(1)
    # check the presence of the reference structure if the output
    # PDBs have been requested
    if (args.components_pdb or args.hubs_pdb) and (not args.top):
        # exit if the user requested the PDB files with connected
        # components and hubs but did not provide a reference PDB
        # file
        log.error(\
            "A PDB reference file must be supplied if using options " \
            "-cb and -ub. Exiting ...")
        exit(1)
    # build the graph
    try:
        identifiers, G = build_graph(args.dat, pdb = args.top)
    except ValueError:
        errstr = \
            "Could not build the graph from the files provided. " \
            "Exiting ..."
        log.error(errstr, exc_info = True)
        exit(1)
    # get graph nodes and edges
    nodes = G.nodes()
    edges = G.edges()
    # log about the graph building
    outstr = "Graph loaded! {:d} nodes, {:d} edges\n"
    sys.stdout.write(outstr.format(len(nodes), len(edges)))
    outstr = "Node list: \n{:s}\n"
    sys.stdout.write(outstr.format(\
        "\n".join([node for node in sorted(nodes, key = get_resnum)])))


    ###################### CONNECTED COMPONENTS #######################

    if args.do_components: 
        # calculate the connected components
        ccs = get_connected_components(G)
        # write the connected components
        write_connected_components(ccs = ccs, outfile = None)
        # if the user requested the PDB file with the connected
        # components
        if args.components_pdb:
            # write PDB file with B-factor column replaced
            write_connected_components_pdb(
                identifiers = identifiers,
                ccs = ccs,
                ref = args.top,
                components_pdb = args.components_pdb,
                replace_bfac_func = replace_bfac_column)


    ############################## HUBS ###############################
            
    if args.do_hubs:
        # calculate the hubs
        hubs = get_hubs(G = G,
                        min_k = args.hubs_cutoff,
                        sorting = "descending")
        # if hubs have been found
        if hubs:
            # write the hubs
            write_hubs(hubs = hubs, outfile = None)
            # if the user requested the PDB file with the hubs
            if args.hubs_pdb:
                # write PDB file with B-factor column replaced
                write_hubs_pdb(\
                    identifiers = identifiers,
                    hubs = hubs,
                    ref = args.top,
                    hubs_pdb = args.hubs_pdb,
                    replace_bfac_func = replace_bfac_column)
        else:
            log.warning("No hubs were found")


    ############################## PATHS ##############################
            
    if args.do_paths:    
        # source and target must be specified
        if not args.source or not args.target:
            log.error(\
                "You must specify source and target residues. " \
                "Exiting...")
            exit(1)
        try:
            # calculate paths between a pair of residues
            paths = get_paths(G = G,
                              source = args.source,
                              target = args.target,
                              maxl = args.maxl,
                              sort_paths_by = args.sort_paths_by)
        except ValueError:
            errstr = "Could not compute paths."
            log.error(errstr)
            paths = None
        # if paths have been found
        if paths is not None:
            # write the paths
            write_paths(paths = paths, outfile = None)
            # if path matrices have been requested           
            if args.write_paths:
                # write paths as matrices
                write_paths_matrices(identifiers = identifiers,
                                     G = G,
                                     paths = paths,
                                     fmt = "%.1f",
                                     where = os.getcwd())

if __name__ == "__main__":
    main()

