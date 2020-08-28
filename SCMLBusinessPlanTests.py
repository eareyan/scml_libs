import itertools as it
import time
import unittest

import numpy as np

from SCMLBusinessPlan import SCMLBusinessPlan
from SCMLBusinessPlanInspector import SCMLBusinessPlanInspector


class SCMLBusinessTests(unittest.TestCase):
    HOW_MANY_RUNS = 5

    @staticmethod
    def synthetic_input(horizon: int, q_max: int):

        # Random quantities inn
        random_quantities_inn = np.random.randint(0, q_max, (horizon, q_max))
        normalization_qtt_inn = random_quantities_inn.sum(axis=1)
        Q_inn = {t: {q: random_quantities_inn[t][q] / normalization_qtt_inn[t] for q in range(0, q_max)} for t in range(0, horizon)}

        # Random quantities out
        random_quantities_out = np.random.randint(0, q_max, (horizon, q_max))
        normalization_qtt_out = random_quantities_out.sum(axis=1)
        Q_out = {t: {q: random_quantities_out[t][q] / normalization_qtt_out[t] for q in range(0, q_max)} for t in range(0, horizon)}

        # Random prices
        p_inn = {t: np.random.uniform(7, 12) for t in range(0, horizon)}
        p_out = {t: np.random.uniform(10, 15) for t in range(0, horizon)}

        # Sanity check: if the price of outputs is 0 always, then the program should buy and sell nothing.
        # p_out = {t: np.random.uniform(0, 0) for t in range(0, T)}

        # Debug print
        # pprint.pprint(Q_inn)
        # pprint.pprint(Q_out)
        return {'horizon': horizon,
                'q_max': q_max,
                'Q_inn': Q_inn,
                'Q_out': Q_out,
                'p_inn': p_inn,
                'p_out': p_out}

    def solve_a_plan(self, horizon: int, q_max: int):
        # Fetch synthetic input
        synthetic_input = SCMLBusinessTests.synthetic_input(horizon=horizon, q_max=q_max)
        horizon = synthetic_input['horizon']
        q_max = synthetic_input['q_max']
        Q_inn = synthetic_input['Q_inn']
        Q_out = synthetic_input['Q_out']
        p_inn = synthetic_input['p_inn']
        p_out = synthetic_input['p_out']

        t0 = time.time()
        inn = {t: SCMLBusinessPlan.compute_min_expectation(Q_inn[t], q_max) for t in range(0, horizon)}
        out = {t: SCMLBusinessPlan.compute_min_expectation(Q_out[t], q_max) for t in range(0, horizon)}
        print(f'took {time.time() - t0} to generate the minima')

        # Sanity check: the expectation of the minima should be non-negative
        for t, min_data in inn.items():
            for q, the_min in min_data.items():
                self.assertGreaterEqual(the_min, 0)

        # Debug print
        # pprint.pprint(inn)

        business_plan_output = SCMLBusinessPlan.compute_business_plan(horizon=horizon,
                                                                      q_max=q_max,
                                                                      out=out,
                                                                      inn=inn,
                                                                      p_out=p_out,
                                                                      p_inn=p_inn)
        SCMLBusinessPlanInspector.inspect_business_plan(business_plan_output=business_plan_output)
        total_buy_qtty = sum([business_plan_output['buy_plan'][t] for t in range(0, business_plan_output['horizon'])])
        total_sell_qtty = sum([business_plan_output['sell_plan'][t] for t in range(0, business_plan_output['horizon'])])
        return business_plan_output, total_buy_qtty, total_sell_qtty

    def test_multiple_runs(self):
        """
        Test many runs of signing contracts.
        """
        for _ in range(0, SCMLBusinessTests.HOW_MANY_RUNS):
            for horizon, q_max in it.product([5, 10, 15], [5, 15, 30]):
                business_plan_output, total_buy_qtty, total_sell_qtty = self.solve_a_plan(horizon=horizon, q_max=q_max)
                # Making sure the plan is consistent.
                if business_plan_output['optimistic']:
                    self.assertEqual(total_buy_qtty, total_sell_qtty)


if __name__ == '__main__':
    unittest.main()
