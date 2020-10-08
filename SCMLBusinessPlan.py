from collections import defaultdict
import itertools as it
import time

import pulp
from typing import Dict


class SCMLBusinessPlan:
    @staticmethod
    def compute_min_expectation(dict_data: Dict[int, float], size: int) -> dict:
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
    def get_minima(
        horizon: int,
        q_max: int,
        Q_inn: Dict[int, Dict[int, float]],
        Q_out: Dict[int, Dict[int, float]],
    ):
        """
        Given the time horizon, the range of the domain optimization 0, ..., q_max, and the probability
        distribution on the input and output produce, this function returns two maps:
            {t : {q : E[min(q, Q_inn) } } and {t : {q : E[min(q, Q_out) } }.
        This maps are used by the business plan solver.
        :param horizon: an integer denoting the length of the plan.
        :param q_max: and integer denoting the range over which quantities will be optimized, 0, ..., q_max.
        :param Q_inn: a map {t : { q : P(Q_inn = q @ time t} }, i.e., probabilities of seeing quantities for the buy product for each time in the horizon.
        :param Q_out: a map {t : { q : P(Q_out = q @ time t} }, i.e., probabilities of seeing quantities for the sell product for each time in the horizon.
        :return:
        """
        inn = {
            t: SCMLBusinessPlan.compute_min_expectation(Q_inn[t], q_max)
            for t in range(0, horizon)
        }
        out = {
            t: SCMLBusinessPlan.compute_min_expectation(Q_out[t], q_max)
            for t in range(0, horizon)
        }
        return inn, out

    @staticmethod
    def compute_business_plan(
        horizon: int,
        q_max: int,
        Q_inn: Dict[int, Dict[int, float]],
        Q_out: Dict[int, Dict[int, float]],
        p_inn: Dict[int, float],
        p_out: Dict[int, float],
        C_inn: Dict[int, int] = None,
        C_out: Dict[int, int] = None,
        optimistic: bool = True,
        step: int = 0,
    ):
        """
        Constructs the business plan.
        :param horizon: an integer denoting the length of the plan.
        :param q_max: and integer denoting the range over which quantities will be optimized, 0, ..., q_max.
        :param Q_inn: a map {t : { q : P(Q_inn = q @ time t} }, i.e., probabilities of seeing quantities for the buy product for each time in the horizon.
        :param Q_out: a map {t : { q : P(Q_out = q @ time t} }, i.e., probabilities of seeing quantities for the sell product for each time in the horizon.
        :param p_inn: a map {t : price for buy product @ time t}, i.e., the expected price at which the input product will be traded at time t.
        :param p_out: a map {t : price for the sell product @ time t }, i.e., the expected price at which the output product will be traded at time t.
        :param C_inn: a map {t: quantity of the input that we already committed to through contracts/agreements (or hypothetical ones)}
        :param C_out: a map {t: quantity of the output that we already committed to through contracts/agreements (or hypothetical ones)}
        :param optimistic: a boolean.
        :param step: the first step at which quantities can be nonzero
        :return: a map with all the information about the solver and the actual business plan.
        """
        # initialized C_inn to all zeros if not given and make sure
        # it defaults to zero for keys not given in the inputs
        if C_inn is None:
            C_inn = defaultdict(int)
        else:
            _G = defaultdict(int)
            for k, v in C_inn.items():
                _G[k] = k
            C_inn = _G

        if C_out is None:
            C_out = defaultdict(int)
        else:
            _G = defaultdict(int)
            for k, v in C_out.items():
                _G[k] = k
            C_out = _G
        # Time the run of the algorithm.
        t0 = time.time()

        # Generate the minima.
        inn, out = SCMLBusinessPlan.get_minima(horizon, q_max, Q_inn, Q_out)

        # Generate the pulp problem.
        model = pulp.LpProblem("Business_Plan_Solver", pulp.LpMaximize)

        # Generate the integer 0/1 decision variables. There are two kinds: inn_vars[t][k] and out_vars[t][k]
        # inn_vars[t][k] == 1 iff in the business plan the agent tries to buy k inputs at time t
        inn_vars = pulp.LpVariable.dicts(
            "inn",
            ((t, k) for t, k in it.product(range(0, horizon), range(0, q_max))),
            lowBound=0,
            upBound=1,
            cat="Integer",
        )
        # out_vars[t][k] == 1 iff in the business plan the agent tries to sell k inputs at time t
        out_vars = pulp.LpVariable.dicts(
            "out",
            ((t, k) for t, k in it.product(range(0, horizon), range(0, q_max))),
            lowBound=0,
            upBound=1,
            cat="Integer",
        )
        time_to_generate_variables = time.time() - t0

        # Generate the objective function - the total profit of the plan. Profit = revenue - cost
        # Here, revenue is the money received from sales of outputs, and cost is the money used to buy inputs.
        model += pulp.lpSum(
            [
                out_vars[t, k] * out[t][k] * p_out[t]
                - inn_vars[t, k] * inn[t][k] * p_inn[t]
                for t, k in it.product(range(0, horizon), range(0, q_max))
            ]
        )
        time_to_generate_objective = time.time() - t0

        # Generate the constraints. Only one quantity can be planned for at each time step for buying or selling.
        for t in range(0, horizon):
            model += sum([out_vars[t, k] for k in range(0, q_max)]) <= 1
            model += sum([inn_vars[t, k] for k in range(0, q_max)]) <= 1

        # Document here: optimistic == True means no bluffing, otherwise there is bluffing going on
        if optimistic:
            # Constraints that ensure there are enough outputs to sell at each time step.
            right_hand_size = sum(
                [inn_vars[0, k] * k - out_vars[0, k] * k for k in range(0, q_max)]
            )
            for t in range(1, horizon):
                model += (
                    sum([out_vars[t, k] * k for k in range(0, q_max)])
                    <= right_hand_size
                )
                right_hand_size += sum(
                    [inn_vars[t, k] * k - out_vars[t, k] * k for k in range(0, q_max)]
                )
        else:
            # Constraints that ensure there are enough outputs, in expectation, to sell at each time step.
            right_hand_size = sum(
                [
                    inn_vars[0, k] * inn[0][k] - out_vars[0, k] * out[0][k]
                    for k in range(0, q_max)
                ]
            )
            for t in range(1, horizon):
                model += (
                    sum([out_vars[t, k] * out[t][k] for k in range(0, q_max)])
                    <= right_hand_size
                )
                right_hand_size += sum(
                    [
                        inn_vars[t, k] * inn[t][k] - out_vars[t, k] * out[t][k]
                        for k in range(0, q_max)
                    ]
                )
        # Adding constraints from committed inputs/outputs
        for t in range(0, horizon):
            model += (
                sum([out_vars[t, k] * out[t][k] for k in range(0, q_max)]) >= C_out[t]
            )
            model += (
                sum([inn_vars[t, k] * inn[t][k] for k in range(0, q_max)]) >= C_inn[t]
            )
        # We assume that the planning starts with no inventory and thus, the agent cannot sell anything at time 0.
        # Yasser: except if it already have committed to selling.
        # Yasser: Something seems strange here. Originally, this was setting all  to 0, Should not out_vars[0, 0]
        #         have been set to 1.
        if step == 0:
            for k in range(0, q_max):
                if k == C_out[0]:
                    model += out_vars[0, k] == 1
                else:
                    model += out_vars[0, k] == 0
        else:
            # We force all quantities before `step` to be whatever we are committed to.
            for i in range(step):
                for k in range(0, q_max):
                    if k == C_out[i]:
                        model += out_vars[i, k] == 1
                    else:
                        model += out_vars[i, k] == 0
                    if k == C_inn[i]:
                        model += inn_vars[i, k] == 1
                    else:
                        model += inn_vars[i, k] == 0

        time_to_generate_constraints = time.time() - t0

        # Solve the ILP.
        t0 = time.time()
        model.solve(pulp.PULP_CBC_CMD(msg=False))
        time_to_solve = time.time() - t0

        # Read the solution.
        t0 = time.time()
        buy_plan = {
            t: sum([int(k * inn_vars[t, k].varValue) for k in range(0, q_max)])
            for t in range(0, horizon)
        }
        sell_plan = {
            t: sum([int(k * out_vars[t, k].varValue) for k in range(0, q_max)])
            for t in range(0, horizon)
        }
        time_to_read_plan = time.time() - t0

        return {
            "horizon": horizon,
            "q_max": q_max,
            "out": out,
            "inn": inn,
            "p_out": p_out,
            "p_inn": p_inn,
            "optimistic": optimistic,
            "time_to_generate_variables": time_to_generate_variables,
            "time_to_generate_objective": time_to_generate_objective,
            "time_to_generate_constraints": time_to_generate_constraints,
            "time_to_solve": time_to_solve,
            "time_to_read_plan": time_to_read_plan,
            "buy_plan": buy_plan,
            "sell_plan": sell_plan,
        }
