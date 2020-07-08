import unittest
import random
from negmas import Contract
import SCMLContractsSigner

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

    @staticmethod
    def generate_random_contract(T: int = 10, buy: bool = None):
        """
        Generates a random contract.
        If buy is None, the contract is equally likely to be a sell or buy contract.
        If buy is given, buy is expected to be a boolean indicated whehtehr the contract should be a buy or sell contract.
        :param T: time horizon
        :param buy: None or bool
        :return: a random contract
        """
        return Contract(agreement={'time': random.randint(1, T - 1),
                                   'quantity': random.randint(1, T - 1),
                                   'unit_price': random.random() * (T - 1)},
                        annotation={'is_buy': random.randint(1, 2) <= 1 if buy is None else buy})

    def test_border_cases(self):
        """
        Testing some border cases, e.g., signing a list of empty contracts, or signing a list with only buy/sell agreements.
        """
        # Empty list of agreements should raise an exception.
        signer_output_empty_list = SCMLContractsSigner.SCMLContractsSigner.sign('Monty', [])
        SCMLContractsSigner.SCMLContractsSigner.signer_inspector(signer_output_empty_list)
        self.assertEqual(len(signer_output_empty_list['list_of_signatures']), 0)

        # A list of agreements with no sell agreement should return a list of all None as signatures.
        signer_output_all_buy = SCMLContractsSigner.SCMLContractsSigner.sign('Monty',
                                                                             [SCMLSignerTests.generate_random_contract(100, buy=True) for _ in range(0, 10)])
        SCMLContractsSigner.SCMLContractsSigner.signer_inspector(signer_output_all_buy)
        self.assertTrue(all(signature is None for signature in signer_output_all_buy['list_of_signatures']))

        # A list of agreements with all sell agreements should return a list of all None as signatures, as we can't buy inputs to satisfy demand.
        signer_output_all_sell = SCMLContractsSigner.SCMLContractsSigner.sign('Monty',
                                                                              [SCMLSignerTests.generate_random_contract(100, buy=False) for _ in range(0, 10)])
        SCMLContractsSigner.SCMLContractsSigner.signer_inspector(signer_output_all_sell)
        self.assertTrue(all(signature is None for signature in signer_output_all_sell['list_of_signatures']))

    def test_manual_agreements_for_visual_inspection(self):
        """
        A test with some contracts created manually.
        """
        list_of_agreements = [
            Contract(agreement={'time': 6, 'quantity': 1, 'unit_price': 110.0}, annotation={'is_buy': False}),
            Contract(agreement={'time': 4, 'quantity': 1, 'unit_price': 10.00}, annotation={'is_buy': True}),
            Contract(agreement={'time': 1, 'quantity': 1, 'unit_price': 12.00}, annotation={'is_buy': False}),
            Contract(agreement={'time': 5, 'quantity': 1, 'unit_price': 11.01}, annotation={'is_buy': False}),
        ]

        # Call the signer.
        signer_output = SCMLContractsSigner.SCMLContractsSigner.sign('Monty', list_of_agreements)
        SCMLContractsSigner.SCMLContractsSigner.signer_inspector(signer_output)

        # Check the consistency of the plan
        self.assertTrue(SCMLContractsSigner.SCMLContractsSigner.plan_checker(signer_output))

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
        signer_output = SCMLContractsSigner.SCMLContractsSigner.sign('Monty', list_of_agreements)
        SCMLContractsSigner.SCMLContractsSigner.signer_inspector(signer_output)

        # Check the consistency of the plan.
        self.assertTrue(SCMLContractsSigner.SCMLContractsSigner.plan_checker(signer_output))

    def test_many_random_agreements(self, n: int = 50):
        """
        Test a few random contracts.
        """
        # Generate some random agreements.
        list_of_agreements = [SCMLSignerTests.generate_random_contract() for _ in range(0, n)]

        # Call the signer.
        signer_output = SCMLContractsSigner.SCMLContractsSigner.sign('Monty', list_of_agreements)
        SCMLContractsSigner.SCMLContractsSigner.signer_inspector(signer_output)

        # Check the consistency of the plan.
        self.assertTrue(SCMLContractsSigner.SCMLContractsSigner.plan_checker(signer_output))

    def test_multiple_runs(self):
        """
        Test many runs of signing contracts.
        """
        for _ in range(0, 100):
            self.test_many_random_agreements(n=random.randint(1, 100))


if __name__ == '__main__':
    unittest.main()
