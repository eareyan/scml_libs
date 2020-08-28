import unittest
import random
import pprint
from negmas import Contract
from typing import Dict
from SCMLContractsSigner import SCMLContractsSigner
from SCMLContractsSignerInspector import SCMLContractsSignerInspector
import pulp

"""
This is what a contract looks like:

Contract(
partners=['02Mon@0', 'SELLER'], 
agreement={'time': 25, 'quantity': 1, 'unit_price': 10}, 
annotation={'seller': 'SELLER', 'buyer': '02Mon@0', 'caller': 'SELLER', 'is_buy': True, 'product': 0}, 
issues=[], 
signed_at=-1, 
executed_at=-1, 
concluded_at=-1, 
nullified_at=-1, 
to_be_signed_at=2, 
signatures={'SELLER': 'SELLER'}, 
mechanism_state=None, 
mechanism_id=None, 
id='3a13f912-dc68-4c58-8573-70f06022f6df')
"""


class SCMLSignerTests(unittest.TestCase):
    AGENT_ID = 'Monty'
    OTHER_AGENT_ID = 'OTHER'
    DEFAULT_TRUST_PROB = {OTHER_AGENT_ID: 0.75}
    HOW_MANY_RUNS = 250
    HORIZON_LENGTH = 20

    @staticmethod
    def generate_random_contract(horizon: int = HORIZON_LENGTH, buy: bool = None, partners: Dict[str, float] = None):
        """
        Generates a random contract.
        If buy is None, the contract is equally likely to be a sell or buy contract.
        If buy is given, buy is expected to be a boolean indicated whehtehr the contract should be a buy or sell contract.
        :param horizon: time horizon
        :param buy: None or bool
        :param partners: a dictionary agent_id -> trust index
        :return: a random contract
        """
        # Create the list of partners. By default, is just us and the OTHER_AGENT_ID. Otherwise, we select a random partner from the input partners dictionary.
        agreement_partners = [SCMLSignerTests.AGENT_ID, SCMLSignerTests.OTHER_AGENT_ID] if partners is None else [SCMLSignerTests.AGENT_ID, random.choice(list(partners))]

        # Shuffle the partner list. This ensures that we test different orders in which this list might be given in the actual game.
        random.shuffle(agreement_partners)

        return Contract(partners=agreement_partners,
                        agreement={'time': random.randint(0, horizon - 1),
                                   'quantity': random.randint(1, horizon - 1),
                                   'unit_price': random.random() * (horizon - 1)},
                        annotation={'is_buy': random.randint(1, 2) <= 1 if buy is None else buy})

    def test_border_cases(self):
        """
        Testing some border cases, e.g., signing a list of empty contracts, or signing a list with only buy/sell agreements.
        """
        # Empty list of agreements should raise an exception.
        signer_output_empty_list = SCMLContractsSigner.sign(SCMLSignerTests.AGENT_ID, [], SCMLSignerTests.DEFAULT_TRUST_PROB)
        SCMLContractsSignerInspector.signer_inspector(signer_output_empty_list)
        self.assertEqual(len(signer_output_empty_list['list_of_signatures']), 0)

        # A list of agreements with no sell agreement should return a list of all None as signatures.
        signer_output_all_buy = SCMLContractsSigner.sign(SCMLSignerTests.AGENT_ID,
                                                         [SCMLSignerTests.generate_random_contract(100, buy=True) for _ in range(0, 10)],
                                                         SCMLSignerTests.DEFAULT_TRUST_PROB)
        SCMLContractsSignerInspector.signer_inspector(signer_output_all_buy)
        self.assertTrue(all(signature is None for signature in signer_output_all_buy['list_of_signatures']))

        # A list of agreements with all sell agreements should return a list of all None as signatures, as we can't buy inputs to satisfy demand.
        signer_output_all_sell = SCMLContractsSigner.sign(SCMLSignerTests.AGENT_ID,
                                                          [SCMLSignerTests.generate_random_contract(100, buy=False) for _ in range(0, 10)],
                                                          SCMLSignerTests.DEFAULT_TRUST_PROB)
        SCMLContractsSignerInspector.signer_inspector(signer_output_all_sell)
        self.assertTrue(all(signature is None for signature in signer_output_all_sell['list_of_signatures']))

    def test_manual_agreements_for_visual_inspection(self):
        """
        A test with some contracts created manually.
        """
        list_of_agreements = [
            Contract(partners=[SCMLSignerTests.AGENT_ID, SCMLSignerTests.OTHER_AGENT_ID], agreement={'time': 6, 'quantity': 1, 'unit_price': 110.0}, annotation={'is_buy': False}),
            Contract(partners=[SCMLSignerTests.AGENT_ID, SCMLSignerTests.OTHER_AGENT_ID], agreement={'time': 4, 'quantity': 1, 'unit_price': 10.00}, annotation={'is_buy': True}),
            Contract(partners=[SCMLSignerTests.AGENT_ID, SCMLSignerTests.OTHER_AGENT_ID], agreement={'time': 1, 'quantity': 1, 'unit_price': 12.00}, annotation={'is_buy': False}),
            Contract(partners=[SCMLSignerTests.AGENT_ID, SCMLSignerTests.OTHER_AGENT_ID], agreement={'time': 5, 'quantity': 1, 'unit_price': 11.01}, annotation={'is_buy': False}),
        ]

        # Call the signer.
        signer_output = SCMLContractsSigner.sign(SCMLSignerTests.AGENT_ID, list_of_agreements, SCMLSignerTests.DEFAULT_TRUST_PROB)
        SCMLContractsSignerInspector.signer_inspector(signer_output)

        # Check the consistency of the plan
        self.assertTrue(SCMLContractsSigner.is_sign_plan_consistent(signer_output))

        # Assert we get the optimal profit
        self.assertEqual(pulp.value(signer_output['model'].objective), 100.0 * SCMLSignerTests.DEFAULT_TRUST_PROB[SCMLSignerTests.OTHER_AGENT_ID])
        self.assertEqual(signer_output['profit'], 100.0 * SCMLSignerTests.DEFAULT_TRUST_PROB[SCMLSignerTests.OTHER_AGENT_ID])

    def test_random_agreements_for_visual_inspection(self):
        """
        Test for manual inspection of a few randomly generated contracts.
        """
        list_of_agreements = []
        # T = 100
        # num_buy_agreements = 100
        # num_sell_agreements = 50
        T = 10
        num_buy_agreements = 3
        num_sell_agreements = 3

        # Generate some random buy agreements.
        for i in range(num_buy_agreements):
            list_of_agreements.append(SCMLSignerTests.generate_random_contract(T, buy=True))

        # Generate some random sell agreements.
        for i in range(num_sell_agreements):
            list_of_agreements.append(SCMLSignerTests.generate_random_contract(T, buy=False))

        # Let's shuffle the list to simulate a run time environment.
        random.shuffle(list_of_agreements)

        # Call the signer.
        signer_output = SCMLContractsSigner.sign(SCMLSignerTests.AGENT_ID, list_of_agreements, SCMLSignerTests.DEFAULT_TRUST_PROB)
        SCMLContractsSignerInspector.signer_inspector(signer_output)

        # Check the consistency of the plan.
        self.assertTrue(SCMLContractsSigner.is_sign_plan_consistent(signer_output))

    def test_many_random_agreements(self, n: int = 50, partners: Dict[str, float] = None):
        """
        Test a few random contracts.
        """
        # Use the default partner dictionary in case we receive no custom partner dictionary
        partners = SCMLSignerTests.DEFAULT_TRUST_PROB if partners is None else partners

        # Generate some random agreements
        list_of_agreements = [SCMLSignerTests.generate_random_contract(partners=partners) for _ in range(0, n)]

        # Call the signer.
        signer_output = SCMLContractsSigner.sign(SCMLSignerTests.AGENT_ID, list_of_agreements, partners)
        SCMLContractsSignerInspector.signer_inspector(signer_output)
        SCMLContractsSignerInspector.solver_statistics(signer_output)

        # Check the consistency of the plan.
        self.assertTrue(SCMLContractsSigner.is_sign_plan_consistent(signer_output))

        # Check greedy.
        greedy_signer_output = SCMLContractsSigner.greedy_signer(SCMLSignerTests.AGENT_ID, list_of_agreements, partners)
        SCMLContractsSignerInspector.signer_inspector(greedy_signer_output, title='Greedy Solver')

        self.assertTrue(SCMLContractsSigner.is_sign_plan_consistent(greedy_signer_output))

        # Check that the greedy profit is less than the optimal solver's profit. We add 0.00001 tolerance to avoid numerical issues.
        if signer_output['profit'] is not None:
            print(f"greedy_profit = {greedy_signer_output['profit']}, OPT =  {signer_output['profit']}")
            self.assertLessEqual(greedy_signer_output['profit'] - 0.00001, signer_output['profit'])

    def test_multiple_runs(self):
        """
        Test many runs of signing contracts.
        """
        how_many_agreements = 50

        for _ in range(0, SCMLSignerTests.HOW_MANY_RUNS):
            self.test_many_random_agreements(n=random.randint(1, how_many_agreements))

    def test_different_trust(self):
        """
        In this test,  partners have randomly chosen trust probabilities.
        """
        how_many_partners = 50
        possible_partners = {f'partner_{i}': random.random() for i in range(1, how_many_partners)}
        for _ in range(0, SCMLSignerTests.HOW_MANY_RUNS):
            self.test_many_random_agreements(partners=possible_partners)

    def test_greedy_solver(self):
        """
        Simple tests for the greedy solver.
        """
        list_of_agreements = [
            Contract(partners=[SCMLSignerTests.AGENT_ID, SCMLSignerTests.OTHER_AGENT_ID], agreement={'time': 6, 'quantity': 1, 'unit_price': 110.0}, annotation={'is_buy': False}),
            Contract(partners=[SCMLSignerTests.AGENT_ID, SCMLSignerTests.OTHER_AGENT_ID], agreement={'time': 4, 'quantity': 1, 'unit_price': 10.00}, annotation={'is_buy': True}),
            Contract(partners=[SCMLSignerTests.AGENT_ID, SCMLSignerTests.OTHER_AGENT_ID], agreement={'time': 3, 'quantity': 1, 'unit_price': 100.00}, annotation={'is_buy': True}),
            Contract(partners=[SCMLSignerTests.AGENT_ID, SCMLSignerTests.OTHER_AGENT_ID], agreement={'time': 1, 'quantity': 2, 'unit_price': 12.00}, annotation={'is_buy': False}),
            Contract(partners=[SCMLSignerTests.AGENT_ID, SCMLSignerTests.OTHER_AGENT_ID], agreement={'time': 5, 'quantity': 1, 'unit_price': 11.01}, annotation={'is_buy': False}),
        ]

        signer_output = SCMLContractsSigner.greedy_signer(SCMLSignerTests.AGENT_ID, list_of_agreements, SCMLSignerTests.DEFAULT_TRUST_PROB)
        pprint.pprint(signer_output['agreements'])
        print(signer_output['list_of_signatures'])
        print(signer_output['profit'])
        # Check the consistency of the plan.
        self.assertTrue(SCMLContractsSigner.is_sign_plan_consistent(signer_output))


if __name__ == '__main__':
    unittest.main()
