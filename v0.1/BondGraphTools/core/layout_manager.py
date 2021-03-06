import math
import random
import logging
from functools import reduce
from itertools import permutations
import numpy as np
from scipy.sparse.csgraph import floyd_warshall, laplacian
from collections import defaultdict

logger = logging.getLogger(__name__)
DIRS = [(-1, 0), (0, -1), (1, 0), (0, 1)]


def simulated_annealing(nodes, edges, N=1000):
    """
    e is a list of edge tuples [(i,j), (i,m), ... ]


    Returns:

    """
    dirs = [(a,b) for a in range(-1,2) for b in range(-1,2)]

    a, d, (x, y) = _initial_conditions(nodes, edges)

    n = 0
    obj = 1000
    targets = set()
    w1 = 0.5
    w2 = 0.01

    lenx = len(x)
    step = math.ceil(math.sqrt(lenx))
    T = 1

    xt = [p for p in x]
    yt = [p for p in y]

    while n < N:
        # generate new candidate
        dist = 1 + step*int(math.exp(-n))
        for i in range(lenx):
            if i in targets:
                xt[i] = x[i] + random.randint(-step, step)
                yt[i] = y[i] + random.randint(-step, step)
            else:
                d = random.randint(0, 8)
                dx, dy = dirs[d]
                xt[i] = x[i] + dx*dist
                yt[i] = y[i] + dy*dist

        targets = set()
        crossings = 0
        zero_bonds = 0
        dist = 0
        node_dist = sum(
            sum(((x1-x2)**2 + (y1 - y2)**2 + w2)**(-2) for x1, y1 in zip(xt,yt))
                for x2,y2 in zip(xt,yt))

        bd_x = [xt[j] - xt[i] for i, j in edges]
        bd_y = [yt[j] - yt[i] for i, j in edges]

        for k, (i, j) in enumerate(edges):
            bx = bd_x[k]
            by = bd_y[k]
            d = bx**2 + by**2
            if d == 0:
                zero_bonds += 1
                targets &= {i, j}
            else:
                dist += d
                for l in range(k, len(edges)):
                    ip, jp = edges[l]

                    rs = bd_x[k]*bd_y[l] - bd_x[l]*bd_y[k]
                    if rs != 0:
                        t = ((x[ip] - x[i])*bd_y[l] - (y[ip] - y[i])*bd_x[l])/rs
                        u = ((x[ip] - x[i])*bx - (y[ip] - y[i])*by)/rs
                        if 0 <= u <= 1 and 0 <= t <= 1:
                            crossings += 1
                            targets &= {i, j, ip, jp}

        new_obj = dist**2*(1 + zero_bonds + crossings)**2 + w1 * node_dist

        delta = new_obj - obj
        if delta <= 0 or math.exp(-delta/T) > random.uniform(0, 1) or n == 0:
            x = [p for p in xt]
            y = [p for p in yt]
            obj = new_obj
        n += 1

    xm = int(sum(x)/lenx)
    ym = int(sum(y)/lenx)
    if abs(min(x) - max(x)) < abs(min(y) - max(y)):
        out = [(ym - yp[0], xp[0] - xm) for xp, yp in zip(x, y)]
    else:
        out = [(xp[0] - xm, yp[0] - ym) for xp, yp in zip(x, y)]

    return out


def _make_planar_graph(bond_graph):
    nodes = list()
    adj_dict = defaultdict(lambda: dict())
    for node in bond_graph.nodes.values():
        try:
            x, y = node.pos
            nodes.append((x, y))
        except TypeError:
            nodes.append((0, 0))
    adj_matrix = np.zeros((len(nodes), len(nodes)))
    edges = []
    for k, (i, j, _, _) in enumerate(bond_graph.bonds):
        edges.append((i,j))
        adj_matrix[i,j] = 1
        adj_matrix[j,i] = 1

        adj_dict[i][j] = k
        adj_dict[j][i] = k

    return nodes, edges


def branch_and_bound(nodes, edges):

    n = len(nodes)

    a, d, (x,y) = _initial_conditions(nodes, edges)

    a = np.triu(a)
    d = np.triu(d)

    M = np.triu(_distance_matrix(nodes))
    W = np.zeros((n, n))
    W[d != 0] = d[d != 0]**(-2)

    phi_0 = np.sum(W * (M - d)**2) + np.sum(d[M == 0])

    X0 = tuple((int(xp) if xp < 0 else int(np.ceil(xp)),
                int(yp) if yp < 0 else int(np.ceil(xp)))
                for xp, yp in zip(x, y))

    tree = [(X0, phi_0)]

    new_list = []
    i = 0
    max_i = 10000

    seen_list = set(X0)
    while tree and i < max_i:
        X, phi = tree.pop()

        for j in range(n):
            for dx, dy in DIRS:
                Xjk = tuple((x + dx, y + dy) if l == j else (x, y)
                            for l, (x, y) in enumerate(X))

                if Xjk not in seen_list:
                    seen_list.add(Xjk)
                    M_jk = np.triu(_distance_matrix(Xjk))
                    phi_jk = np.sum(W * (M_jk - d) ** 2)
                    phi_jk += np.sum(
                        d[M_jk == 0]
                    )

                    new_list.append((Xjk, phi_jk))

        new_list.append((X, phi))
        new_list.sort(key=lambda x: x[1], reverse=True)
        tree += new_list
        new_list = []
        i += 1
        # if sub_tree[0][1] > phi:
        #     if len(leaves) > max_leaves:
        #         leaves.pop(-1)
        #     leaves.add((X, phi))
        # else:
        #     sub_tree.add((X, phi))
        #
        # tree |= sub_tree
        #
        # index = max_tree - len(tree)
        # if index < -1:
        #     print("clearing")
        #     del tree[index:-1]
    pos, _ = tree[-1]

    return pos


def _distance_matrix(nodes):

    n = len(nodes)
    M = np.zeros((n, n))
    for i, (x1, y1) in enumerate(nodes):
        for j in range(i, n):
            x2, y2 = nodes[j]
            #M[i, j] = max(abs(x1 - x2), abs(y1 - y2))
            M[i, j] = ((x1 - x2)**2 + (y1 - y2)**2)**0.5
    return M


def force_directed(nodes, edges):

    n = len(nodes)

    # W_adj = np.zeros((len(nodes), len(nodes)))
    # for i, j in edges:
    #     W_adj[i, j] = 1
    #     W_adj[j, i] = 1
    #
    # graph_dist = floyd_warshall(W_adj, directed=False)
    # L = laplacian(W_adj)
    #
    # r0 = n**2
    # Xnew = [
    #     (r0/L[i, i]*np.cos(2*np.pi*i/(n-1)),
    #      r0/L[i, i]*np.sin(2*np.pi*i/(n-1))) for i in range(n)
    # ]
    W_adj, graph_dist, (xvect, yvect) = _initial_conditions(nodes, edges)

    Xnew = [(xp[0],yp[0]) for xp,yp in zip(xvect, yvect)]

    euclid_dist = _distance_matrix(Xnew)
    weights = np.zeros(W_adj.shape)
    weights[graph_dist!=0] = graph_dist[graph_dist!=0]**(-2)
    wp = np.zeros(W_adj.shape)
    wp[W_adj > 1] = W_adj[W_adj > 1]
    wp += wp.transpose()
    wp2 = wp
    wp2[wp!=0] = 0.5
    EP = np.ones_like(W_adj)
    EYE = np.eye(n)
    sigma_new = np.sum(weights * (euclid_dist - graph_dist) ** 2
                           + wp2*(euclid_dist - wp) ** 2
                           + (graph_dist / (euclid_dist + EP) - EYE)
                           )
    sigma_old = sigma_new*10
    eps = 0.00001
    delta = 0.1
    its = 0
    max_its = 2500
    scale = 0
    while max_its > its and (scale == 0 or
                             abs(sigma_new - sigma_old) > eps*sigma_old):
        Xold = Xnew
        sigma_old = sigma_new
        Xnew = []
        coeff = weights * (euclid_dist - graph_dist) + wp2 *(euclid_dist - wp)
        for k in range(n):
            dx = 0
            dy = 0
            for i in range(n-1):
                for j in range(i, n):
                    xi, yi = Xold[i]
                    xj, yj = Xold[j]
                    rij = max(euclid_dist[i, j], eps)

                    if i == k:
                        dx += (coeff[i, j] - graph_dist[i, j]*rij**(-2)) * (xi - xj)/rij
                        dy += (coeff[i, j] - graph_dist[i, j]*rij**(-2)) * (yi - yj)/rij
                    elif j == k:
                        dx -= (coeff[i, j] - graph_dist[i, j]*rij**(-2)) * (xi - xj)/rij
                        dy -= (coeff[i, j] - graph_dist[i, j]*rij**(-2)) * (yi - yj)/rij
            x, y = Xold[k]
            x, y = x - delta*dx, y - delta*dy

            Xnew.append((x,y))

        euclid_dist = _distance_matrix(Xnew)
        scale = (euclid_dist + 2 * np.eye(n)).min()
        sigma_new = np.sum(weights * (euclid_dist - graph_dist) ** 2
                           + wp2 * (euclid_dist - wp) ** 2
                           + (graph_dist / (euclid_dist + EP) - EYE)
                           )
        its += 1

    xm, ym = reduce((lambda P, Q: (P[0]+Q[0], P[1]+Q[1])), Xnew)
    Xnew = [(x - xm/n, y - ym/n) for x,y in Xnew]
    euclid_dist = _distance_matrix(Xnew)
    scale = min(euclid_dist[euclid_dist!= 0])/2

    Xnew =[(int(np.ceil(x/scale)) if x > 0 else int(np.floor(x)),
           int(np.ceil(y/scale)) if y > 0 else int(np.floor(y)))
           for x, y in Xnew]

    return Xnew


def _initial_conditions(nodes, edges):

    A = np.zeros((len(nodes), len(nodes)))
    # x y are always column vectors
    x, y = map(lambda q: np.array(q, ndmin=2).transpose(), zip(*nodes))

    for i, j in edges:
        A[i, j] = 1
        A[j, i] = 1

    D = floyd_warshall(A, directed=False)
    dmax = D.max(0)

    dsup = int(dmax.min())
    Dmax = int(dmax.max())

    for n in range(dsup, Dmax + 1):
        indicies = (dmax == n).nonzero()

        for k, idx in enumerate(indicies[0]):

            theta = 2*np.pi*k/len(indicies[0])

            x[idx] = np.cos(theta)*n
            y[idx] = np.sin(theta)*n

    return A, D, (x, y)


def arrange(bond_graph,
            algorithm=branch_and_bound,
            **kwargs):
    nodes, edges = _make_planar_graph(bond_graph)
    args = []
    nodes = algorithm(nodes, edges, *args, **kwargs)

    for i in bond_graph.nodes:
        bond_graph.nodes[i].pos = nodes[i]



def adj_matrix(edge_list):
    N = max(max(edge_list))

    A = np.zeros((N + 1, N + 1))
    for (i, j) in edge_list:
        A[i, j] = 1

    return A + A.T


def metro_map(nodes, edge_list):
    A = adj_matrix(edge_list)
    n, _ = A.shape
    D = floyd_warshall(A, directed=False)
    ecen = D.max(1)
    eta_0 = int(ecen.min())
    level_struct = {int(eta): np.where(ecen == eta)[0].tolist() for eta in
                    np.unique(ecen)}
    z = np.zeros((n, 1), dtype=np.complex_)
    z, R, N = initialise(z, eta_0, level_struct[eta_0], D)

    for k, eta in enumerate(range(eta_0, max(level_struct.keys()))):
        R += 1
        z, N = optimise_layer(z, N, R, eta, level_struct, A,D)

    Z = z - z.T
    zmin = np.abs(Z[Z!=0]).min()

    return [(zp.real/zmin, zp.imag/zmin) for zp in z.flatten()]


def permute(z, N, r, indicies):
    i_len = len(indicies)
    for idx in permutations(range(N), i_len):
        zp = z.copy()
        zp[indicies, 0] = [r * np.exp(w*2*np.pi*np.complex(0,1)/N) for w in idx]
        yield zp


def initialise(z, eta_0, level_set, d):
    if len(level_set) == 1:
        return z, 0, 0
    elif len(level_set) < 4:
        R_0 = 0.5
    else:
        R_0 = 1

    N_0 = int(2 * np.ceil(len(level_set) / 2))
    f = lambda x: init_obj(x, level_set, d, eta_0)

    for zp in permute(z, N_0, R_0, level_set):
        phi = f(zp)
        try:
            if phi_min > phi:
                phi_min = phi
                z_min = zp
        except NameError:
            z_min = zp
            phi_min = phi

    return z_min, R_0, N_0


def optimise_layer(z, N_eta, R, eta, level_struct, adj, dist):

    N = int(max(N_eta, 2*np.ceil(len(level_struct[eta+1])/2)))

    #f = lambda x: objective(x, eta, level_struct, adj)
    f = lambda x: objective_f(x, eta, level_struct, dist)
    z_min = z
    for zp in permute(z, N, R, level_struct[eta + 1]):
        phi = f(zp)
        try:
            if phi_min > phi:
                z_min = zp
                phi_min = phi
        except NameError:
            z_min = zp
            phi_min = phi


    return z_min, N


def init_obj(z, level_set, d, eta_0):
    phi = sum(
        [(np.abs(z[i] - z[j]) / d[i, j] - 1) ** 2 for i in level_set for j in
         level_set if i != j])
    return phi


def objective(z, eta, level_struct, A):
    target_set = [i for i in level_struct[eta] + level_struct[eta + 1]]
    phi = sum(
        [(np.abs(z[i] - z[j]) - 1) ** 2 for i in level_struct[eta + 1] for j in
         target_set if A[i, j] > 0])
    return phi


def objective_f(z, eta, level_struct, d):
    target_set = [i for i in level_struct[eta] + level_struct[eta + 1]]

    phi = sum(
        [(np.abs(z[i] - z[j]) / d[i, j] - 1) ** 2 for i in level_struct[eta + 1]
         for j in target_set if i != j])
    return phi
