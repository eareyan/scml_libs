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

    def test_border_cases(self):
        # Empty list of agreements should raise an exception
        self.assertRaises(Exception, SCMLContractsSigner.SCMLContractsSigner.sign, ('Monty', []))
        # A list of agreements with no sell agreement raise an exception
        self.assertRaises(Exception, SCMLContractsSigner.SCMLContractsSigner.sign, ('Monty', [Contract(agreement={'time': 4, 'quantity': 1, 'unit_price': 10}, annotation={'is_buy': True})]))

    @staticmethod
    def test():
        list_of_agreements = [
            Contract(agreement={'time': 6, 'quantity': 1, 'unit_price': 110}, annotation={'is_buy': False}),
            Contract(agreement={'time': 4, 'quantity': 1, 'unit_price': 10}, annotation={'is_buy': True}),
            Contract(agreement={'time': 1, 'quantity': 1, 'unit_price': 12}, annotation={'is_buy': False}),
            Contract(agreement={'time': 5, 'quantity': 1, 'unit_price': 11.01}, annotation={'is_buy': False}),
        ]
        signer_output = SCMLContractsSigner.SCMLContractsSigner.sign('Monty', list_of_agreements)
        SCMLContractsSigner.SCMLContractsSigner.signer_inspector(signer_output)

        # self.assertEqual(True, False)

    @staticmethod
    def test_random_for_manual_inspection():
        list_of_agreements = []
        # T = 100
        # num_buy_agreements = 100
        # num_sell_agreements = 50
        T = 10
        num_buy_agreements = 3
        num_sell_agreements = 3
        # Generate some random buy agreements
        for i in range(num_buy_agreements):
            list_of_agreements.append(Contract(agreement={'time': random.randint(1, T - 1),
                                                          'quantity': random.randint(1, T - 1),
                                                          'unit_price': random.randint(1, T - 1)},
                                               annotation={'is_buy': True}))
        for i in range(num_sell_agreements):
            list_of_agreements.append(Contract(agreement={'time': random.randint(1, T - 1),
                                                          'quantity': random.randint(1, T - 1),
                                                          'unit_price': random.randint(1, T - 1)},
                                               annotation={'is_buy': False}))
        # Let's shuffle the list to simulate a run time environment.
        random.shuffle(list_of_agreements)

        signer_output = SCMLContractsSigner.SCMLContractsSigner.sign('Monty', list_of_agreements)
        SCMLContractsSigner.SCMLContractsSigner.signer_inspector(signer_output)


if __name__ == '__main__':
    unittest.main()
