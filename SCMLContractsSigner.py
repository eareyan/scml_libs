import pulp
import time
from negmas import Contract
from typing import List, Dict


class SCMLContractsSigner:
    # Indices uses to access the agreements' tuples. DO NOT CHANGE.
    MASTER_INDEX = 0
    QUANTITY = 1
    TIME = 2
    PRICE = 3
    PARTNER_TRUST = 4
    SUB_INDEX = 5

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
    def find_partner_trust(agent_id: str, agreement: Contract, trust_probabilities: Dict[str, float]):
        """
        Given the agent's id and an agreement, return the partner of the agreement.
        This function checks that agreement.partners is a list of length exactly 2, where both elements of the list are distinct
        and one of them is agent_id. It also checks that the trust values are actual probabilities, i.e., numbers between 0 and 1.
        :param agent_id: our agent's id
        :param agreement: the agreement for which we want to find the agreement's partner
        :param trust_probabilities: a dictionary mapping an agent's id to its trust probability
        :return: the id of the partner.
        """
        # Find out who is the negotiation partner.
        assert len(agreement.partners) == 2
        assert agreement.partners[0] != agreement.partners[1]
        assert agreement.partners[0] == agent_id or agreement.partners[1] == agent_id
        partner = agreement.partners[0] if agreement.partners[0] != agent_id else agreement.partners[1]
        assert partner in trust_probabilities
        assert 0.0 <= trust_probabilities[partner] <= 1.0
        return trust_probabilities[partner]

    @staticmethod
    def partition_agreements(agent_id: str, agreements: List[Contract], trust_probabilities: Dict[str, float]):
        """
        Partition the list of agreements into agreements to buy inputs and agreements to sell outputs.
        :param agreements:
        :param trust_probabilities:
        :return:
        """
        agreements_to_buy_inputs = []
        agreements_to_sell_outputs = []
        for i, agreement in enumerate(agreements):
            # We collect here only the information we need from the original list of agreements.
            agreement_tuple = (i,
                               agreement.agreement['quantity'],
                               agreement.agreement['time'],
                               agreement.agreement['unit_price'],
                               SCMLContractsSigner.find_partner_trust(agent_id=agent_id, agreement=agreement, trust_probabilities=trust_probabilities))
            # Note that we assume here that we only engage in buy contracts for inputs and sell contracts for outputs.
            if agreement.annotation['is_buy']:
                agreements_to_buy_inputs.append(agreement_tuple)
            else:
                agreements_to_sell_outputs.append(agreement_tuple)
        return agreements_to_buy_inputs, agreements_to_sell_outputs

    @staticmethod
    def sign(agent_id: str, agreements: List[Contract], trust_probabilities: Dict[str, float]):
        """
        Given a list of agreements and trust probabilities, each of type negmas.Contract, decides which agreements to sign.
        :param agent_id: the agent's id (self.id of the calling agent)
        :param agreements: a list of agreements, each of type negmas.Contracts.
        :param trust_probabilities: a dictionary mapping an agent's id to its trust probability
        :return: a list of the same length as the input list of agreements. The i-th element of the return list
        is self.id/None in case the agent wants/do not wants to sign the i-th agreement in the input list.
        """
        # If the list of agreements is empty, then return an empty list of signatures.
        if len(agreements) == 0:
            return {'list_of_signatures': [],
                    'agent_id': agent_id,
                    'model': None,
                    'time_to_generate_ilp': None,
                    'time_to_solve_ilp': None,
                    'agreements': agreements,
                    'trust_probabilities': trust_probabilities,
                    'profit': None}

        # Partition agreements into buy and sell agreements.
        agreements_to_buy_inputs, agreements_to_sell_outputs = SCMLContractsSigner.partition_agreements(agent_id, agreements, trust_probabilities)

        # If there are no sell contracts, the signer has nothing to do and signs nothing.
        if len(agreements_to_sell_outputs) == 0:
            return {'list_of_signatures': [None] * len(agreements),
                    'agent_id': agent_id,
                    'model': None,
                    'time_to_generate_ilp': None,
                    'time_to_solve_ilp': None,
                    'agreements': agreements,
                    'trust_probabilities': trust_probabilities,
                    'profit': None}

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
                             sell_agreements[i][SCMLContractsSigner.PARTNER_TRUST] *
                             sell_sign_vars[s[SCMLContractsSigner.SUB_INDEX]]
                             for i, s in enumerate(sell_agreements)]
                            +
                            [-1.0 *
                             buy_agreements[i][SCMLContractsSigner.QUANTITY] *
                             buy_agreements[i][SCMLContractsSigner.PRICE] *
                             buy_agreements[i][SCMLContractsSigner.PARTNER_TRUST] *
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
        model.solve(pulp.PULP_CBC_CMD(msg=False))
        time_to_solve_ilp = time.time() - t0_solve

        # Record which contracts should be signed. We start by assuming no contracts will be signed.
        list_of_signatures = [None] * len(agreements)
        for agreement in buy_agreements_copy:
            if buy_sign_vars[agreement[SCMLContractsSigner.SUB_INDEX]].varValue is not None and int(buy_sign_vars[agreement[SCMLContractsSigner.SUB_INDEX]].varValue) == 1:
                list_of_signatures[agreement[SCMLContractsSigner.MASTER_INDEX]] = agent_id

        for agreement in sell_agreements_copy:
            if sell_sign_vars[agreement[SCMLContractsSigner.SUB_INDEX]].varValue is not None and int(sell_sign_vars[agreement[SCMLContractsSigner.SUB_INDEX]].varValue) == 1:
                list_of_signatures[agreement[SCMLContractsSigner.MASTER_INDEX]] = agent_id

        # Return multiple objects for inspection purposes. In production, we care about the list of sign contracts, 'list_of_signatures'.
        return {'list_of_signatures': list_of_signatures,
                'agent_id': agent_id,
                'model': model,
                'time_to_generate_ilp': time_to_generate_ilp,
                'time_to_solve_ilp': time_to_solve_ilp,
                'agreements': agreements,
                'trust_probabilities': trust_probabilities,
                'profit': pulp.value(model.objective)}

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
    def is_sign_plan_consistent(signer_output):
        """
        Given the output of a signer, this function checks if the plan is feasible, i.e.,
        if it never has a negative number of output units assuming all inputs are turned
        into outputs in 1 time step and that all outputs are sold as indicated by the sign plan.
        :param signer_output: the output of SCMLContractsSigner.sign
        :return: True if the plan is implementable, otherwise False.
        """
        horizon, buy_plan, sell_plan = SCMLContractsSigner.get_plan_as_lists(signer_output)
        assert len(buy_plan) == len(sell_plan)
        # Sanity check: we cannot sell at the first time period.
        assert sell_plan[0] == 0
        # Sanity check: we should not buy at the last time period, as we can't sell.
        assert buy_plan[len(buy_plan) - 1] == 0
        output_inventory_level = 0
        for i in range(1, len(buy_plan)):
            output_inventory_level += buy_plan[i - 1] - sell_plan[i]
            if output_inventory_level < 0:
                return False
        return True

    @staticmethod
    def greedy_signer(agent_id: str, agreements: List[Contract], trust_probabilities: Dict[str, float]):
        """
        A simple greedy signer. Signs sell contracts in descending order of revenue, provided the contract can be satisfied.
        The buy contracts are completely consumed by a sell contract, i.e., if they are used for one sell contract, any possible
        remaining units are effectively wasted.

        :param agent_id:
        :param agreements:
        :param trust_probabilities:
        :return:
        """
        buy_agreements, sell_agreements = SCMLContractsSigner.partition_agreements(agent_id, agreements, trust_probabilities)
        buy_agreements = sorted(buy_agreements, key=lambda x: x[SCMLContractsSigner.QUANTITY] * x[SCMLContractsSigner.PRICE] * x[SCMLContractsSigner.PARTNER_TRUST], reverse=False)
        sell_agreements = sorted(sell_agreements, key=lambda x: x[SCMLContractsSigner.QUANTITY] * x[SCMLContractsSigner.PRICE] * x[SCMLContractsSigner.PARTNER_TRUST], reverse=True)

        profit = 0
        set_of_signed_buy = set()
        set_of_signed_sell = set()
        for s in sell_agreements:
            qtty_s_satisfied = 0
            set_of_buy_for_s = set()
            cost = 0
            for i, b in enumerate(buy_agreements):
                if b[SCMLContractsSigner.TIME] < s[SCMLContractsSigner.TIME]:
                    qtty_s_satisfied += b[SCMLContractsSigner.QUANTITY]
                    set_of_buy_for_s.add(i)
                    cost += b[SCMLContractsSigner.QUANTITY] * b[SCMLContractsSigner.PRICE] * b[SCMLContractsSigner.PARTNER_TRUST]
                    # Todo: check if the per-unit price is low enough to actually commit to buy the inputs for the sell contract under consideration.
                    if qtty_s_satisfied >= s[SCMLContractsSigner.QUANTITY]:
                        set_of_signed_sell.add(s[SCMLContractsSigner.MASTER_INDEX])
                        set_of_signed_buy = set_of_signed_buy | {buy_agreements[i][SCMLContractsSigner.MASTER_INDEX] for i in set_of_buy_for_s}
                        # We have enough to satisfy this contract.
                        buy_agreements = [b for i, b in enumerate(buy_agreements) if i not in set_of_buy_for_s]
                        revenue = s[SCMLContractsSigner.QUANTITY] * s[SCMLContractsSigner.PRICE] * s[SCMLContractsSigner.PARTNER_TRUST]
                        profit += revenue - cost
                        break

        return {'agent_id': agent_id,
                'agreements': agreements,
                'list_of_signatures': [agent_id if (i in set_of_signed_buy or i in set_of_signed_sell) else None for i, _ in enumerate(agreements)],
                'trust_probabilities': trust_probabilities,
                'profit': profit}
