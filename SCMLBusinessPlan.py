import itertools as it
import time

import pulp
from typing import Dict


class SCMLBusinessPlan:

    @staticmethod
    def compute_min_expectation(dict_data, size) -> dict:
        """
        Compute the expectation of min(y, X) for all values of y in the support of X where X is a discrete random variable.
        This function implements a simple dynamic program which is fully documented in a separate latex document.
        If dict_data is empty, then we assume the random variable X has no support.
        :param dict_data: {x: P(X = x)} where x ranges from 0 to size.
        :param size: the support of random variable is from 0, ..., size.
        :return: a dictionary {y : E[min(y, X)]} for y ranging from 0, ..., size.
        """
        ret = {0: 0.0}
        temp = 1
        for i in range(1, size):
            # The dictionary only stores the values where X has positive probability. All other values are assumed to be zero.
            temp -= dict_data[i - 1] if i - 1 in dict_data else 0.0
            ret[i] = ret[i - 1] + temp
        return ret

    @staticmethod
    def compute_business_plan(horizon: int,
                              q_max: int,
                              out: Dict[int, Dict[int, float]],
                              inn: Dict[int, Dict[int, float]],
                              p_out: Dict[int, float],
                              p_inn: Dict[int, float],
                              optimistic: bool = True):
        """
        Constructs the business plan.
        :param horizon: an integer denoting the length of the plan.
        :param q_max: and integer denoting the range over which quantities will be optimized, 0, ..., q_max.
        :param out:
        :param inn:
        :param p_out:
        :param p_inn:
        :param optimistic:
        :return:
        """
        # Time the run of the algorithm.
        t0 = time.time()

        # Generate the pulp problem.
        model = pulp.LpProblem('Business_Plan_Solver', pulp.LpMaximize)

        # Generate the integer 0/1 decision variables. There are two kinds: inn_vars[t][k] and out_vars[t][k]
        # inn_vars[t][k] == 1 iff in the business plan the agent tries to buy k inputs at time t
        inn_vars = pulp.LpVariable.dicts('inn', ((t, k) for t, k in it.product(range(0, horizon), range(0, q_max))),
                                         lowBound=0, upBound=1, cat='Integer')
        # out_vars[t][k] == 1 iff in the business plan the agent tries to sell k inputs at time t
        out_vars = pulp.LpVariable.dicts('out', ((t, k) for t, k in it.product(range(0, horizon), range(0, q_max))),
                                         lowBound=0, upBound=1, cat='Integer')
        time_to_generate_variables = time.time() - t0

        # Generate the objective function - the total profit of the plan. Profit = revenue - cost
        # Here, revenue is the money received from sales of outputs, and cost is the money used to buy inputs.
        model += pulp.lpSum([out_vars[t, k] * out[t][k] * p_out[t] - inn_vars[t, k] * inn[t][k] * p_inn[t]
                             for t, k in it.product(range(0, horizon), range(0, q_max))])
        time_to_generate_objective = time.time() - t0

        # Generate the constraints. Only one quantity can be planned for at each time step for buying or selling.
        for t in range(0, horizon):
            model += sum([out_vars[t, k] for k in range(0, q_max)]) <= 1
            model += sum([inn_vars[t, k] for k in range(0, q_max)]) <= 1

        # Document here: optimistic == True means no bluffing, otherwise there is bluffing going on
        if optimistic:
            # Constraints that ensure there are enough outputs to sell at each time step.
            right_hand_size = sum([inn_vars[0, k] * k - out_vars[0, k] * k for k in range(0, q_max)])
            for t in range(1, horizon):
                model += sum([out_vars[t, k] * k for k in range(0, q_max)]) <= right_hand_size
                right_hand_size += sum([inn_vars[t, k] * k - out_vars[t, k] * k for k in range(0, q_max)])
        else:
            # Constraints that ensure there are enough outputs, in expectation, to sell at each time step.
            right_hand_size = sum([inn_vars[0, k] * inn[0][k] - out_vars[0, k] * out[0][k] for k in range(0, q_max)])
            for t in range(1, horizon):
                model += sum([out_vars[t, k] * out[t][k] for k in range(0, q_max)]) <= right_hand_size
                right_hand_size += sum([inn_vars[t, k] * inn[t][k] - out_vars[t, k] * out[t][k] for k in range(0, q_max)])

        # We assume that the planning starts with no inventory and thus, the agent cannot sell anything at time 0.
        for k in range(0, q_max):
            model += out_vars[0, k] == 0
        time_to_generate_constraints = time.time() - t0

        # Solve the ILP.
        t0 = time.time()
        model.solve(pulp.PULP_CBC_CMD(msg=False))
        time_to_solve = time.time() - t0

        # Read the solution.
        t0 = time.time()
        buy_plan = {t: sum([int(k * inn_vars[t, k].varValue) for k in range(0, q_max)]) for t in range(0, horizon)}
        sell_plan = {t: sum([int(k * out_vars[t, k].varValue) for k in range(0, q_max)]) for t in range(0, horizon)}
        time_to_read_plan = time.time() - t0

        return {'horizon': horizon,
                'q_max': q_max,
                'out': out,
                'inn': inn,
                'p_out': p_out,
                'p_inn': p_inn,
                'optimistic': optimistic,
                'time_to_generate_variables': time_to_generate_variables,
                'time_to_generate_objective': time_to_generate_objective,
                'time_to_generate_constraints': time_to_generate_constraints,
                'time_to_solve': time_to_solve,
                'time_to_read_plan': time_to_read_plan,
                'buy_plan': buy_plan,
                'sell_plan': sell_plan}
