import pulp
import time
from negmas import Contract
from typing import List
from pulp import PULP_CBC_CMD
from prettytable import PrettyTable


class SCMLContractsSigner:
    # Indices uses to access the agreements' tuples. DO NOT CHANGE.
    MASTER_INDEX = 0
    QUANTITY = 1
    TIME = 2
    PRICE = 3
    SUB_INDEX = 4

    @staticmethod
    def constraints_generation_helper(buy_agreements, buy_sign_vars, current_sell_time):
        """
        A helper function to generate the constraints of the contract signer.
        :param buy_agreements:
        :param buy_sign_vars:
        :param current_sell_time:
        :return:
        """
        partial_buy_sum = []
        while len(buy_agreements) > 0 and (buy_agreements[0][SCMLContractsSigner.TIME] < current_sell_time):
            c = buy_agreements.pop(0)
            partial_buy_sum += [buy_sign_vars[c[SCMLContractsSigner.SUB_INDEX]] * c[SCMLContractsSigner.QUANTITY]]
        return partial_buy_sum

    @staticmethod
    def sign(agent_id: str, agreements: List[Contract]):
        """
        Given a list of agreements, each of type negmas.Contract, decides which agreements to sign.
        :param agent_id: the agent's id (self.id of the calling agent)
        :param agreements: a list of agreements, each of type negmas.Contracts.
        :return: a list of the same length as the input list of agreements. The i-th element of the return list
        is self.id/None in case the agent wants/do not wants to sign the i-th agreement in the input list.
        """
        # If the list of agreements is empty, then return an empty list of signatures.
        if len(agreements) == 0:
            return {'list_of_signatures': [],
                    'model': None,
                    'time_to_generate_ilp': None,
                    'time_to_solve_ilp': None,
                    'agreements': agreements}

        # Partition the list of agreements into agreements to buy inputs and agreements to sell outputs.
        agreements_to_buy_inputs = []
        agreements_to_sell_outputs = []
        for i, agreement in enumerate(agreements):
            # We collect here only the information we need from the original list of agreements.
            agreement_tuple = (i,
                               agreement.agreement['quantity'],
                               agreement.agreement['time'],
                               agreement.agreement['unit_price'])
            # Note that we assume here that we only engage in buy contracts for inputs and sell contracts for outputs.
            if agreement.annotation['is_buy']:
                agreements_to_buy_inputs.append(agreement_tuple)
            else:
                agreements_to_sell_outputs.append(agreement_tuple)

        # If there are no sell contracts, the signer has nothing to do and signs nothing.
        if len(agreements_to_sell_outputs) == 0:
            return {'list_of_signatures': [None] * len(agreements),
                    'model': None,
                    'time_to_generate_ilp': None,
                    'time_to_solve_ilp': None,
                    'agreements': agreements}

        # For efficiency purposes, we order the agreements by delivery times. But, before we do, we must be able to
        # recover the indices of the agreements as given to the solver, otherwise, we can't map the output to the right agreements.
        buy_agreements = [agreement + (i,) for i, agreement in enumerate(agreements_to_buy_inputs)]
        sell_agreements = [agreement + (i,) for i, agreement in enumerate(agreements_to_sell_outputs)]

        # At this point an agreement is a tuple: (MASTER_INDEX, QUANTITY, TIME, PRICE, SUB_INDEX). Now we order by TIME.
        buy_agreements = sorted(buy_agreements, key=lambda x: x[SCMLContractsSigner.TIME])
        sell_agreements = sorted(sell_agreements, key=lambda x: x[SCMLContractsSigner.TIME])

        # The code that follows will change the agreement lists, so we make a copy of them for later reference.
        buy_agreements_copy = buy_agreements.copy()
        sell_agreements_copy = sell_agreements.copy()

        t0 = time.time()
        # Decision variables
        buy_sign_vars = pulp.LpVariable.dicts('buy_sign', (i for i, _ in enumerate(buy_agreements)), lowBound=0, upBound=1, cat='Integer')
        sell_sign_vars = pulp.LpVariable.dicts('sell_sign', (i for i, _ in enumerate(sell_agreements)), lowBound=0, upBound=1, cat='Integer')

        # Generate the pulp problem.
        model = pulp.LpProblem('Contract_Signer_Solver', pulp.LpMaximize)

        # The objective function is profit, defined as revenue minus cost.
        model += pulp.lpSum([sell_agreements[i][SCMLContractsSigner.QUANTITY] *
                             sell_agreements[i][SCMLContractsSigner.PRICE] *
                             sell_sign_vars[s[SCMLContractsSigner.SUB_INDEX]]
                             for i, s in enumerate(sell_agreements)]
                            +
                            [-1.0 *
                             buy_agreements[i][SCMLContractsSigner.QUANTITY] *
                             buy_agreements[i][SCMLContractsSigner.PRICE] *
                             buy_sign_vars[b[SCMLContractsSigner.SUB_INDEX]]
                             for i, b in enumerate(buy_agreements)])

        # Construct the constraints. The constraint model inventory feasibility, i.e., we don't commit to a sell unless we have enough outputs.
        current_sell_time = sell_agreements[0][SCMLContractsSigner.TIME]
        current_sell_time_sum = []
        partial_sell_sum = []
        partial_buy_sum = []
        result = []
        while len(sell_agreements) > 0:
            s = sell_agreements.pop(0)
            if current_sell_time == s[SCMLContractsSigner.TIME]:
                current_sell_time_sum += [sell_sign_vars[s[SCMLContractsSigner.SUB_INDEX]] * s[SCMLContractsSigner.QUANTITY]]
            else:
                partial_buy_sum += SCMLContractsSigner.constraints_generation_helper(buy_agreements, buy_sign_vars, current_sell_time)
                result += [(current_sell_time_sum.copy(), partial_buy_sum.copy(), partial_sell_sum.copy())]
                partial_sell_sum += current_sell_time_sum
                current_sell_time = s[SCMLContractsSigner.TIME]
                current_sell_time_sum = [sell_sign_vars[s[SCMLContractsSigner.SUB_INDEX]] * s[SCMLContractsSigner.QUANTITY]]
        partial_buy_sum += SCMLContractsSigner.constraints_generation_helper(buy_agreements, buy_sign_vars, current_sell_time)
        result += [(current_sell_time_sum.copy(), partial_buy_sum.copy(), partial_sell_sum.copy())]
        for left, middle, right in result:
            model += sum(left) <= sum(middle) - sum(right)

        # Measure the time taken to generate the ILP.
        time_to_generate_ilp = time.time() - t0

        # Solve the integer program and hide the output given by the solver.
        t0_solve = time.time()
        model.solve(PULP_CBC_CMD(msg=False))
        time_to_solve_ilp = time.time() - t0_solve

        # Record which contracts should be signed. We start by assuming no contracts will be signed.
        list_of_signatures = [None] * len(agreements)
        for agreement in buy_agreements_copy:
            if int(buy_sign_vars[agreement[SCMLContractsSigner.SUB_INDEX]].varValue) == 1:
                list_of_signatures[agreement[SCMLContractsSigner.MASTER_INDEX]] = agent_id

        for agreement in sell_agreements_copy:
            if int(sell_sign_vars[agreement[SCMLContractsSigner.SUB_INDEX]].varValue) == 1:
                list_of_signatures[agreement[SCMLContractsSigner.MASTER_INDEX]] = agent_id

        # Return multiple objects for inspection purposes. In production, we care about the list of sign contracts, 'list_of_signatures'.
        return {'list_of_signatures': list_of_signatures,
                'model': model,
                'time_to_generate_ilp': time_to_generate_ilp,
                'time_to_solve_ilp': time_to_solve_ilp,
                'agreements': agreements}

    @staticmethod
    def get_plan_as_lists(signer_output):
        # Check if agreements are received
        if len(signer_output['agreements']) == 0:
            return 0, [], []

        # Compute the horizon of the agreements defined as the time of the farthest agreement.
        horizon = max(a['agreement']['time'] for a in signer_output['agreements']) + 1
        buy_plan = [0 for _ in range(horizon)]
        sell_plan = [0 for _ in range(horizon)]
        for i, a in enumerate(signer_output['agreements']):
            if signer_output['list_of_signatures'][i] is not None:
                if a['annotation']['is_buy']:
                    buy_plan[a['agreement']['time']] = buy_plan[a['agreement']['time']] + a['agreement']['quantity']
                else:
                    sell_plan[a['agreement']['time']] = sell_plan[a['agreement']['time']] + a['agreement']['quantity']
        return horizon, buy_plan, sell_plan

    @staticmethod
    def plan_checker(signer_output):
        """
        Given the output of the signer, this function checks if the plan is feasible, i.e.,
        if it never has a negative number of output units assuming all inputs are turned
        into outputs in 1 time step and that all outputs are sold as indicated by the sign plan.
        :param signer_output: the output of SCMLContractsSigner.sign
        :return: True if the plan is implementable, otherwise False.
        """
        horizon, buy_plan, sell_plan = SCMLContractsSigner.get_plan_as_lists(signer_output)
        assert len(buy_plan) == len(sell_plan)
        assert sell_plan[0] == 0
        output_inventory_level = 0
        for i in range(1, len(buy_plan)):
            output_inventory_level += buy_plan[i - 1] - sell_plan[i]
            if output_inventory_level < 0:
                return False
        return True

    @staticmethod
    def signer_inspector(signer_output):
        """
        This function takes the output of the signer and outputs useful info. Used for debugging purposes.
        :param signer_output:
        :return:
        """
        # Some prints.
        agreements_table = PrettyTable()
        agreements_table.field_names = ['t', 'q', 'p', 'is_buy', 'signed?']
        for i, a in enumerate(signer_output['agreements']):
            agreements_table.add_row([a['agreement']['time'],
                                      a['agreement']['quantity'],
                                      a['agreement']['unit_price'],
                                      a['annotation']['is_buy'],
                                      'yes' if signer_output['list_of_signatures'][i] is not None else 'No'])
        print('\n--- Agreements ---')
        print(agreements_table)

        # Pretty table print of the buy and sell plan.
        horizon, buy_plan, sell_plan = SCMLContractsSigner.get_plan_as_lists(signer_output)
        signature_plan_table = PrettyTable()
        signature_plan_table.field_names = ['t'] + [str(t) for t in range(0, horizon)] + ['total']
        signature_plan_table.add_row(['buy'] + buy_plan + [sum(buy_plan)])
        signature_plan_table.add_row(['sel'] + sell_plan + [sum(sell_plan)])
        print('\n--- Signatures Plan ---')
        print(signature_plan_table)

        # Print solve time info.
        statistics_table = PrettyTable()
        statistics_table.field_names = ['Statistic', 'Value']

        time_to_generate_ilp = None
        if signer_output['time_to_generate_ilp'] is not None:
            time_to_generate_ilp = f"{signer_output['time_to_generate_ilp'] : .4f}"
        statistics_table.add_row(['time to generate the ILP', f'{time_to_generate_ilp} sec.'])

        time_to_solve_ilp = None
        if signer_output['time_to_solve_ilp'] is not None:
            time_to_solve_ilp = f"{signer_output['time_to_solve_ilp'] : .4f}"
        statistics_table.add_row(['time to solve the ILP', f"{time_to_solve_ilp} sec."])

        total_time = None
        if signer_output['time_to_generate_ilp'] is not None and signer_output['time_to_solve_ilp'] is not None:
            total_time = f"{signer_output['time_to_generate_ilp'] + signer_output['time_to_solve_ilp'] : .4f}"
        statistics_table.add_row(['total solver time', f'{total_time} sec.'])

        status = None
        if signer_output['model'] is not None:
            status = pulp.LpStatus[signer_output['model'].status]
        statistics_table.add_row(['solver status', f'{status}'])

        objective = None
        if signer_output['model'] is not None:
            objective = f"{pulp.value(signer_output['model'].objective):.4f}"
        statistics_table.add_row(['optimal profit', f'{objective}'])

        statistics_table.align['Statistic'] = 'r'
        print(statistics_table)
